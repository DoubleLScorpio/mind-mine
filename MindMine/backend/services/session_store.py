"""会话存储与状态流转。

Phase 1 使用进程内存储（TECH_DESIGN 允许第一阶段用内存 Session）。
接入 SQLite 时只需替换 SessionStore 的实现，路由层无需改动。

Real Integration 阶段：访谈/洞察/修正/成文优先走真实 LLM，
任一环节失败自动退回 services.demo_content 的固定脚本 ——
Demo fallback 永久保留，演示不会因为模型不可用而卡死。
"""

from __future__ import annotations

import re
import uuid

from ai import engine
from models.session import (
    ChatMessage,
    Insight,
    QuestionCard,
    Session,
    SessionState,
    UserProfile,
)
from services import demo_content, perspective_service
from services.llm_service import llm

# 真实模式下的访谈上限：到这一轮无论如何都要凝结判断，
# 不让用户被无限追问。
MAX_INTERVIEW_TURNS = 6
# 少于这个碎片数不认为「收够了料」
MIN_FRAGMENTS_FOR_INSIGHT = 3

_QID_RE = re.compile(r"/question/(\d+)")


def _question_id_of(q: QuestionCard | None) -> str:
    """取问题的知乎数字 id。

    真实问题的 question_id 已是数字；Mock 问题是 q_xxx 这种，
    此时从 url 里找，找不到就返回空（表示无法按题过滤）。
    """
    if q is None:
        return ""
    if q.question_id.isdigit():
        return q.question_id
    m = _QID_RE.search(q.url or "")
    return m.group(1) if m else ""


class SessionNotFoundError(Exception):
    """会话不存在。"""


class InvalidStateError(Exception):
    """非法的状态流转。"""

    def __init__(self, current: SessionState, expected: str) -> None:
        self.current = current
        self.expected = expected
        super().__init__(
            f"当前状态为 {current.value}，无法执行该操作（期望：{expected}）"
        )


