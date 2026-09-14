"""MindMine 后端入口。

Phase 1：单体 FastAPI 应用，会话存于进程内存，全部内容为 Mock。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routers.onboarding import router as onboarding_router
from routers.sessions import router as sessions_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("mindmine")

app = FastAPI(
    title="MindMine API",
    description="You know more than you think. — Phase 1 Mock Skeleton",
    version="0.1.0",
)

# CORS：只放行必要的前端 origin，不使用通配符 "*"。
# 通过环境变量 CORS_ORIGINS 注入额外域名（逗号分隔）。
_allow_origins = settings.cors_origin_list()
logger.info("cors allow_origins=%s", _allow_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底异常处理，保证前端始终拿到统一信封。"""
    logger.exception("未处理异常：%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
            },
        },
    )


@app.get("/")
async def root() -> dict:
    return {
        "ok": True,
        "data": {
            "name": "MindMine API",
            "slogan": "You know more than you think.",
            "phase": "1-mock",
            "docs": "/docs",
        },
    }
