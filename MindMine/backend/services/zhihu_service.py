"""知乎能力适配层。

硬约束（AGENTS.md）：
    所有 zhihu-cli 调用集中在本文件。
    业务层禁止直接执行 CLI，Vue 组件禁止直接调知乎 API。

能力边界依据已完成的 Capability Audit，不重新猜 API：
  - question recommend --query   按主题推荐问题（已验证）
  - search zhihu --query         社区观点主来源（已验证，含 AuthorName/Url/ContentText）
  - question answers --question-url  辅助来源，quota 仅 100，谨慎使用
  - 无 create/publish answer 能力 —— 禁止自己猜发布 Endpoint

所有调用都有 timeout，失败快速 fallback，不把错误栈暴露给用户。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field

from config import settings

logger = logging.getLogger("mindmine.zhihu")

_QUESTION_ID_RE = re.compile(r"/question/(\d+)")


class ZhihuUnavailable(Exception):
    """真实知乎能力不可用。上层据此 fallback。"""


@dataclass
class ZhihuQuestion:
    title: str
    url: str
    question_id: str = ""

    def __post_init__(self) -> None:
        if not self.question_id:
            m = _QUESTION_ID_RE.search(self.url or "")
            self.question_id = m.group(1) if m else ""


@dataclass
class ZhihuAnswer:
    """一条真实的社区回答。保留可追溯字段。"""

    title: str = ""
    author_name: str = ""
    content_text: str = ""
    url: str = ""
    badge: str = ""
    authority_level: str = ""
    question_id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.question_id:
            m = _QUESTION_ID_RE.search(self.url or "")
            self.question_id = m.group(1) if m else ""


class ZhihuService:
    """唯一的知乎适配器。"""

    def __init__(self) -> None:
        self._cli = settings.resolved_zhihu_cli_path()

    @property
    def available(self) -> bool:
        import os

        return settings.zhihu_mode() == "real" and bool(self._cli) and os.path.exists(self._cli)

    # ------------------------------------------------------------------
    # CLI 执行
    # ------------------------------------------------------------------

    async def _run(self, args: list[str], *, stage: str) -> dict:
        """执行一次 CLI 调用并解析 JSON。

        超时/非零退出/JSON 异常统一抛 ZhihuUnavailable。
        """
        if not self.available:
            raise ZhihuUnavailable("zhihu-cli 不可用")

        timeout = settings.zhihu_timeout_seconds
        cmd = [self._cli, *args, "--timeout", f"{int(timeout)}s"]
        t0 = time.perf_counter()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout + 4)
        except asyncio.TimeoutError as exc:
            _log(stage, t0, ok=False, err="timeout")
            raise ZhihuUnavailable(f"{stage} 超时") from exc
        except Exception as exc:
            _log(stage, t0, ok=False, err=type(exc).__name__)
            raise ZhihuUnavailable(f"{stage} 执行失败：{type(exc).__name__}") from exc

        if proc.returncode != 0:
            # stderr 可能含诊断信息，只记录类型，不外泄给用户
            _log(stage, t0, ok=False, err=f"exit={proc.returncode}")
            raise ZhihuUnavailable(f"{stage} 返回非零退出码")

        try:
            data = json.loads(out.decode("utf-8", "replace"))
        except json.JSONDecodeError as exc:
            _log(stage, t0, ok=False, err="bad_json")
            raise ZhihuUnavailable(f"{stage} 返回无法解析") from exc

        if data.get("Code") not in (0, None):
            _log(stage, t0, ok=False, err=f"code={data.get('Code')}")
            raise ZhihuUnavailable(f"{stage} 业务错误 Code={data.get('Code')}")

        _log(stage, t0, ok=True)
        return data

    # ------------------------------------------------------------------
    # 问题推荐
    # ------------------------------------------------------------------

    async def recommend_questions(self, queries: list[str]) -> list[ZhihuQuestion]:
        """按主题推荐问题。

        注意：不假设 question recommend 能用 OAuth 身份做 server-side
        personalization —— 该能力未验证。个性化来自我们自己传入的 queries。
        """
        seen: set[str] = set()
        result: list[ZhihuQuestion] = []

        for q in queries[:4]:
            q = q.strip()
            if not q:
                continue
            try:
                data = await self._run(
                    ["question", "recommend", "--query", q, "--count", "5"],
                    stage="recommend",
                )
            except ZhihuUnavailable as exc:
                logger.warning("recommend(%s) 失败：%s", q, exc)
                continue

            for item in (data.get("Data") or {}).get("Items") or []:
                title = (item.get("Title") or "").strip()
                url = (item.get("Url") or "").strip()
                if not title or not url:
                    continue
                zq = ZhihuQuestion(title=title, url=url)
                key = zq.question_id or url
                if key in seen:
                    continue
                seen.add(key)
                result.append(zq)

        return result

    # ------------------------------------------------------------------
    # 社区观点：search zhihu 为主来源
    # ------------------------------------------------------------------

    async def search_answers(self, question_title: str, count: int = 10) -> list[ZhihuAnswer]:
        """搜索与问题相关的真实回答。

        Audit 结论：search zhihu 能提供 AuthorName / Badge / AuthorityLevel /
        ContentText / Url，所以作为 Perspective 的主来源。
        """
        data = await self._run(
            ["search", "zhihu", "--query", question_title[:80], "--count", str(min(count, 10))],
            stage="search",
        )
        return _parse_answers(data)

    async def get_answer_summaries(
        self, question_url: str, limit: int = 10
    ) -> list[ZhihuAnswer]:
        """按问题 URL 取回答摘要。

        辅助来源：question_answers quota 只有 100，只在明确需要时调用。
        """
        data = await self._run(
            [
                "question",
                "answers",
                "--question-url",
                question_url,
                "--limit",
                str(min(limit, 20)),
            ],
            stage="answers",
        )
        return _parse_answers(data)

    # ------------------------------------------------------------------
    # 身份边界（重要）
    #
    # 此处曾提供 me_followees / me_favorite_titles / me_content_titles，
    # 它们读取的是「Access Secret 所属账号本人」（即开发者）的知乎数据。
    # 这类「当前账号本人」命令绝不能进入任何面向访客的用户身份路径 ——
    # 未 OAuth 的访客会因此看到开发者的知乎数据。
    #
    # 现已移除。若要读「当前访问 MindMine 的用户」数据，只能走
    # services/zhihu_oauth.py 的 OAuth 授权（X-OAuth-Token），
    # 与这里的平台搜索能力（search / recommend / answers）彻底分开。
    # ------------------------------------------------------------------


def _parse_answers(data: dict) -> list[ZhihuAnswer]:
    """兼容 Data 为 list 或 {Items: [...]} 两种返回形态。"""
    raw = data.get("Data")
    items = raw if isinstance(raw, list) else (raw or {}).get("Items") or []

    out: list[ZhihuAnswer] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        out.append(
            ZhihuAnswer(
                title=(it.get("Title") or "").strip(),
                author_name=(it.get("AuthorName") or "").strip(),
                content_text=(it.get("ContentText") or it.get("Summary") or "").strip(),
                url=(it.get("Url") or "").strip(),
                badge=(it.get("Badge") or "").strip(),
                authority_level=str(it.get("AuthorityLevel") or "").strip(),
            )
        )
    return out


def dedup_by_author(answers: list[ZhihuAnswer], max_per_author: int = 1) -> list[ZhihuAnswer]:
    """按作者去重。

    Audit 已发现同一结果集可能大量来自同一作者，
    所以这是必须项：观点多样性 > 同一作者多个回答。

    不使用 VoteUpCount 排序 —— 该字段已验证可能为空/不可靠。
    """
    count: dict[str, int] = {}
    out: list[ZhihuAnswer] = []
    for a in answers:
        key = a.author_name or a.url
        if count.get(key, 0) >= max_per_author:
            continue
        count[key] = count.get(key, 0) + 1
        out.append(a)
    return out


def _log(stage: str, t0: float, *, ok: bool, err: str = "") -> None:
    """记录 provider/latency/成败。绝不记录 Access Secret。"""
    if not settings.verbose_provider_log:
        return
    ms = int((time.perf_counter() - t0) * 1000)
    if ok:
        logger.info("zhihu stage=%s provider=real latency=%dms ok", stage, ms)
    else:
        logger.warning(
            "zhihu stage=%s provider=real latency=%dms failed=%s", stage, ms, err
        )


zhihu = ZhihuService()