class SessionStore:
    """进程内会话存储。"""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    # ------------------------------------------------------------------
    # 基础读写
    # ------------------------------------------------------------------

    def get(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def list_questions(self, profile: UserProfile | None = None) -> list[QuestionCard]:
        """返回问题列表。

        why_fits 会按用户画像重新渲染 —— 让用户觉得「该我回答」的
        唯一手段是引用用户自己，而不是夸这个问题有多好。
        """
        result: list[QuestionCard] = []
        for q in demo_content.DEMO_QUESTIONS:
            card = q.model_copy(deep=True)
            card.why_fits = demo_content.render_why_fits(q, profile)
            result.append(card)
        return result

    def create(
        self,
        profile: UserProfile,
        question_id: str,
        *,
        title: str = "",
        url: str = "",
    ) -> Session:
        """开一个新会话。

        真实模式下问题来自知乎，question_id 是数字 id 且带 url ——
        此时必须原样保留，不能被 Demo 问题顶替，否则访谈上下文就错了。
        """
        question = self._resolve_question(question_id, title=title, url=url)
        if question.source == "mock":
            question.why_fits = demo_content.render_why_fits(question, profile)

        session = Session(
            id=f"s_{uuid.uuid4().hex[:12]}",
            state=SessionState.DISCOVERY,
            profile=profile,
            question=question,
        )

        # 访谈开场白由 AI 提出
        session.messages.append(
            ChatMessage(
                role="ai",
                content=demo_content.MockInterviewEngine.opening_question(),
                turn=0,
            )
        )

        self._sessions[session.id] = session
        return session

    @staticmethod
    def _resolve_question(
        question_id: str, *, title: str = "", url: str = ""
    ) -> QuestionCard:
        """解析问题。

        优先匹配 Demo 问题；匹配不到但调用方给了 title，
        说明这是一道真实知乎问题 —— 原样构造，不要退回 Demo 问题，
        否则访谈的上下文会和用户看到的题目不一致。
        """
        for q in demo_content.DEMO_QUESTIONS:
            if q.question_id == question_id:
                return q.model_copy(deep=True)

        if title.strip():
            return QuestionCard(
                question_id=question_id,
                title=title.strip(),
                why_fits="",
                tag="",
                url=url.strip() or None,
                source="api",
            )

        # 既不是 Demo 问题、也没带标题时才回退，保证演示不中断
        for q in demo_content.DEMO_QUESTIONS:
            if q.question_id == demo_content.DEMO_QUESTION_ID:
                return q.model_copy(deep=True)
        raise SessionNotFoundError(question_id)

    # ------------------------------------------------------------------
    # Stage 3 — 访谈
    # ------------------------------------------------------------------

    async def post_message(
        self, session_id: str, content: str
    ) -> tuple[Session, str | None, bool, bool]:
        """处理一次用户发言。

        返回 (session, ai_reply, insight_ready, used_real)。

        真实模式：LLM 抽取碎片 + 生成追问；任一环节失败自动退回 Demo 脚本，
        所以演示不会因为模型不可用而卡住。
        """
        session = self.get(session_id)

        allowed = {
            SessionState.DISCOVERY,
            SessionState.EXPERIENCE,
            SessionState.REFLECTION,
        }
        if session.state not in allowed:
            raise InvalidStateError(session.state, "DISCOVERY / EXPERIENCE / REFLECTION")

        session.messages.append(
            ChatMessage(
                role="user",
                content=content,
                turn=session.user_turn_count + 1,
            )
        )

        if not llm.available:
            ai_reply, insight_ready = demo_content.MockInterviewEngine.advance(
                session, content
            )
            session.touch()
            return session, ai_reply, insight_ready, False

        # ---- 真实链路 ----
        session.user_turn_count += 1
        used_real = False

        extraction, ok = await engine.extract(session, content)
        if extraction is not None:
            engine.apply_extraction(session, extraction)
            used_real = ok

        # 状态推进：前两轮先把经历讲出来，之后进入反思
        session.state = (
            SessionState.EXPERIENCE
            if session.user_turn_count <= 2
            else SessionState.REFLECTION
        )

        # 是否收够了料。模型说够了、或已经聊满上限
        enough = bool(extraction and extraction.ready_for_insight)
        reached_cap = session.user_turn_count >= MAX_INTERVIEW_TURNS
        has_material = len(session.fragments) >= MIN_FRAGMENTS_FOR_INSIGHT

        if (enough and has_material) or reached_cap:
            insight, ok2 = await engine.make_insight(session)
            session.insight_v1 = insight
            session.state = SessionState.INSIGHT
            session.touch()
            return session, None, True, used_real or ok2

        ai_reply, ok3 = await engine.next_question(session, content)
        if ai_reply:
            session.messages.append(
                ChatMessage(
                    role="ai",
                    content=ai_reply,
                    turn=session.user_turn_count,
                )
            )
        session.touch()
        return session, ai_reply, False, used_real or ok3

    # ------------------------------------------------------------------
    # Stage 4 — 洞察确认
    # ------------------------------------------------------------------

    async def confirm_insight(self, session_id: str) -> Session:
        """用户点「看看」时，才真正去取社区视角。

        真实优先，失败退回 Demo；无论如何「直接写成答案」始终可用。
        """
        session = self.get(session_id)

        if session.state != SessionState.INSIGHT or session.insight_v1 is None:
            raise InvalidStateError(session.state, "INSIGHT")

        session.insight_v1.confirmed_by_user = True

        insight_text = (
            session.insight_v1.user_edited_text or session.insight_v1.deep_insight
        )
        q = session.question
        perspective, used_real = await perspective_service.fetch_perspective(
            question_title=q.title if q else "",
            question_id=_question_id_of(q),
            user_insight=insight_text,
        )
        session.challenge = perspective
        session.state = SessionState.CHALLENGE
        session.touch()
        return session, used_real

    def edit_insight(self, session_id: str, text: str) -> Session:
        """用户选择「我想修改」时提交自己的表述。"""
        session = self.get(session_id)

        if session.state != SessionState.INSIGHT or session.insight_v1 is None:
            raise InvalidStateError(session.state, "INSIGHT")

        session.insight_v1.user_edited_text = text
        session.insight_v1.deep_insight = text
        session.touch()
        return session

    # ------------------------------------------------------------------
    # Stage 5 — 挑战回应
    # ------------------------------------------------------------------

    async def respond_challenge(self, session_id: str, content: str) -> Session:
        """路径 A —— 用户补充了一点东西，观点因此增加新的限定。

        真实模式下由 LLM 修正；允许 refined == original，不强迫观点升级。
        """
        session = self.get(session_id)

        if session.state != SessionState.CHALLENGE:
            raise InvalidStateError(session.state, "CHALLENGE")

        session.challenge_response = content
        insight_v2, refine_real = await engine.refine_insight(session, content)
        session.insight_v2 = insight_v2
        session.insight_v2_owned = False
        session.take_kept = False
        session.state = SessionState.REFINEMENT
        session.touch()
        return session, refine_real

    # ------------------------------------------------------------------
    # 观点压力测试的另外两条出口
    #
    # Challenge 是增强体验，不是必经流程。
    # 所以「跳过」和「保留原判断」都必须是完整可用路径，
    # 不弹二次确认、不制造负罪感、不假装用户一定想深了一层。
    # ------------------------------------------------------------------

    def skip_challenge(self, session_id: str) -> Session:
        """路径 C/D —— 不看追问，或看了但直接去写答案。

        允许从 INSIGHT（还没看）和 CHALLENGE（看了但跳过）两个状态进入。
        """
        session = self.get(session_id)

        if session.state not in {SessionState.INSIGHT, SessionState.CHALLENGE}:
            raise InvalidStateError(session.state, "INSIGHT / CHALLENGE")

        if session.insight_v1 is None:
            raise InvalidStateError(session.state, "INSIGHT（缺少观点）")

        # 用户已经认下这句话了，直接以它成文
        session.insight_v1.confirmed_by_user = True
        session.challenge_skipped = True
        session.insight_v2 = None
        session.insight_v2_owned = True
        session.state = SessionState.COMPOSE
        session.touch()
        return session

    def keep_take(self, session_id: str) -> Session:
        """路径 B —— 看了追问，仍然这么想。

        不强制生成 V2。一个观点经过追问后仍然成立，
        本身也是一次更坚定的确认。
        """
        session = self.get(session_id)

        if session.state != SessionState.CHALLENGE:
            raise InvalidStateError(session.state, "CHALLENGE")

        if session.insight_v1 is None:
            raise InvalidStateError(session.state, "CHALLENGE（缺少观点）")

        session.insight_v1.confirmed_by_user = True
        session.take_kept = True
        session.insight_v2 = None
        session.insight_v2_owned = True
        session.state = SessionState.COMPOSE
        session.touch()
        return session

    # ------------------------------------------------------------------
    # Ownership handshake
    #
    # AI 可以帮助发现和整理，但「这是不是我的观点」只能由用户决定。
    # 未经用户认领，不允许进入 Compose。
    # ------------------------------------------------------------------

    def set_ownership(
        self, session_id: str, owned: bool, edited_text: str | None = None
    ) -> Session:
        session = self.get(session_id)

        if session.state != SessionState.REFINEMENT or session.insight_v2 is None:
            raise InvalidStateError(session.state, "REFINEMENT")

        if edited_text:
            session.insight_v2.user_edited_text = edited_text
            session.insight_v2.deep_insight = edited_text

        session.insight_v2_owned = owned
        session.insight_v2.confirmed_by_user = owned
        # 观点一旦改动，已生成的回答作废，需要重新成文
        if edited_text:
            session.composed_answer = None
        session.touch()
        return session

    # ------------------------------------------------------------------
    # Stage 6 — 成文
    # ------------------------------------------------------------------

    async def compose(self, session_id: str) -> Session:
        session = self.get(session_id)

        if session.state not in {SessionState.REFINEMENT, SessionState.COMPOSE, SessionState.DONE}:
            raise InvalidStateError(session.state, "REFINEMENT")

        # 成文采用 final_insight：没有 V2 不等于用户没想清楚。
        # 跳过追问、或看完仍然保留原判断，都是正当路径。
        if session.final_insight is None:
            raise InvalidStateError(session.state, "REFINEMENT（缺少观点）")

        # Ownership handshake：未经用户认领的观点不允许成文。
        # 这是产品红线 —— 决定「这是不是我的观点」的人只能是用户。
        if not session.insight_v2_owned:
            raise InvalidStateError(session.state, "REFINEMENT（用户尚未确认这是自己的观点）")

        # 幂等：已生成则直接返回
        if session.composed_answer is None:
            answer, _ = await engine.compose_answer(session)
            session.composed_answer = answer

        session.state = SessionState.DONE
        session.touch()
        return session


store = SessionStore()
