"""真实画像提取：从知乎足迹里找「这个人有什么值得知乎听」。

目标不是描述人口属性，而是发现：
    这个人可能拥有、但还没有写出来的知识。

链路：
    me followees / favorites / contents
      ↓ ProfileEvidence（真实痕迹，is_mock=False）
      ↓ ProfileExtractor（LLM）
    ContributionProfile → MindPortrait

任何环节失败 → MockProfileService，「先聊两句」永远可用。
OAuth 是增强路径，不是 MindMine 能否工作的前提。
"""

from __future__ import annotations

import logging

from ai import prompts
from models.profile import (
    ContributionProfile,
    MindPortrait,
    ProfileEvidence,
)
from pydantic import BaseModel, Field
from services.llm_service import LLMUnavailable, llm
from services.zhihu_service import ZhihuUnavailable, zhihu

logger = logging.getLogger("mindmine.profile")


class PortraitOut(BaseModel):
    """ProfileExtractor 的结构化输出。

    字段对应 ContributionProfile + MindPortrait 的自然语言层。
    possible_knowledge / contribution_angles 权重最高。
    """

    journey: str
    lived_experiences: list[str] = Field(default_factory=list)
    recurring_interests: list[str] = Field(default_factory=list)
    possible_knowledge: list[str] = Field(default_factory=list)
    contribution_angles: list[str] = Field(default_factory=list)
    # 面向用户的自然语言描述，2 段
    paragraphs: list[str] = Field(default_factory=list)


EXTRACTOR_SYSTEM = f"""{prompts.PHILOSOPHY}

你现在的角色：从一个人的知乎足迹里，看出他可能有什么值得写出来的东西。

重要：你的任务不是给他贴标签、不是做人口统计分类。
是回答一个问题 —— 这个人有什么东西，值得知乎听。

输出字段（权重从低到高）：
- journey：他正在走的路。一句话，第三人称描述，不超过 25 字。
- lived_experiences：他真正待过的领域，3-5 个短词。
- recurring_interests：反复出现的关注，3-5 个短词。
- possible_knowledge：**最重要**。他可能有、但还没写出来的知识。
  必须是「只有经历过才知道」那一类，不是「懂某个技术」。
  例如「转行时真实的机会成本判断」而不是「Python」。2-4 条。
- contribution_angles：**最重要**。他可以从哪些角度贡献。3-4 个短词。
- paragraphs：面向他本人的自然语言描述，恰好 2 段。
  第二人称「你」。语气必须不确定：好像 / 似乎 / 可能。
  不要下定义、不要评价、不要表扬。每段不超过 50 字。

只能基于给出的足迹推断。看不出来的不要编。"""


def _evidence_from(
    followees: list[str], favorites: list[str], contents: list[str]
) -> list[ProfileEvidence]:
    """真实痕迹。is_mock=False，前端据此显示真实来源。"""
    out: list[ProfileEvidence] = []
    if followees:
        out.append(
            ProfileEvidence(
                kind="follow",
                label="你关注的人里，反复出现这些名字……",
                items=[f.split("：")[0] for f in followees[:6]],
                is_mock=False,
            )
        )
    if favorites:
        out.append(
            ProfileEvidence(
                kind="favorite",
                label="你收藏夹的名字，其实很说明问题……",
                items=favorites[:6],
                is_mock=False,
            )
        )
    if contents:
        out.append(
            ProfileEvidence(
                kind="creation",
                label="你自己写过的东西里……",
                items=[c[:24] for c in contents[:4]],
                is_mock=False,
            )
        )
    return out


async def fetch_traces() -> tuple[list[ProfileEvidence], bool]:
    """拉取真实足迹。返回 (evidence, used_real)。"""
    if not zhihu.available:
        return [], False
    try:
        followees = await zhihu.me_followees(12)
        favorites = await zhihu.me_favorite_titles(12)
        contents = await zhihu.me_content_titles(8)
    except ZhihuUnavailable as exc:
        logger.warning("traces fallback: %s", exc)
        return [], False

    ev = _evidence_from(followees, favorites, contents)
    if not ev:
        return [], False
    logger.info("profile stage=traces provider=real fallback=False groups=%d", len(ev))
    return ev, True


async def build_portrait(
    evidence: list[ProfileEvidence],
) -> tuple[ContributionProfile, MindPortrait, bool] | None:
    """从真实足迹生成画像。失败返回 None，由调用方 fallback 到 Mock。"""
    if not evidence or not llm.available:
        return None

    digest = "\n".join(
        f"{e.label}\n  " + "、".join(e.items) for e in evidence
    )

    try:
        out: PortraitOut = await llm.generate_structured(
            system=EXTRACTOR_SYSTEM,
            user=f"这个人的知乎足迹：\n\n{digest}",
            schema=PortraitOut,
            temperature=0.6,
            max_tokens=900,
            stage="portrait",
        )
    except LLMUnavailable as exc:
        logger.warning("portrait fallback: %s", exc)
        return None

    angles = [a.strip() for a in out.contribution_angles if a.strip()][:4]
    paragraphs = [p.strip() for p in out.paragraphs if p.strip()][:2]
    if not paragraphs or not angles:
        return None

    profile = ContributionProfile(
        source="oauth",
        journey=out.journey.strip(),
        lived_experiences=[x.strip() for x in out.lived_experiences if x.strip()][:5],
        recurring_interests=[x.strip() for x in out.recurring_interests if x.strip()][:5],
        possible_knowledge=[x.strip() for x in out.possible_knowledge if x.strip()][:4],
        contribution_angles=angles,
        evidence=evidence,
    )

    portrait = MindPortrait(
        lead="从你留下的这些痕迹里，我好像看到这样一个你。",
        paragraphs=paragraphs,
        topics=angles,
        core_lead="而你真正值得写下来的，可能不是某个知识点。",
        core_line="是那些——「做过之后才知道」的东西。",
    )

    logger.info("profile stage=portrait provider=real fallback=False")
    return profile, portrait, True
