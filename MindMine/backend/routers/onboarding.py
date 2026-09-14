"""Onboarding API 路由。

产品原则：不要让用户填写「我是谁」。
所以这里没有任何「保存画像字段」的端点——
只有「认识我」「我眼中的你」「哪里不像」「该你答的问题」。

统一响应信封与 sessions.py 一致。

身份边界（关键）：
    「用知乎认识我」的真实入口是 /oauth/zhihu/authorize（见 routers/oauth.py）。
    本文件不再包含任何读取 Access Secret 所属账号（开发者本人）数据的端点。
    「先聊两句」走 /onboarding/chat/* 与 /onboarding/from-chat。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config import settings
from models.profile import ChatAnswerRequest, CorrectionRequest
from services import question_matcher
from services.profile_service import profile_service

router = APIRouter()


def ok(data) -> dict:
    return {"ok": True, "data": data}


def _dev(used_real: bool) -> dict:
    """开发态 provider/source 标记。生产可通过 VERBOSE_PROVIDER_LOG=false 关闭。"""
    if not settings.verbose_provider_log:
        return {}
    return {
        "_provider": settings.llm_model if used_real else "mock",
        "_source": "real" if used_real else "mock_fallback",
    }


def _not_found(onboarding_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "ok": False,
            "error": {
                "code": "ONBOARDING_NOT_FOUND",
                "message": f"找不到这次对话：{onboarding_id}",
            },
        },
    )


# --------------------------------------------------------------------------
# 路径 A —— 用知乎认识我（真实 OAuth，入口在 /oauth/zhihu/authorize）
# --------------------------------------------------------------------------


@router.get("/onboarding/{onboarding_id}")
async def get_onboarding(onboarding_id: str) -> dict:
    """恢复一次已完成的 Onboarding（OAuth 回调后前端用它取回画像）。

    这里只读取本次会话自己的 onboarding 记录，不涉及任何知乎账号数据。
    """
    state = profile_service.get(onboarding_id)
    if state is None:
        raise _not_found(onboarding_id)
    return ok(
        {
            **state.model_dump(mode="json"),
            "source": state.profile.source,
        }
    )


# --------------------------------------------------------------------------
# 路径 B —— 先聊两句
# --------------------------------------------------------------------------


@router.get("/onboarding/chat/{step}")
async def chat_question(step: int) -> dict:
    """第 step 个问题。done=True 表示问够了，可以生成画像。"""
    q = profile_service.chat_question(step)
    return ok({"question": q, "done": q is None})


@router.post("/onboarding/from-chat")
async def from_chat(req: ChatAnswerRequest) -> dict:
    state = await profile_service.from_chat(req)
    used_real = state.profile.source == "chat_llm"
    return ok({**state.model_dump(mode="json"), **_dev(used_real)})


# --------------------------------------------------------------------------
# 自然语言纠正 —— 不是字段编辑
# --------------------------------------------------------------------------


@router.post("/onboarding/correct")
async def correct(req: CorrectionRequest) -> dict:
    content = req.content.strip()
    if not content:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": {"code": "EMPTY_MESSAGE", "message": "说点什么都行"},
            },
        )

    state, used_real = await profile_service.correct(req.onboarding_id, content)
    if state is None:
        raise _not_found(req.onboarding_id)
    return ok({**state.model_dump(mode="json"), **_dev(used_real)})


# --------------------------------------------------------------------------
# 从画像出发找问题
# --------------------------------------------------------------------------


@router.get("/onboarding/{onboarding_id}/questions")
async def matched_questions(onboarding_id: str) -> dict:
    state = profile_service.get(onboarding_id)
    if state is None:
        raise _not_found(onboarding_id)

    # Mock 永久保留，作为真实链路失败时的 Demo fallback
    mock_items = profile_service.match_questions(onboarding_id)
    items, used_real = await question_matcher.find_questions(state.profile, mock_items)

    return ok(
        {
            "items": [q.model_dump() for q in items],
            "source": "api" if used_real else "mock",
            **_dev(used_real),
        }
    )
