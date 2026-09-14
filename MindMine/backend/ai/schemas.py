"""LLM 结构化输出的契约。

所有关键模块用 Pydantic 校验，不解析自由文本。
这些 schema 只描述「模型该返回什么」，与会话模型解耦。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FragmentOut(BaseModel):
    """给用户看的思想碎片。text 必须是用户原话的压缩。"""

    label: str = ""
    text: str


class EventOut(BaseModel):
    event: str
    result: str


class ExtractionOut(BaseModel):
    """一轮用户发言的抽取结果。

    前端只显示 fragments；其余进入内部 KnowledgeState。
    所有字段都允许为空 —— 用户只是表达态度时就该是空的。
    """

    fragments: list[FragmentOut] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    events: list[EventOut] = Field(default_factory=list)
    beliefs: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    candidate_insights: list[str] = Field(default_factory=list)
    # 信息是否已经足够凝结出一个判断
    ready_for_insight: bool = False


class InsightOut(BaseModel):
    """对经历的命名 + 从中长出的判断。"""

    experience_summary: str
    insight: str
    evidence_fragment_ids: list[str] = Field(default_factory=list)


class RefineOut(BaseModel):
    """观点修正结果。

    用户没有真正改变判断时，允许 refined_insight == original_insight，
    且两个列表为空 —— 不强迫观点升级。
    """

    original_insight: str
    refined_insight: str
    removed_or_softened: list[str] = Field(default_factory=list)
    added_qualifiers: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""


class TopicQueriesOut(BaseModel):
    """从贡献画像提炼的检索主题（Phase B 用）。"""

    queries: list[str] = Field(default_factory=list)


class MatchReasonOut(BaseModel):
    """为什么是你。必须引用画像里真实存在的信息。"""

    from_you: str
    therefore: str


class PerspectiveOut(BaseModel):
    """从真实知乎回答里提炼的一种视角（Phase C 用）。"""

    claim: str
    # 站在用户观点面前会问的那句话
    challenge_question: str
    # 是否真的构成不同视角。false 时前端用「还有一个角度」而不是对立表述
    is_opposing: bool = True
