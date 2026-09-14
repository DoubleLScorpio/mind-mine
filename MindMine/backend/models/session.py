"""MindMine 核心数据模型。

本阶段（Phase 1）所有内容均为 Mock，但数据结构必须是正式的 Pydantic 模型，
以保证后续替换为真实 LLM / 知乎 API 时无需改动契约。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# 会话状态机
# --------------------------------------------------------------------------


class SessionState(str, Enum):
    """显式会话状态。Phase 1 按固定规则推进，不使用 LLM 判断。"""

    PROFILE = "PROFILE"
    DISCOVERY = "DISCOVERY"
    EXPERIENCE = "EXPERIENCE"
    REFLECTION = "REFLECTION"
    INSIGHT = "INSIGHT"
    CHALLENGE = "CHALLENGE"
    REFINEMENT = "REFINEMENT"
    COMPOSE = "COMPOSE"
    DONE = "DONE"


# --------------------------------------------------------------------------
# Stage 1 — 轻画像
# --------------------------------------------------------------------------

CurrentStatus = Literal[
    "student",
    "early_career",
    "mid_career",
    "senior",
    "freelance",
]

SharePreference = Literal[
    "experience",
    "opinion",
    "expertise",
    "mistakes",
]


class UserProfile(BaseModel):
    """用户轻画像。Phase 1 只有手动路径（source 固定为 manual）。"""

    source: Literal["manual", "oauth"] = "manual"
    current_status: CurrentStatus
    domains: list[str] = Field(default_factory=list)
    share_preferences: list[SharePreference] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Stage 2 — 问题卡片
# --------------------------------------------------------------------------


class QuestionCard(BaseModel):
    """推荐问题卡片。

    Phase 1 的 source 固定为 mock；接入知乎 API 后为 api。
    该字段是审计追踪，用于在 UI 上区分真实数据与演示数据。
    """

    question_id: str
    title: str
    why_fits: str
    tag: str
    url: str | None = None
    source: Literal["mock", "api"] = "mock"


# --------------------------------------------------------------------------
# Stage 3 — 知识状态
# --------------------------------------------------------------------------


class KnowledgeEvent(BaseModel):
    """结构化事件：发生了什么 + 结果如何。"""

    event: str
    result: str


class ThoughtFragment(BaseModel):
    """面向用户展示的思想碎片。

    这是 KnowledgeState 的「展示投影」：KnowledgeState 是系统内部结构，
    永远不直接上屏；ThoughtFragment 才是用户看得见的东西。

    设计约束：
    1. label 是可选的、开放的字符串，不是枚举。
       Phase 1 Mock 用「选择 / 期待 / 代价 / 结果」，
       接入 LLM 后可生成任意标签，前端不得硬编码分类。
    2. text 必须是用户原话的压缩，不是 AI 的改写。
    3. source_message_id 指向用户的哪一句话，用于「这是我说的」溯源。
    """

    id: str
    label: str | None = None
    text: str
    source_message_id: str


class FragmentLink(BaseModel):
    """两个碎片之间的关系。Insight Reveal 时据此绘制连接线。"""

    from_id: str
    to_id: str
    # 可选的关系说明，Phase 1 不显示，保留给 LLM 阶段
    relation: str | None = None


class KnowledgeState(BaseModel):
    """访谈过程中累积的结构化知识。

    严格约束：facts / events / beliefs / conflicts / reflections
    只能来自用户所说的内容。AI 的推测只能进入 candidate_insights。

    注意：本结构是系统内部表示，不得直接渲染到界面上。
    面向用户的展示请使用 ThoughtFragment。
    """

    facts: list[str] = Field(default_factory=list)
    events: list[KnowledgeEvent] = Field(default_factory=list)
    beliefs: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    candidate_insights: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            [
                self.facts,
                self.events,
                self.beliefs,
                self.conflicts,
                self.reflections,
                self.candidate_insights,
            ]
        )


# --------------------------------------------------------------------------
# 对话
# --------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Literal["user", "ai"]
    content: str
    turn: int


# --------------------------------------------------------------------------
# Stage 4 / 6 — 洞察
# --------------------------------------------------------------------------


class Insight(BaseModel):
    """洞察。surface_claim 是用户最初的表述，deep_insight 是提炼后的表达。

    naming 是「对经历的命名」，先于 deep_insight 出现。
    顺序很重要：先说「你做了什么」，再说「所以什么成立」，
    这样观点才像是从用户经历里长出来的，而不是 AI 下的结论。

    softened_span / added_qualifiers 仅 V2 使用，
    用于在界面上演示「同一个观点正在被修正」，而不是替换成新版本。
    """

    version: Literal["V1", "V2"]
    surface_claim: str
    deep_insight: str
    naming: str | None = None
    confirmed_by_user: bool = False
    user_edited_text: str | None = None

    # --- Refinement 展示用（V2） ---
    # V1 中被弱化/删除的绝对化表达，例如「不要让」
    softened_span: str | None = None
    # 经过 Challenge 后新增的限定条件，例如 ["兑现条件", "概率", "机会成本"]
    added_qualifiers: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Stage 5 — 社区挑战
# --------------------------------------------------------------------------


class CommunityPerspective(BaseModel):
    """社区观点。

    Phase 1 使用 Mock 数据，is_mock 必须为 True，
    前端必须显式标注「演示数据」，不得伪装成真实知乎作者。
    """

    id: str
    claim: str
    reason: str
    author: str
    badge: str
    source_label: str
    source_url: str | None = None
    challenge_question: str
    is_mock: bool = True


# --------------------------------------------------------------------------
# 会话
# --------------------------------------------------------------------------


class Session(BaseModel):
    id: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    state: SessionState = SessionState.PROFILE

    profile: UserProfile | None = None
    question: QuestionCard | None = None

    messages: list[ChatMessage] = Field(default_factory=list)
    knowledge_state: KnowledgeState = Field(default_factory=KnowledgeState)
    # KnowledgeState 的展示投影：用户唯一看得见的那一层
    fragments: list[ThoughtFragment] = Field(default_factory=list)
    fragment_links: list[FragmentLink] = Field(default_factory=list)
    user_turn_count: int = 0

    insight_v1: Insight | None = None
    challenge: CommunityPerspective | None = None
    challenge_response: str | None = None
    insight_v2: Insight | None = None
    # Ownership handshake：用户是否确认「这句话是我的」
    insight_v2_owned: bool = False

    # --- 观点压力测试的三条出口 ---
    # 用户没看追问就直接写答案
    challenge_skipped: bool = False
    # 看了追问，但决定保留原判断（不生成 V2）
    take_kept: bool = False

    composed_answer: str | None = None

    @property
    def final_insight(self) -> Insight | None:
        """成文时采用的观点。

        没有 V2 不等于用户没想清楚 —— 一个观点经过追问后仍然成立，
        本身也是一次更坚定的确认。所以这里不强求 V2。
        """
        return self.insight_v2 or self.insight_v1

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# 请求 / 响应体
# --------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    profile: UserProfile
    question_id: str


class PostMessageRequest(BaseModel):
    content: str


class PostMessageResponse(BaseModel):
    """一次用户发言的处理结果。

    fragments / fragment_links 是本次发言后的全量展示投影，
    前端据此增量渲染 Thought Fragment，不再渲染 KnowledgeState。
    """

    state: SessionState
    ai_reply: str | None
    knowledge_state: KnowledgeState
    fragments: list[ThoughtFragment] = Field(default_factory=list)
    fragment_links: list[FragmentLink] = Field(default_factory=list)
    user_turn_count: int
    insight_ready: bool
    insight: Insight | None = None


class OwnershipRequest(BaseModel):
    """Ownership handshake：用户确认或否认「这是我的观点」。"""

    owned: bool
    edited_text: str | None = None


class ChallengeRespondRequest(BaseModel):
    content: str


class ComposeResponse(BaseModel):
    """成文结果。

    challenge / insight_v2 允许为空：观点压力测试是增强体验，不是必经流程。
    用户跳过追问，或看完追问仍然保留原判断，都是正当路径。
    """

    insight_v1: Insight
    challenge: CommunityPerspective | None = None
    challenge_response: str = ""
    insight_v2: Insight | None = None
    # 成文实际采用的那句话（跳过/保留时即 insight_v1）
    final_insight: Insight | None = None
    take_kept: bool = False
    challenge_skipped: bool = False
    composed_answer: str
