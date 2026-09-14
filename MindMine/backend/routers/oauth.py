"""知乎 OAuth 路由。

路径 A 的真实实现：
    前端「用知乎认识我」→ GET /oauth/zhihu/authorize
      → 后端生成 state、写 HttpOnly cookie、302 到知乎授权页
      → 用户在知乎登录并授权
      → 知乎 302 回 /oauth/zhihu/callback?authorization_code=...
      → 后端校验 state/cookie、换 token、读当前用户数据、生成画像
      → 302 回前端 /oauth/return?ob=<onboarding_id>

身份边界：
    这里的 access_token（X-OAuth-Token）代表「当前授权用户」。
    服务器 Access Secret 只是换取/携带用户 token 的调用方凭据，
    绝不能作为「当前访客」身份。
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, Cookie, HTTPException, Query
from fastapi.responses import RedirectResponse

from config import settings
from services import profile_extractor
from services.oauth_store import oauth_store
from services.profile_service import profile_service
from services.zhihu_oauth import ZhihuOAuthError, zhihu_oauth

logger = logging.getLogger("mindmine.oauth")

router = APIRouter(prefix="/oauth/zhihu", tags=["oauth"])

_STATE_COOKIE = "mm_oauth_state"
# 路由实际挂在 /api/v1 前缀下，完整路径是 /api/v1/oauth/zhihu/*。
# cookie path 必须与之匹配，否则 callback 请求不会回传 state cookie，
# 后端会误判 missing_state。这里用 /api/v1/oauth/zhihu 精确覆盖
# authorize 与 callback 两个端点。
_COOKIE_PATH = "/api/v1/oauth/zhihu"


def _oauth_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "ok": False,
            "error": {
                "code": "OAUTH_NOT_CONFIGURED",
                "message": "知乎登录暂不可用，请先聊两句。",
            },
        },
    )


def _frontend(path: str) -> RedirectResponse:
    """跳转回前端（Vercel），只带路径，不带任何 token。"""
    base = settings.frontend_url.rstrip("/")
    return RedirectResponse(url=f"{base}{path}", status_code=302)


@router.get("/authorize")
async def authorize(return_to: str = Query(default="/portrait")) -> RedirectResponse:
    """发起知乎授权。

    只允许站内相对路径作为 return_to，防止开放重定向。
    生成随机 state 并写入 HttpOnly cookie，用于 callback 时绑定会话。

    OAuth 未配置时，不返回错误 JSON，而是 302 回前端的错误落地页，
    由前端引导「先聊两句」—— 保证不授权也永远有可用路径。
    """
    if not zhihu_oauth.configured:
        logger.warning("oauth authorize unavailable — redirect to chat fallback")
        return _frontend("/oauth/return?error=not_configured")

    if not return_to.startswith("/") or return_to.startswith("//"):
        return_to = "/portrait"

    state = oauth_store.create(return_to)
    url = zhihu_oauth.authorize_url(state)

    resp = RedirectResponse(url=url, status_code=302)
    resp.set_cookie(
        key=_STATE_COOKIE,
        value=state,
        path=_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=settings.oauth_cookie_secure,
        max_age=600,
    )
    logger.info("oauth authorize state=%s…", state[:8])
    return resp


@router.get("/callback")
async def callback(
    authorization_code: str | None = Query(default=None),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    mm_oauth_state: str | None = Cookie(default=None),
) -> RedirectResponse:
    """知乎授权回调。绑定 state + cookie，换取当前用户身份。"""
    # 知乎回调实测主用 authorization_code，兼容 code
    auth_code = (authorization_code or code or "").strip()

    # state 校验：知乎线上实测会回传 state（query）。state 是本次授权
    # 请求的随机一次性标识，优先用它绑定会话；cookie 只作辅助、不强制，
    # 避免跨域 / 浏览器策略导致 cookie 丢失时误判 missing_state。
    q_state = (state or "").strip()
    c_state = (mm_oauth_state or "").strip()

    if q_state and c_state and q_state != c_state:
        logger.warning("oauth callback state mismatch")
        return _frontend("/oauth/return?error=state_mismatch")

    effective_state = q_state or c_state
    if not effective_state:
        logger.warning("oauth callback missing state")
        return _frontend("/oauth/return?error=missing_state")

    flow = oauth_store.consume(effective_state)
    if flow is None:
        logger.warning("oauth callback invalid/expired state")
        return _frontend("/oauth/return?error=invalid_state")

    # 用户拒绝授权 / 缺少授权码：回退「先聊两句」，不读开发者数据
    if not auth_code:
        logger.info("oauth callback no code — user declined")
        return _frontend("/oauth/return?error=declined")

    if not zhihu_oauth.configured:
        return _frontend("/oauth/return?error=not_configured")

    # 1) 换 access_token
    try:
        oauth_token = await zhihu_oauth.exchange_token(auth_code)
    except ZhihuOAuthError as exc:
        logger.warning("oauth exchange failed: %s", exc)
        return _frontend("/oauth/return?error=token_failed")

    # 2) 读取「当前授权用户」数据
    try:
        user = await zhihu_oauth.fetch_user(oauth_token)
    except ZhihuOAuthError as exc:
        logger.warning("oauth user fetch failed: %s", exc)
        return _frontend("/oauth/return?error=user_failed")

    # 3) ProfileExtractor → ContributionProfile → MindPortrait
    built = await profile_extractor.build_portrait_from_user(user)
    if built is None:
        logger.warning("oauth portrait build failed")
        return _frontend("/oauth/return?error=portrait_failed")

    profile, portrait, used_real = built
    state_obj = profile_service.adopt(profile, portrait)
    logger.info(
        "oauth portrait ok onboarding=%s source=oauth_real real=%s",
        state_obj.onboarding_id,
        used_real,
    )

    # 4) 跳回前端恢复画像。onboarding_id 是服务端会话键，不是用户身份。
    return_to = flow.return_to
    sep = "&" if "?" in return_to else "?"
    dest = f"{return_to}{sep}ob={quote(state_obj.onboarding_id)}"
    return _frontend(dest)
