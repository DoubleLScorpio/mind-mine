"""Onboarding API 路由。

产品原则：不要让用户填写「我是谁」。
所以这里没有任何「保存画像字段」的端点——
只有「认识我」「我眼中的你」「哪里不像」「该你答的问题」。

统一响应信封与 sessions.py 一致。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.profile import ChatAnswerRequest, CorrectionRequest
from services.profile_service import profile_service

router = APIRouter()


def ok(data) -> dict:
    return {"ok": True, "data": data}


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
# 路径 A —— 用知乎认识我
# --------------------------------------------------------------------------


@router.get("/onboarding/traces")
async def traces() -> dict:
    """逐步浮现的痕迹。Phase 1 全部是演示数据，前端必须明确标注。"""
    return ok({"items": [t.model_dump() for t in profile_service.traces()]})


@router.post("/onboarding/from-zhihu")
async def from_zhihu() -> dict:
    """Phase 1 不接 OAuth，直接返回演示画像。"""
    state = profile_service.from_zhihu()
    return ok(state.model_dump(mode="json"))


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
    state = profile_service.from_chat(req)
    return ok(state.model_dump(mode="json"))


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

    state = profile_service.correct(req.onboarding_id, content)
    if state is None:
        raise _not_found(req.onboarding_id)
    return ok(state.model_dump(mode="json"))


# --------------------------------------------------------------------------
# 从画像出发找问题
# --------------------------------------------------------------------------


@router.get("/onboarding/{onboarding_id}/questions")
async def matched_questions(onboarding_id: str) -> dict:
    if profile_service.get(onboarding_id) is None:
        raise _not_found(onboarding_id)
    items = profile_service.match_questions(onboarding_id)
    return ok({"items": [q.model_dump() for q in items]})
