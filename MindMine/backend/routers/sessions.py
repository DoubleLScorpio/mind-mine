"""MindMine API 路由。

统一响应信封（TECH_DESIGN 第 6 节）：
  成功 {"ok": true, "data": {...}}
  失败 {"ok": false, "error": {"code": "...", "message": "..."}}
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config import settings
from services.llm_service import llm
from models.session import (
    ChallengeRespondRequest,
    ComposeResponse,
    CreateSessionRequest,
    OwnershipRequest,
    PostMessageRequest,
    PostMessageResponse,
    UserProfile,
)
from services import demo_content
from services.session_store import (
    InvalidStateError,
    SessionNotFoundError,
    store,
)

router = APIRouter()


def ok(data) -> dict:
    return {"ok": True, "data": data}


def _dev(used_real: bool) -> dict:
    """开发态 provider/source 标记。
    verbose_provider_log=False 时返回空 dict，不污染生产响应。
    """
    if not settings.verbose_provider_log:
        return {}
    return {
        "_provider": settings.llm_model if used_real else "mock",
        "_source": "real" if used_real else "mock_fallback",
    }


def _not_found(session_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "ok": False,
            "error": {
                "code": "SESSION_NOT_FOUND",
                "message": f"会话不存在：{session_id}",
            },
        },
    )


def _invalid_state(exc: InvalidStateError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "ok": False,
            "error": {
                "code": "SESSION_INVALID_STATE",
                "message": str(exc),
            },
        },
    )


# --------------------------------------------------------------------------
# 健康检查与问题列表
# --------------------------------------------------------------------------


@router.get("/health")
async def health() -> dict:
    """健康检查同时暴露各 provider 的实际运行模式。

    用于确认「每个外部依赖都能独立 fallback」，
    不返回任何密钥（只返回脱敏后的标识）。
    """
    from services.llm_service import llm
    from services.zhihu_service import zhihu

    return ok(
        {
            "status": "healthy",
            "phase": "2-real-integration",
            "providers": {
                "llm": {
                    "configured": settings.llm_configured,
                    "mode": settings.llm_mode(),
                    "model": settings.llm_model if settings.llm_configured else None,
                    "key": settings.masked_key(),
                    "available": llm.available,
                },
                "zhihu": {
                    "mode": settings.zhihu_mode(),
                    "cli_available": zhihu.available,
                },
                "profile": {"mode": settings.profile_provider},
            },
            # 任一 provider 不可用时仍可完整演示
            "demo_fallback": True,
        }
    )


@router.post("/questions")
async def list_questions_for_profile(profile: UserProfile) -> dict:
    """Stage 2 —— 按用户画像渲染「为什么该你回答」。

    用 POST 是因为需要携带画像；Phase 1 不落库，纯粹用于文案渲染。
    """
    items = store.list_questions(profile)
    return ok({"items": [q.model_dump() for q in items]})


@router.get("/questions")
async def list_questions() -> dict:
    """无画像时的兜底列表。"""
    items = store.list_questions(None)
    return ok({"items": [q.model_dump() for q in items]})


# --------------------------------------------------------------------------
# 会话
# --------------------------------------------------------------------------


@router.post("/sessions")
async def create_session(req: CreateSessionRequest) -> dict:
    session = store.create(
        profile=req.profile,
        question_id=req.question_id,
        title=req.title,
        url=req.url,
    )
    return ok(session.model_dump(mode="json"))


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    try:
        session = store.get(session_id)
    except SessionNotFoundError:
        raise _not_found(session_id)
    return ok(session.model_dump(mode="json"))


# --------------------------------------------------------------------------
# Stage 3 — 访谈
# --------------------------------------------------------------------------


@router.post("/sessions/{session_id}/messages")
async def post_message(session_id: str, req: PostMessageRequest) -> dict:
    content = req.content.strip()
    if not content:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": {"code": "EMPTY_MESSAGE", "message": "消息内容不能为空"},
            },
        )

    try:
        session, ai_reply, insight_ready, used_real = await store.post_message(
            session_id, content
        )
    except SessionNotFoundError:
        raise _not_found(session_id)
    except InvalidStateError as exc:
        raise _invalid_state(exc)

    payload = PostMessageResponse(
        state=session.state,
        ai_reply=ai_reply,
        knowledge_state=session.knowledge_state,
        fragments=session.fragments,
        fragment_links=session.fragment_links,
        user_turn_count=session.user_turn_count,
        insight_ready=insight_ready,
        insight=session.insight_v1 if insight_ready else None,
    )
    return ok({**payload.model_dump(mode="json"), **_dev(used_real)})


# --------------------------------------------------------------------------
# Stage 4 — 洞察
# --------------------------------------------------------------------------


@router.post("/sessions/{session_id}/insight/confirm")
async def confirm_insight(session_id: str) -> dict:
    try:
        session, perspective_real = await store.confirm_insight(session_id)
    except SessionNotFoundError:
        raise _not_found(session_id)
    except InvalidStateError as exc:
        raise _invalid_state(exc)

    return ok(
        {
            "state": session.state.value,
            "insight_v1": session.insight_v1.model_dump(mode="json"),
            "challenge": session.challenge.model_dump(mode="json"),
            **_dev(perspective_real),
        }
    )


@router.patch("/sessions/{session_id}/insight")
async def edit_insight(session_id: str, req: PostMessageRequest) -> dict:
    try:
        session = store.edit_insight(session_id, req.content.strip())
    except SessionNotFoundError:
        raise _not_found(session_id)
    except InvalidStateError as exc:
        raise _invalid_state(exc)

    return ok({"insight_v1": session.insight_v1.model_dump(mode="json")})


# --------------------------------------------------------------------------
# Stage 5 — 挑战
# --------------------------------------------------------------------------


@router.post("/sessions/{session_id}/challenge/respond")
async def respond_challenge(
    session_id: str, req: ChallengeRespondRequest
) -> dict:
    content = req.content.strip()
    if not content:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": {"code": "EMPTY_MESSAGE", "message": "回应内容不能为空"},
            },
        )

    try:
        session, refine_real = await store.respond_challenge(session_id, content)
    except SessionNotFoundError:
        raise _not_found(session_id)
    except InvalidStateError as exc:
        raise _invalid_state(exc)

    return ok(
        {
            "state": session.state.value,
            "insight_v1": session.insight_v1.model_dump(mode="json"),
            "insight_v2": session.insight_v2.model_dump(mode="json"),
            "challenge_summary": demo_content.CHALLENGE_SUMMARY,
            **_dev(refine_real),
        }
    )


@router.post("/sessions/{session_id}/challenge/skip")
async def skip_challenge(session_id: str) -> dict:
    """不看追问，或看完直接去写答案。

    Challenge 是增强体验，不是必经流程 —— 所以这里不弹二次确认。
    """
    try:
        session = store.skip_challenge(session_id)
    except SessionNotFoundError:
        raise _not_found(session_id)
    except InvalidStateError as exc:
        raise _invalid_state(exc)

    return ok(
        {
            "state": session.state.value,
            "insight_v1": session.insight_v1.model_dump(mode="json"),
            "challenge_skipped": session.challenge_skipped,
        }
    )


@router.post("/sessions/{session_id}/challenge/keep")
async def keep_take(session_id: str) -> dict:
    """看了追问，仍然这么想。

    不强制生成 V2 —— 一个观点经过追问后仍然成立，
    本身也是一次更坚定的确认。
    """
    try:
        session = store.keep_take(session_id)
    except SessionNotFoundError:
        raise _not_found(session_id)
    except InvalidStateError as exc:
        raise _invalid_state(exc)

    return ok(
        {
            "state": session.state.value,
            "insight_v1": session.insight_v1.model_dump(mode="json"),
            "take_kept": session.take_kept,
        }
    )


# --------------------------------------------------------------------------
# Ownership handshake
#
# AI 可以帮助发现和整理，但「这是不是我的观点」只能由用户决定。
# --------------------------------------------------------------------------


@router.post("/sessions/{session_id}/insight/ownership")
async def set_ownership(session_id: str, req: OwnershipRequest) -> dict:
    try:
        session = store.set_ownership(
            session_id, owned=req.owned, edited_text=(req.edited_text or "").strip() or None
        )
    except SessionNotFoundError:
        raise _not_found(session_id)
    except InvalidStateError as exc:
        raise _invalid_state(exc)

    return ok(
        {
            "state": session.state.value,
            "insight_v2": session.insight_v2.model_dump(mode="json"),
            "owned": session.insight_v2_owned,
        }
    )


# --------------------------------------------------------------------------
# Stage 6 — 成文
# --------------------------------------------------------------------------


@router.post("/sessions/{session_id}/compose")
async def compose(session_id: str) -> dict:
    try:
        session = await store.compose(session_id)
    except SessionNotFoundError:
        raise _not_found(session_id)
    except InvalidStateError as exc:
        raise _invalid_state(exc)

    payload = ComposeResponse(
        insight_v1=session.insight_v1,
        challenge=session.challenge,
        challenge_response=session.challenge_response or "",
        insight_v2=session.insight_v2,
        final_insight=session.final_insight,
        take_kept=session.take_kept,
        challenge_skipped=session.challenge_skipped,
        composed_answer=session.composed_answer or "",
    )
    return ok(
        {
            **payload.model_dump(mode="json"),
            "state": session.state.value,
            "challenge_summary": demo_content.CHALLENGE_SUMMARY,
            **_dev(llm.available),
        }
    )
