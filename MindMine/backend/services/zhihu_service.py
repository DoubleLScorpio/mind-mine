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
        self._cli = settings.zhihu_cli_path

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
    # 当前账号自己的数据（Phase D）
    #
    # 只读取生成画像所需的最小范围。user_data quota 10000，
    # 但仍然优先 followees + favorites，不无节制拉取。
    # ------------------------------------------------------------------

    async def me_followees(self, limit: int = 20) -> list[str]:
        """我关注的人。用他们的领域反推「我常待在哪」。"""
        data = await self._run(
            ["me", "followees", "--limit", str(min(limit, 50))], stage="followees"
        )
        out: list[str] = []
        for it in (data.get("Data") or {}).get("Items") or []:
            name = (it.get("Fullname") or "").strip()
            headline = (it.get("Headline") or "").strip()
            if name:
                out.append(f"{name}：{headline}" if headline else name)
        return out

    async def me_favorite_titles(self, limit: int = 20) -> list[str]:
        """我的收藏夹标题。这是「我反复关心什么」的最强信号。"""
        data = await self._run(
            ["me", "favorites", "lists", "--limit", str(min(limit, 50))],
            stage="favorites",
        )
        out: list[str] = []
        for it in (data.get("Data") or {}).get("Items") or []:
            title = (it.get("Title") or "").strip()
            if title and title != "我的收藏":
                out.append(title)
        return out

    async def me_content_titles(self, limit: int = 20) -> list[str]:
        """我自己写过的东西。已经写出来的，说明我真的有话说。"""
        data = await self._run(
            ["me", "contents", "--limit", str(min(limit, 50))], stage="contents"
        )
        out: list[str] = []
        for it in (data.get("Data") or {}).get("Items") or []:
            title = (it.get("Title") or it.get("Summary") or "").strip()
            if title:
                out.append(title[:60])
        return out


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
