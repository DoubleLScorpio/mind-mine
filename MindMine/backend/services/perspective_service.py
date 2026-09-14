"""社区视角获取：把真实知乎回答转成「别人会怎么追问你」。

Pipeline（依据 Capability Audit）：
    当前知乎问题
      ↓ search zhihu（主来源：有 AuthorName/Badge/AuthorityLevel/ContentText/Url）
      ↓ 按 URL 中的 question id 过滤属于目标问题的回答
      ↓ author dedup（必须项：观点多样性 > 同一作者多条）
      ↓ evidence extraction
      ↓ perspective extraction（LLM 改写成追问）
      ↓ 与用户 Insight 比较，选最有价值的另一种视角
    Community Question

两条硬约束：
1. Grounding —— 追问必须能追溯到真实回答（claim / evidence / author / url / qid）。
   LLM 只能把真实观点改写成追问，不能凭空创造「知乎网友认为……」。
2. 没有真正相反的观点时，不硬造 opposition，
   降级为「还有一个角度，也许值得你再看一眼」。
"""

from __future__ import annotations

import logging

from ai import prompts
from ai.schemas import PerspectiveOut
from models.session import CommunityPerspective
from services import demo_content
from services.llm_service import LLMUnavailable, llm
from services.zhihu_service import (
    ZhihuAnswer,
    ZhihuUnavailable,
    dedup_by_author,
    zhihu,
)

logger = logging.getLogger("mindmine.perspective")

# 摘要太短的没有观点可言
_MIN_CONTENT = 40


def _pick_candidates(
    answers: list[ZhihuAnswer], question_id: str, limit: int = 4
) -> list[ZhihuAnswer]:
    """过滤 + 去重 + 选候选。

    question_id 命中的优先（确实是这道题下的回答），
    但 search zhihu 是全站搜索，命中不到也允许作为相关视角使用。
    """
    usable = [a for a in answers if len(a.content_text) >= _MIN_CONTENT]

    same_q = [a for a in usable if question_id and a.question_id == question_id]
    others = [a for a in usable if not (question_id and a.question_id == question_id)]

    # 作者去重是必须项 —— audit 已发现同一作者可能占满结果集
    ordered = dedup_by_author(same_q, max_per_author=1) + dedup_by_author(
        others, max_per_author=1
    )

    # 不用 VoteUpCount 排序（字段不可靠）。
    # 用 AuthorityLevel / Badge 作为辅助信号，其余保持相关性顺序。
    def signal(a: ZhihuAnswer) -> int:
        s = 0
        if a.authority_level:
            s += 1
        if a.badge:
            s += 1
        return -s

    ordered.sort(key=signal)
    return ordered[:limit]


def _lead_sentence(text: str, limit: int = 70) -> str:
    """取开头一到两句，避免把整段原文糊到界面上。

    无 LLM 时也要保证追问读起来像一句话，而不是一坨摘要。
    """
    clean = " ".join(text.split())
    for i, ch in enumerate(clean):
        if ch in "。！？!?" and i >= 18:
            return clean[: i + 1]
    return clean[:limit] + ("…" if len(clean) > limit else "")


