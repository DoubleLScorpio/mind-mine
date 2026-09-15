"""知乎 OAuth 用户数据服务（HTTP 直连，不经 zhihu-cli）。

这是「用户身份」与「平台能力」的分离点：

    zhihu_service.ZhihuService  → 用 Access Secret（CLI）做搜索/问题推荐/社区观点，
                                  只代表「开放平台调用方」，绝不代表当前访客。

    zhihu_oauth.ZhihuOAuth     → 用 app_id/app_key 发起授权，换到用户的
                                  access_token（X-OAuth-Token），代表「当前授权用户」。

两者共用服务器的 Access Secret（Bearer），但 Access Secret 在这里只是
调用方凭据；真正决定「读谁的知乎数据」的是 X-OAuth-Token。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from config import settings

logger = logging.getLogger("mindmine.zhihu_oauth")

# 知乎 OAuth / 用户数据 HTTP API 端点
_AUTHORIZE_URL = "https://openapi.zhihu.com/authorize"
_TOKEN_URL = "https://openapi.zhihu.com/access_token"
_USER_API = "https://developer.zhihu.com/api/v1"


class ZhihuOAuthError(Exception):
    """知乎 OAuth 或用户数据调用失败。上层据此 fallback 到「先聊两句」。"""


class ZhihuOAuthUser:
    """一次授权拿到的当前用户公开数据。字段允许为空，拿到什么用什么。"""

    def __init__(
        self,
        *,
        followees: list[str],
        favorites: list[str],
        contents: list[str],
    ) -> None:
        self.followees = followees
        self.favorites = favorites
        self.contents = contents


class ZhihuOAuth:
    """知乎 OAuth 应用集成 + 授权用户数据读取。"""

    @property
    def configured(self) -> bool:
        return settings.zhihu_oauth_configured

    def authorize_url(self, state: str) -> str:
        """构造知乎授权页 URL。redirect_uri 需 URL 编码。

        注意：知乎当前协议不支持 scope / PKCE，response_type 固定 code。
        """
        import urllib.parse

        params = {
            "redirect_uri": settings.zhihu_oauth_redirect_uri,
            "app_id": settings.zhihu_app_id,
            "response_type": "code",
            "state": state,
        }
        qs = urllib.parse.urlencode(params)
        return f"{_AUTHORIZE_URL}?{qs}"

    async def exchange_token(self, code: str) -> str:
        """用 authorization_code 换 access_token。返回 access_token。

        app_key 只在这里、只在后端使用，绝不进入浏览器/URL/日志。
        """
        import httpx

        if not self.configured:
            raise ZhihuOAuthError("知乎 OAuth 未配置")

        payload = {
            "app_id": settings.zhihu_app_id,
            "app_key": settings.zhihu_app_key,
            "grant_type": "authorization_code",
            "redirect_uri": settings.zhihu_oauth_redirect_uri,
            "code": code,
        }
        async with httpx.AsyncClient(timeout=settings.zhihu_timeout_seconds) as client:
            try:
                resp = await client.post(
                    _TOKEN_URL,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except Exception as exc:  # noqa: BLE001 - 统一转为业务异常
                logger.warning("oauth token exchange failed reason=%s", type(exc).__name__)
                raise ZhihuOAuthError(f"换取 access_token 失败：{type(exc).__name__}") from exc

        if resp.status_code >= 400:
            _log_safe("token_exchange", f"http={resp.status_code}")
            raise ZhihuOAuthError("知乎拒绝授权码或 OAuth 配置不正确")

        data = _as_json(resp, "token_exchange")
        token = _extract_access_token(data)
        if not token:
            # 只记录结构概要（键名 + 业务 code），绝不记录 token / secret。
            _log_safe("token_exchange", f"no_access_token {_describe_response(data)}")
            raise ZhihuOAuthError("知乎未返回 access_token")
        logger.info("oauth token exchange ok")
        return token

    async def fetch_user(self, oauth_token: str) -> ZhihuOAuthUser:
        """读取当前 OAuth 用户的公开数据（followees / favlists / contents）。"""
        import httpx

        headers = _user_headers(oauth_token)
        async with httpx.AsyncClient(timeout=settings.zhihu_timeout_seconds) as client:
            followees, favorites, contents = [], [], []
            try:
                followees = await _fetch_followees(client, headers)
                favorites = await _fetch_favorites(client, headers)
                contents = await _fetch_contents(client, headers)
            except ZhihuOAuthError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("oauth user fetch failed reason=%s", type(exc).__name__)
                raise ZhihuOAuthError(
                    f"读取授权用户数据失败：{type(exc).__name__}"
                ) from exc

        return ZhihuOAuthUser(
            followees=followees,
            favorites=favorites,
            contents=contents,
        )


# --------------------------------------------------------------------------
# 内部工具
# --------------------------------------------------------------------------


def _user_headers(oauth_token: str) -> dict[str, str]:
    """用户数据 API 公共头。

    Authorization 是调用方凭据（服务器 Access Secret）；
    X-OAuth-Token 才是「当前代表哪个用户」。
    """
    return {
        "Authorization": f"Bearer {settings.zhihu_access_secret}",
        "X-OAuth-Token": oauth_token,
        "X-Request-Timestamp": str(int(time.time())),
        "Content-Type": "application/json",
    }


async def _fetch_followees(client, headers: dict[str, str]) -> list[str]:
    resp = await client.get(
        f"{_USER_API}/user/followees", params={"Limit": 20}, headers=headers
    )
    if resp.status_code >= 400:
        _log_safe("followees", f"http={resp.status_code}")
        return []
    data = _as_json(resp, "followees")
    items = _items(data)
    out: list[str] = []
    for it in items:
        name = str(it.get("Fullname") or "").strip()
        headline = str(it.get("Headline") or "").strip()
        if name:
            out.append(f"{name}：{headline}" if headline else name)
    return out


async def _fetch_favorites(client, headers: dict[str, str]) -> list[str]:
    resp = await client.get(
        f"{_USER_API}/user/favlists", params={"Limit": 20}, headers=headers
    )
    if resp.status_code >= 400:
        _log_safe("favlists", f"http={resp.status_code}")
        return []
    data = _as_json(resp, "favlists")
    out: list[str] = []
    for it in _items(data):
        title = str(it.get("Title") or "").strip()
        if title and title != "我的收藏":
            out.append(title)
    return out


async def _fetch_contents(client, headers: dict[str, str]) -> list[str]:
    resp = await client.get(
        f"{_USER_API}/user/contents",
        params={"ContentType": "all", "Limit": 20, "SortField": "ts", "SortOrder": "desc"},
        headers=headers,
    )
    if resp.status_code >= 400:
        _log_safe("contents", f"http={resp.status_code}")
        return []
    data = _as_json(resp, "contents")
    out: list[str] = []
    for it in _items(data):
        title = str(it.get("Title") or it.get("Summary") or "").strip()
        if title:
            out.append(title[:60])
    return out


def _items(data: dict[str, Any]) -> list[Any]:
    """兼容 Data 为 list 或 {Items:[...]} 两种形态。"""
    raw = data.get("Data")
    if isinstance(raw, list):
        return raw
    return (raw or {}).get("Items") or []


def _extract_access_token(data: dict[str, Any]) -> str:
    """从 token 响应中稳健地取出 access_token。

    知乎真实响应可能把 access_token 放在顶层、Data 内、或大小写变体。
    这里做多层查找，绝不返回其它字段（如 app_key）误当 token。
    """
    # 候选键名（按优先级）
    for key in ("access_token", "accessToken", "AccessToken"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # 常见嵌套形态：data["Data"]["access_token"] 或 data["data"][...]
    for nest_key in ("Data", "data"):
        inner = data.get(nest_key)
        if isinstance(inner, dict):
            for key in ("access_token", "accessToken", "AccessToken"):
                v = inner.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()

    return ""


def _describe_response(data: dict[str, Any]) -> str:
    """生成安全的结构概要：只输出顶层键名、业务 code 与 data 的安全摘要。

    绝不输出 access_token / app_key / secret 等敏感值。
    """
    top_keys = list(data.keys())
    code = data.get("code", data.get("Code", data.get("Message", "")))
    has_token = bool(_extract_access_token(data))
    return f"keys={top_keys} code={code!r} has_token={has_token} data={_describe_data(data.get('data', data.get('Data')))!r}"


def _describe_data(node: Any, depth: int = 0) -> Any:
    """递归安全摘要：字符串值只保留短文本或长度，疑似 token/secret 一律脱敏。"""
    if depth > 2:
        return "[...]"
    if isinstance(node, str):
        s = node.strip()
        if not s:
            return ""
        # 疑似 token / secret：长 hex 或 base64 串，只记长度
        if len(s) > 48 and _looks_like_secret(s):
            return f"[len={len(s)}]"
        return s if len(s) <= 60 else s[:60] + "…"
    if isinstance(node, dict):
        return {k: _describe_data(v, depth + 1) for k, v in list(node.items())[:12]}
    if isinstance(node, list):
        return [_describe_data(v, depth + 1) for v in node[:6]]
    return node


def _looks_like_secret(s: str) -> bool:
    """判断一个长字符串是否像 token/secret（用于脱敏，避免误记）。"""
    import re

    if re.fullmatch(r"[0-9a-fA-F]{24,}", s):
        return True
    if re.fullmatch(r"[A-Za-z0-9_\-\.]{24,}", s):
        return True
    return False


def _as_json(resp, stage: str) -> dict[str, Any]:
    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        _log_safe(stage, "bad_json")
        raise ZhihuOAuthError(f"{stage} 返回无法解析") from exc
    if not isinstance(data, dict):
        _log_safe(stage, "not_dict")
        raise ZhihuOAuthError(f"{stage} 返回结构异常")
    return data


def _log_safe(stage: str, detail: str) -> None:
    """只记录阶段与类型，绝不记录 token / secret。"""
    logger.warning("oauth user stage=%s failed=%s", stage, detail)


zhihu_oauth = ZhihuOAuth()
