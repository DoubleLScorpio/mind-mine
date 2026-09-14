"""AI 引擎：真实 LLM 实现 + Demo fallback。

每个能力都是 `真实优先 → 失败退回 Mock` 的结构，
所以 Demo 永远不会因为模型不可用而卡死。

调用方（session_store / routers）只看到这里的函数，
不关心背后是 LLM 还是固定脚本。
"""

from __future__ import annotations

import logging

from ai import prompts
from ai.schemas import ExtractionOut, InsightOut, RefineOut
from config import settings
from models.session import (
    FragmentLink,
    Insight,
    KnowledgeEvent,
    KnowledgeState,
    Session,
    ThoughtFragment,
)
from services import demo_content
from services.llm_service import LLMUnavailable, llm

logger = logging.getLogger("mindmine.ai")


# --------------------------------------------------------------------------
# 上下文摘要
# --------------------------------------------------------------------------


def knowledge_digest(ks: KnowledgeState) -> str:
    """把内部 KnowledgeState 压成给模型看的纯文本。"""
    parts: list[str] = []
    if ks.facts:
        parts.append("事实：" + "；".join(ks.facts))
    if ks.events:
        parts.append(
            "事件：" + "；".join(f"{e.event} → {e.result}" for e in ks.events)
        )
    if ks.beliefs:
        parts.append("当时的判断：" + "；".join(ks.beliefs))
    if ks.conflicts:
        parts.append("冲突：" + "；".join(ks.conflicts))
    if ks.reflections:
        parts.append("反思：" + "；".join(ks.reflections))
    if ks.candidate_insights:
        parts.append("可能的判断：" + "；".join(ks.candidate_insights))
    return "\n".join(parts)


def transcript(session: Session) -> str:
    """用户原话，按顺序。这是成文时唯一的事实来源。"""
    lines = [
        f"{i + 1}. {m.content}"
        for i, m in enumerate([m for m in session.messages if m.role == "user"])
    ]
    return "\n".join(lines)


def _log(stage: str, provider: str, fallback: bool, session_id: str = "-") -> None:
    if not settings.verbose_provider_log:
        return
    logger.info(
        "ai session=%s stage=%s provider=%s fallback=%s",
        session_id,
        stage,
        provider,
        fallback,
    )


# --------------------------------------------------------------------------
# Interview Engine —— 生成下一个追问
# --------------------------------------------------------------------------


async def next_question(session: Session, last_answer: str) -> tuple[str | None, bool]:
    """返回 (追问, 用了真实 LLM)。

    追问为 None 表示信息够了，该进入 Insight。
    """
    if not llm.available:
        return _mock_next_question(session), False

    try:
        text = await llm.generate(
            system=prompts.INTERVIEW_SYSTEM,
            user=prompts.interview_user_prompt(
                question_title=session.question.title if session.question else "",
                stage=session.state.value,
                turn=session.user_turn_count,
                knowledge_digest=knowledge_digest(session.knowledge_state),
                last_answer=last_answer,
            ),
            temperature=0.8,
            max_tokens=120,
            stage="interview",
        )
        _log("interview", "real", False, session.id)
        # 模型偶尔会加引号或前缀，清掉
        return text.strip().strip('「」"\''), True
    except LLMUnavailable as exc:
        logger.warning("interview fallback: %s", exc)
        _log("interview", "mock", True, session.id)
        return _mock_next_question(session), False


def _mock_next_question(session: Session) -> str | None:
    idx = session.user_turn_count - 1
    if 0 <= idx < len(demo_content.INTERVIEW_SCRIPT):
        return demo_content.INTERVIEW_SCRIPT[idx].get("next_question")
    return None


# --------------------------------------------------------------------------
# Knowledge Extractor —— 抽取碎片与内部知识
# --------------------------------------------------------------------------


async def extract(session: Session, answer: str) -> tuple[ExtractionOut | None, bool]:
    """抽取本轮新增信息。返回 (结果, 用了真实 LLM)。"""
    if not llm.available:
        return None, False

    try:
        out = await llm.generate_structured(
            system=prompts.EXTRACTOR_SYSTEM,
            user=prompts.extractor_user_prompt(
                question_title=session.question.title if session.question else "",
                existing=knowledge_digest(session.knowledge_state),
                answer=answer,
            ),
            schema=ExtractionOut,
            temperature=0.3,
            max_tokens=800,
            stage="extract",
        )
        _log("extract", "real", False, session.id)
        return out, True
    except LLMUnavailable as exc:
        logger.warning("extract fallback: %s", exc)
        _log("extract", "mock", True, session.id)
        return None, False


def apply_extraction(session: Session, out: ExtractionOut) -> None:
    """把抽取结果落进会话。

    碎片 id 由后端生成，保证前端 FLIP 动画能稳定追踪同一个节点。
    """
    ks = session.knowledge_state
    ks.facts.extend(out.facts)
    ks.events.extend(KnowledgeEvent(event=e.event, result=e.result) for e in out.events)
    ks.beliefs.extend(out.beliefs)
    ks.conflicts.extend(out.conflicts)
    ks.reflections.extend(out.reflections)
    ks.candidate_insights.extend(out.candidate_insights)

    source_id = f"m_{session.user_turn_count}"
    for i, f in enumerate(out.fragments):
        text = f.text.strip()
        if not text:
            continue
        # 同一句话不重复钉两次
        if any(existing.text == text for existing in session.fragments):
            continue
        session.fragments.append(
            ThoughtFragment(
                id=f"f_{session.user_turn_count}_{i}",
                label=(f.label or "").strip() or None,
                text=text,
                source_message_id=source_id,
            )
        )

    _relink(session)