async def _to_question(
    answer: ZhihuAnswer, user_insight: str, question_title: str
) -> tuple[str, str, bool, bool]:
    """把一条真实回答改写成对用户的追问。

    返回 (claim, challenge_question, is_opposing, used_real)。
    无 LLM 时退回「原文首句 + 中性引导」：内容仍来自真实回答，
    但 used_real=False，调用方必须据此标记 mock_fallback。
    """
    snippet = answer.content_text[:280]
    lead = _lead_sentence(answer.content_text)

    if not llm.available:
        # 没有模型也要保持 grounding：claim 用原文首句，追问用中性引导
        logger.info("perspective stage=rewrite provider=mock fallback=True reason=llm_unavailable")
        return (
            lead,
            f"有人是这么看的：「{lead}」\n如果照这个说法，你那句判断还成立吗？",
            False,
            False,
        )

    try:
        out: PerspectiveOut = await llm.generate_structured(
            system=(
                f"{prompts.PHILOSOPHY}\n\n"
                "你的任务：把一条真实的知乎回答，改写成「这个人站在用户的判断面前会问的一句话」。\n\n"
                "输出：\n"
                "- claim：这条回答的核心主张，一句话，必须忠于原文，不得加入原文没有的意思。\n"
                "- challenge_question：站在用户判断面前会问出的话，1-2 句，口语，不超过 70 字。\n"
                "  要像一个真人在追问，不是辩论稿，不要说「我反对」。\n"
                "- is_opposing：这条回答是否真的与用户判断不同。\n"
                "  如果只是补充或角度不同，填 false —— 不要硬造对立。\n\n"
                "禁止虚构原文中不存在的观点。"
            ),
            user=(
                f"知乎问题：{question_title}\n\n"
                f"用户自己的判断：\n{user_insight}\n\n"
                f"一条真实回答的摘要（作者：{answer.author_name or '匿名'}）：\n{snippet}"
            ),
            schema=PerspectiveOut,
            temperature=0.6,
            max_tokens=400,
            stage="perspective",
        )
        return (
            out.claim.strip() or snippet[:120],
            out.challenge_question.strip(),
            bool(out.is_opposing),
            True,
        )
    except LLMUnavailable as exc:
        logger.warning(
            "perspective stage=rewrite provider=mock fallback=True reason=%s", exc
        )
        return (
            snippet[:120],
            f"有人是这么看的：「{snippet[:110]}」\n如果照这个说法，你那句判断还成立吗？",
            False,
            False,
        )


async def fetch_perspective(
    question_title: str,
    question_id: str,
    user_insight: str,
) -> tuple[CommunityPerspective, bool]:
    """获取一个社区视角。返回 (perspective, used_real)。

    任何环节失败都退回 Demo 数据 —— 而且「直接写成答案」始终可用，
    所以即使这里完全拿不到东西，用户也不会被卡住。
    """
    if not zhihu.available:
        logger.info("perspective provider=mock fallback=True reason=cli_unavailable")
        return demo_content.DEMO_CHALLENGE.model_copy(deep=True), False

    try:
        answers = await zhihu.search_answers(question_title, count=10)
    except ZhihuUnavailable as exc:
        logger.warning("perspective fallback: %s", exc)
        return demo_content.DEMO_CHALLENGE.model_copy(deep=True), False

    candidates = _pick_candidates(answers, question_id)
    if not candidates:
        logger.info("perspective provider=mock fallback=True reason=no_candidate")
        return demo_content.DEMO_CHALLENGE.model_copy(deep=True), False

    # 优先选真正构成不同视角的那条
    best: tuple[ZhihuAnswer, str, str, bool, bool] | None = None
    for a in candidates[:3]:
        claim, cq, opposing, rewrite_real = await _to_question(
            a, user_insight, question_title
        )
        if not cq:
            continue
        if opposing:
            best = (a, claim, cq, True, rewrite_real)
            break
        if best is None:
            best = (a, claim, cq, False, rewrite_real)

    if best is None:
        logger.info("perspective provider=mock fallback=True reason=no_rewrite")
        return demo_content.DEMO_CHALLENGE.model_copy(deep=True), False

    answer, claim, cq, opposing, rewrite_real = best
    author = answer.author_name or "知乎用户"

    # 来源关系必须如实反映：绝不能把相关问题伪装成「这个问题下的回答」
    same_q = bool(question_id) and answer.question_id == question_id
    relation = "same_question" if same_q else "related_question"
    source_label = (
        f"这个问题下 · {author}" if same_q else f"知乎相关问题 · {author}"
    )

    logger.info(
        "perspective provider=real fallback=%s relation=%s opposing=%s "
        "rewrite=%s author_dedup=%d/%d",
        not rewrite_real,
        relation,
        opposing,
        "real" if rewrite_real else "mock",
        len(candidates),
        len(answers),
    )

    return (
        CommunityPerspective(
            id=f"zhihu_{answer.question_id or 'x'}_{abs(hash(answer.url)) % 10**8}",
            claim=claim,
            # evidence snippet：保留原文片段，保证可追溯
            reason=answer.content_text[:160],
            author=author,
            badge=answer.badge or answer.authority_level or "",
            # 真实模式显示轻量来源，不抢走用户观点的中心地位
            source_label=source_label,
            source_url=answer.url or None,
            challenge_question=cq,
            is_mock=False,
            source_relation=relation,
            source_question_id=answer.question_id or "",
        ),
        # 检索是真的，但改写退回模板时整体不算 real
        rewrite_real,
    )
