"""会话存储与状态流转。

Phase 1 使用进程内存储（TECH_DESIGN 允许第一阶段用内存 Session）。
接入 SQLite 时只需替换 SessionStore 的实现，路由层无需改动。
"""

from __future__ import annotations

import uuid

from models.session import (
    ChatMessage,
    Insight,
    QuestionCard,
    Session,
    SessionState,
    UserProfile,
)
from services import demo_content


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

    def create(self, profile: UserProfile, question_id: str) -> Session:
        question = self._resolve_question(question_id)
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
    def _resolve_question(question_id: str) -> QuestionCard:
        for q in demo_content.DEMO_QUESTIONS:
            if q.question_id == question_id:
                return q.model_copy(deep=True)
        # 未知 question_id 时回退到主 Demo 问题，保证演示不中断
        for q in demo_content.DEMO_QUESTIONS:
            if q.question_id == demo_content.DEMO_QUESTION_ID:
                return q.model_copy(deep=True)
        raise SessionNotFoundError(question_id)

    # ------------------------------------------------------------------
    # Stage 3 — 访谈
    # ------------------------------------------------------------------

    def post_message(self, session_id: str, content: str) -> tuple[Session, str | None, bool]:
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

        ai_reply, insight_ready = demo_content.MockInterviewEngine.advance(
            session, content
        )
        session.touch()
        return session, ai_reply, insight_ready

    # ------------------------------------------------------------------
    # Stage 4 — 洞察确认
    # ------------------------------------------------------------------

    def confirm_insight(self, session_id: str) -> Session:
        session = self.get(session_id)

        if session.state != SessionState.INSIGHT or session.insight_v1 is None:
            raise InvalidStateError(session.state, "INSIGHT")

        session.insight_v1.confirmed_by_user = True
        session.challenge = demo_content.DEMO_CHALLENGE.model_copy(deep=True)
        session.state = SessionState.CHALLENGE
        session.touch()
        return session

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

    def respond_challenge(self, session_id: str, content: str) -> Session:
        """路径 A —— 用户补充了一点东西，观点因此增加新的限定。"""
        session = self.get(session_id)

        if session.state != SessionState.CHALLENGE:
            raise InvalidStateError(session.state, "CHALLENGE")

        session.challenge_response = content
        session.insight_v2 = demo_content.DEMO_INSIGHT_V2.model_copy(deep=True)
        session.insight_v2_owned = False
        session.take_kept = False
        session.state = SessionState.REFINEMENT
        session.touch()
        return session

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

    def compose(self, session_id: str) -> Session:
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
            session.composed_answer = demo_content.compose_answer(session)

        session.state = SessionState.DONE
        session.touch()
        return session


store = SessionStore()