def _relink(session: Session) -> None:
    """按讲述顺序把碎片连成一条经历链。

    真实模式下碎片 id 是动态的，所以关系只能来自顺序 ——
    这本身也来自用户的讲述，不是 AI 额外推断的东西。
    """
    ids = [f.id for f in session.fragments]
    session.fragment_links = [
        FragmentLink(from_id=a, to_id=b) for a, b in zip(ids, ids[1:])
    ]


# --------------------------------------------------------------------------
# Insight Extractor
# --------------------------------------------------------------------------


async def make_insight(session: Session) -> tuple[Insight, bool]:
    """凝结出属于用户的判断。返回 (Insight, 用了真实 LLM)。"""
    first_said = next(
        (m.content for m in session.messages if m.role == "user"), ""
    )

    if not llm.available:
        _log("insight", "mock", True, session.id)
        return demo_content.DEMO_INSIGHT_V1.model_copy(deep=True), False

    try:
        out: InsightOut = await llm.generate_structured(
            system=prompts.INSIGHT_SYSTEM,
            user=prompts.insight_user_prompt(
                question_title=session.question.title if session.question else "",
                knowledge_digest=knowledge_digest(session.knowledge_state),
                transcript=transcript(session),
            ),
            schema=InsightOut,
            temperature=0.5,
            max_tokens=500,
            stage="insight",
        )
        _log("insight", "real", False, session.id)
        return (
            Insight(
                version="V1",
                surface_claim=first_said,
                naming=out.experience_summary.strip(),
                deep_insight=out.insight.strip(),
            ),
            True,
        )
    except LLMUnavailable as exc:
        logger.warning("insight fallback: %s", exc)
        _log("insight", "mock", True, session.id)
        return demo_content.DEMO_INSIGHT_V1.model_copy(deep=True), False


# --------------------------------------------------------------------------
# Insight Refiner
# --------------------------------------------------------------------------


async def refine_insight(
    session: Session, user_response: str
) -> tuple[Insight, bool]:
    """根据用户补充修正判断。不强迫观点升级。"""
    original = session.insight_v1
    original_text = (
        original.user_edited_text or original.deep_insight if original else ""
    )

    if not llm.available:
        _log("refine", "mock", True, session.id)
        return demo_content.DEMO_INSIGHT_V2.model_copy(deep=True), False

    try:
        out: RefineOut = await llm.generate_structured(
            system=prompts.REFINER_SYSTEM,
            user=prompts.refiner_user_prompt(
                original_insight=original_text,
                community_question=(
                    session.challenge.challenge_question if session.challenge else ""
                ),
                user_response=user_response,
            ),
            schema=RefineOut,
            temperature=0.4,
            max_tokens=600,
            stage="refine",
        )
        _log("refine", "real", False, session.id)

        # 只保留在原文/新文中真实出现的片段，
        # 否则前端的「删除线 + 限定词落位」动画会指向不存在的文字
        softened = next(
            (s for s in out.removed_or_softened if s and s in original_text), None
        )
        refined = out.refined_insight.strip() or original_text
        quals = [q for q in out.added_qualifiers if q and q in refined]

        return (
            Insight(
                version="V2",
                surface_claim=original.surface_claim if original else "",
                naming=original.naming if original else None,
                deep_insight=refined,
                softened_span=softened,
                added_qualifiers=quals,
            ),
            True,
        )
    except LLMUnavailable as exc:
        logger.warning("refine fallback: %s", exc)
        _log("refine", "mock", True, session.id)
        return demo_content.DEMO_INSIGHT_V2.model_copy(deep=True), False


# --------------------------------------------------------------------------
# Answer Composer
# --------------------------------------------------------------------------


async def compose_answer(session: Session) -> tuple[str, bool]:
    """写成知乎回答。素材只能来自用户说过的话。"""
    if not llm.available:
        _log("compose", "mock", True, session.id)
        return demo_content.compose_answer(session), False

    final = session.insight_v2 or session.insight_v1
    insight_text = (
        (final.user_edited_text or final.deep_insight) if final else ""
    )

    try:
        text = await llm.generate(
            system=prompts.COMPOSER_SYSTEM,
            user=prompts.composer_user_prompt(
                question_title=session.question.title if session.question else "",
                transcript=transcript(session),
                knowledge_digest=knowledge_digest(session.knowledge_state),
                insight=insight_text,
                community_question=(
                    session.challenge.challenge_question if session.challenge else ""
                ),
                user_response=session.challenge_response or "",
            ),
            temperature=0.75,
            max_tokens=1800,
            stage="compose",
        )
        _log("compose", "real", False, session.id)
        return text, True
    except LLMUnavailable as exc:
        logger.warning("compose fallback: %s", exc)
        _log("compose", "mock", True, session.id)
        return demo_content.compose_answer(session), False
