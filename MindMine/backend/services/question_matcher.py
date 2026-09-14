"""问题匹配：从贡献画像出发，找可能真的该这个用户回答的问题。

真实链路：
    ContributionProfile
      ↓ 生成 2～4 个主题 query（LLM，失败则用画像字段直接拼）
    question recommend --query
      ↓ 去重 + rerank（推荐结果实测有噪声，必须过滤）
    候选问题
      ↓ match_reason（引用画像里真实存在的信息）
    前端一次展示一个

任一环节失败 → MockQuestionProvider，Demo 不卡死。
"""

from __future__ import annotations

import logging
import re

from ai import prompts
from ai.schemas import MatchReasonOut, TopicQueriesOut
from models.profile import (
    ContributionProfile,
    MatchedQuestion,
    QuestionMatchReason,
)
from services.llm_service import LLMUnavailable, llm
from services.zhihu_service import ZhihuQuestion, ZhihuUnavailable, zhihu

logger = logging.getLogger("mindmine.match")

# 推荐结果里明显与「个人经历型回答」无关的噪声
_NOISE = re.compile(
    r"(股|炒股|交易|彩票|基金|币|房价|书法|游戏厂商|买断制|明星|恋爱|相亲|减肥)"
)


async def topic_queries(profile: ContributionProfile) -> tuple[list[str], bool]:
    """从画像提炼 2～4 个检索主题。返回 (queries, 用了真实 LLM)。"""
    # 画像里本来就有可用的角度，LLM 只是让它更准
    fallback = [
        *profile.contribution_angles[:3],
        *profile.possible_knowledge[:1],
    ]
    fallback = [q for q in fallback if q.strip()][:4]

    if not llm.available:
        return fallback, False

    try:
        out: TopicQueriesOut = await llm.generate_structured(
            system=(
                f"{prompts.PHILOSOPHY}\n\n"
                "你的任务：把用户的贡献画像，转成 2-4 个用于检索知乎问题的主题词。\n"
                "要求：每个 2-8 个字；偏向「个人经历能回答」的主题；\n"
                "不要泛化成「职场」「技术」这种大词；不要包含投资、炒股、娱乐等无关领域。"
            ),
            user=(
                f"这个人正在走的路：{profile.journey}\n"
                f"真正经历过：{'、'.join(profile.lived_experiences)}\n"
                f"可能有的独有知识：{'、'.join(profile.possible_knowledge)}\n"
                f"可以贡献的角度：{'、'.join(profile.contribution_angles)}"
            ),
            schema=TopicQueriesOut,
            temperature=0.4,
            max_tokens=300,
            stage="queries",
        )
        qs = [q.strip() for q in out.queries if q.strip()][:4]
        return (qs or fallback), True
    except LLMUnavailable as exc:
        logger.warning("topic_queries fallback: %s", exc)
        return fallback, False


def rerank(
    questions: list[ZhihuQuestion], profile: ContributionProfile, limit: int = 3
) -> list[ZhihuQuestion]:
    """按「这个人的经历能不能回答」排序。

    不使用热度/VoteUpCount（已验证不可靠），只用文本相关性 + 噪声过滤。
    """
    keys = [
        *profile.contribution_angles,
        *profile.possible_knowledge,
        *profile.recurring_interests,
        *profile.lived_experiences,
    ]
    keys = [k for k in keys if k.strip()]

    scored: list[tuple[int, ZhihuQuestion]] = []
    for q in questions:
        if _NOISE.search(q.title):
            continue
        score = 0
        for k in keys:
            # 关键词整体命中，或其中的二字片段命中
            if k in q.title:
                score += 3
            else:
                for i in range(len(k) - 1):
                    if k[i : i + 2] in q.title:
                        score += 1
                        break
        # 偏好「个人经历型」问法
        if any(w in q.title for w in ["你", "经历", "感受", "体验", "后悔", "建议", "道理", "坑"]):
            score += 2
        if score > 0:
            scored.append((score, q))

    scored.sort(key=lambda x: -x[0])
    return [q for _, q in scored[:limit]]


async def match_reason(
    question_title: str, profile: ContributionProfile
) -> tuple[QuestionMatchReason, bool]:
    """生成「为什么是你？」。必须引用画像里真实存在的信息。"""
    journey = profile.journey or "正在经历一些变化"
    knowledge = (
        profile.possible_knowledge[0]
        if profile.possible_knowledge
        else "做过之后才知道的东西"
    )
    fallback = QuestionMatchReason(
        from_you=f"你刚才告诉我，你{journey}，",
        therefore=f"而且真正让你有话说的，往往是那些「{knowledge}」。",
    )

    if not llm.available:
        return fallback, False

    try:
        out: MatchReasonOut = await llm.generate_structured(
            system=(
                f"{prompts.PHILOSOPHY}\n\n"
                "你的任务：说清楚「为什么这个问题该这个用户来回答」。\n\n"
                "输出两句：\n"
                "- from_you：以「你刚才告诉我，」开头，引用用户画像里真实存在的内容。\n"
                "- therefore：说明他的经历为什么正好是这题需要的。\n\n"
                "硬性要求：\n"
                "- 只能使用画像里给出的信息，不要虚构他的经历。\n"
                "- 禁止出现匹配度、百分比、推荐指数、热门度这类表述。\n"
                "- 每句不超过 40 字，口语，第二人称。"
            ),
            user=(
                f"知乎问题：{question_title}\n\n"
                f"这个人正在走的路：{profile.journey}\n"
                f"真正经历过：{'、'.join(profile.lived_experiences)}\n"
                f"可能有的独有知识：{'、'.join(profile.possible_knowledge)}\n"
                f"可以贡献的角度：{'、'.join(profile.contribution_angles)}"
            ),
            schema=MatchReasonOut,
            temperature=0.6,
            max_tokens=300,
            stage="match_reason",
        )
        return (
            QuestionMatchReason(
                from_you=out.from_you.strip() or fallback.from_you,
                therefore=out.therefore.strip() or fallback.therefore,
            ),
            True,
        )
    except LLMUnavailable as exc:
        logger.warning("match_reason fallback: %s", exc)
        return fallback, False


async def find_questions(
    profile: ContributionProfile, mock_fallback: list[MatchedQuestion]
) -> tuple[list[MatchedQuestion], bool]:
    """真实链路找问题。失败返回 Mock，保证 Demo 不卡死。

    返回 (questions, used_real)。
    """
    if not zhihu.available:
        logger.info("match provider=mock fallback=True reason=cli_unavailable")
        return mock_fallback, False

    try:
        queries, _ = await topic_queries(profile)
        if not queries:
            return mock_fallback, False

        candidates = await zhihu.recommend_questions(queries)
        picked = rerank(candidates, profile, limit=3)

        if not picked:
            logger.info("match provider=mock fallback=True reason=no_candidate")
            return mock_fallback, False

        out: list[MatchedQuestion] = []
        for q in picked:
            reason, _ = await match_reason(q.title, profile)
            out.append(
                MatchedQuestion(
                    question_id=q.question_id or q.url,
                    title=q.title,
                    reason=reason,
                    url=q.url,
                    source="api",
                )
            )
        logger.info(
            "match provider=real fallback=False queries=%d picked=%d",
            len(queries),
            len(out),
        )
        return out, True
    except (ZhihuUnavailable, Exception) as exc:
        logger.warning("match fallback: %s", exc)
        return mock_fallback, False
