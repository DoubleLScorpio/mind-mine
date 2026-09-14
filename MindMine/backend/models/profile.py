"""Onboarding 阶段的数据模型。

产品原则（AGENTS.md）：
  MindMine 不要求用户定义自己。
  MindMine 尝试理解用户，然后把解释权交还给用户。

因此这里的模型不是人口统计分类器。它的任务是回答一个问题：
  「这个人有什么东西，值得知乎听。」

字段权重：possible_knowledge 与 contribution_angles 最高，
它们最终决定我们去帮用户找什么问题。journey / lived_experiences
只是支撑它们的依据。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# 认识用户的「痕迹」
# --------------------------------------------------------------------------


class ProfileEvidence(BaseModel):
    """MindMine 认识这个人所依据的痕迹。

    Phase 1 全部是演示数据；接入 OAuth 后来自
    followees / favorites / creations。
    is_mock 为 True 时，前端必须明确标注，不得伪装成真实知乎账户数据。
    """

    kind: Literal["follow", "favorite", "creation", "said"]
    label: str
    items: list[str] = Field(default_factory=list)
    is_mock: bool = True


# --------------------------------------------------------------------------
# 贡献画像
# --------------------------------------------------------------------------


class ContributionProfile(BaseModel):
    """不是「这个人是谁」，而是「这个人有什么值得写下来」。

    界面上永远不出现本模型的字段名。它只通过 MindPortrait
    的自然语言描述与用户见面。
    """

    # chat_llm：「先聊两句」路径由 LLM 生成
    # chat_mock：chat 路径 LLM 失败后的关键词 fallback
    source: Literal["mock_zhihu", "mock_chat", "oauth", "chat_llm", "chat_mock"] = "mock_zhihu"

    # 你在走什么路
    journey: str = ""
    # 你真正经历过什么
    lived_experiences: list[str] = Field(default_factory=list)
    # 反复出现的关注
    recurring_interests: list[str] = Field(default_factory=list)
    # 你可能有什么「只有经历过才知道」的东西（高权重）
    possible_knowledge: list[str] = Field(default_factory=list)
    # 可以从哪个角度贡献（高权重）
    contribution_angles: list[str] = Field(default_factory=list)

    evidence: list[ProfileEvidence] = Field(default_factory=list)
    # 用户用自然语言纠正过几次
    correction_count: int = 0


# --------------------------------------------------------------------------
# 我眼中的你
# --------------------------------------------------------------------------


class MindPortrait(BaseModel):
    """「我好像看到这样一个你。」

    这是 ContributionProfile 面向用户的那一层，全部是自然语言。
    语气必须保持不确定：我好像看到 / 你似乎 / 可能 / 也许 ——
    因为这是 AI 的理解，不是事实裁决。
    """

    lead: str
    # 人物描述，逐段浮现
    paragraphs: list[str] = Field(default_factory=list)
    # 「你似乎特别容易对这些事情有话说」
    topics: list[str] = Field(default_factory=list)
    # 视觉权重最高的那一段：做过之后才知道的东西
    core_lead: str = ""
    core_line: str = ""
    # 纠正之后的开场白（「明白了。」）
    ack: str | None = None


class OnboardingState(BaseModel):
    """一次 Onboarding 的完整结果。前端不关心画像来自 Mock / OAuth / LLM。"""

    onboarding_id: str
    profile: ContributionProfile
    portrait: MindPortrait


# --------------------------------------------------------------------------
# 为什么是你
# --------------------------------------------------------------------------


class QuestionMatchReason(BaseModel):
    """问题与这个人之间的因果关系。

    必须引用 MindPortrait 里真实存在的信息，
    不得展示 Match Score / 推荐算法解释 / 多个 Badge。
    """

    # 「你刚才告诉我，……」
    from_you: str
    # 「而真正让你有话说的，往往是……」
    therefore: str


class MatchedQuestion(BaseModel):
    question_id: str
    title: str
    reason: QuestionMatchReason
    url: str | None = None
    source: Literal["mock", "api"] = "mock"


# --------------------------------------------------------------------------
# 请求体
# --------------------------------------------------------------------------


class ChatAnswerRequest(BaseModel):
    """「先聊两句」路径：用户对第 step 个问题的回答。"""

    step: int
    content: str
    # 之前几轮的回答，用于生成画像
    history: list[str] = Field(default_factory=list)


class CorrectionRequest(BaseModel):
    """自然语言纠正。不是字段编辑，是用户直接说哪里不像。"""

    onboarding_id: str
    content: str
