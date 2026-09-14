"""真实画像提取：从知乎 OAuth 用户足迹里找「这个人有什么值得知乎听」。

目标不是描述人口属性，而是发现：
    这个人可能拥有、但还没有写出来的知识。

链路：
    OAuth 授权用户数据（followees / favorites / contents）
      ↓ ProfileEvidence（真实痕迹，is_mock=False）
      ↓ ProfileExtractor（LLM）
    ContributionProfile → MindPortrait

重要：本模块不再读取 Access Secret 所属账号（开发者本人）的数据。
只有拿到 OAuth access_token（X-OAuth-Token）后，才读取「当前授权用户」
的公开数据；任何环节失败都回退到「先聊两句」，绝不回退到开发者账号。
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
from services.zhihu_oauth import ZhihuOAuthUser

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
    """【已废弃】不再读取 Access Secret 所属账号（开发者本人）的数据。

    保留该函数名仅为兼容旧导入；现在一律返回空 + False，
    表示「没有当前用户的真实足迹」。OAuth 路径改走 build_portrait_from_user()。
    """
    logger.warning("profile fetch_traces() called — developer identity read is removed")
    return [], False


def evidence_from_user(user: ZhihuOAuthUser) -> list[ProfileEvidence]:
    """从「当前 OAuth 授权用户」的原始数据构建真实痕迹。

    只使用本次授权拿到的数据，绝不混入开发者账号数据。
    """
    return _evidence_from(user.followees, user.favorites, user.contents)


async def build_portrait_from_user(
    user: ZhihuOAuthUser,
) -> tuple[ContributionProfile, MindPortrait, bool] | None:
    """从 OAuth 用户数据生成画像。失败返回 None，调用方 fallback 到「先聊两句」。"""
    evidence = evidence_from_user(user)
    if not evidence:
        logger.warning("oauth portrait no_evidence")
        return None

    built = await build_portrait(evidence)
    if built is not None:
        return built

    # LLM 失败：仍用真实 OAuth 足迹兜底，绝不退回 demo persona
    salvaged = portrait_from_evidence(evidence)
    if salvaged is None:
        return None
    profile, portrait = salvaged
    logger.info("oauth portrait fallback=evidence")
    return profile, portrait, False


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


def portrait_from_evidence(
    evidence: list[ProfileEvidence],
) -> tuple[ContributionProfile, MindPortrait] | None:
    """真实足迹已拿到、但 LLM 失败时的兜底。

    仍然只使用真实足迹里的词，绝不退回与这个人无关的 demo persona。
    调用方必须把 _source 标记为 mock_fallback。
    """
    if not evidence:
        return None

    follows = next((e.items for e in evidence if e.kind == "follow"), [])
    favs = next((e.items for e in evidence if e.kind == "favorite"), [])
    creations = next((e.items for e in evidence if e.kind == "creation"), [])

    angles = [x.strip() for x in (favs + creations) if x.strip()][:4]
    if not angles:
        angles = [x.strip() for x in follows if x.strip()][:4]
    if not angles:
        return None

    profile = ContributionProfile(
        source="oauth",
        journey="正在关注这些方向的人",
        lived_experiences=[x for x in creations if x][:5],
        recurring_interests=[x for x in favs if x][:5],
        possible_knowledge=["自己真实经历过、别人替代不了的部分"],
        contribution_angles=angles,
        evidence=evidence,
    )
    portrait = MindPortrait(
        lead="从你留下的这些痕迹里，我好像看到这样一个你。",
        paragraphs=[
            "你反复停留的地方，大致集中在这几件事上。",
            "这些痕迹是真的，但我这次没能把它们读得更深——"
            "你可以直接告诉我，哪里不像。",
        ],
        topics=angles,
        core_lead="而你真正值得写下来的，可能不是某个知识点。",
        core_line="是那些——「做过之后才知道」的东西。",
    )
    logger.info("profile stage=portrait provider=mock fallback=True source=evidence")
    return profile, portrait
