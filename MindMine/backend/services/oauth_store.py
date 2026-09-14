"""OAuth 流程 state 的生成与校验（无状态签名方案）。

为什么不能用进程内 dict：
    线上 Railway 可能有多个副本（replica）或部署期间进程重启。
    authorize 把 state 存进「实例 A」的内存，callback 却可能命中
    「实例 B」，导致 state 找不到 → invalid_state。

方案：
    state 不再落内存，而是生成一个带 HMAC 签名的 token：
        state = base64url(payload) + "." + hmac(payload)
    payload 内只放 return_to 与过期时间（都不是敏感信息）。
    callback 时校验签名与过期，无需查询任何共享存储，
    因此多实例 / 重启都安全。

安全边界：
    - 签名密钥使用服务器持有的 zhihu_app_key（Railway 环境变量，
      所有副本一致），绝不写入源码、不进入日志。
    - state 短 TTL，超时即失效。
    - 知乎的 authorization_code 本身一次性，进一步限制了重放风险。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time

from config import settings

logger = logging.getLogger("mindmine.oauth_store")

# state 有效时长（秒）。超过即视为过期，防止旧链接被重放。
_STATE_TTL_SECONDS = 600


class OAuthFlow:
    """一次待完成的 OAuth 授权请求（解析结果）。"""

    def __init__(self, state: str, return_to: str) -> None:
        self.state = state
        self.return_to = return_to


def _signing_key() -> bytes:
    """签名密钥：服务器持有的 app_key。所有副本一致。"""
    return settings.zhihu_app_key.encode("utf-8")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(body: str) -> str:
    return hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).hexdigest()


class OAuthStore:
    """无状态 OAuth state 生成与校验。"""

    def create(self, return_to: str) -> str:
        """生成一个签名 state，绑定 return_to 与过期时间。"""
        payload = json.dumps(
            {"return_to": return_to, "exp": int(time.time()) + _STATE_TTL_SECONDS},
            separators=(",", ":"),
            ensure_ascii=True,
        )
        body = _b64e(payload.encode("utf-8"))
        sig = _sign(body)
        state = f"{body}.{sig}"
        logger.info("oauth state issued sig=%s…", sig[:8])
        return state

    def consume(self, state: str) -> OAuthFlow | None:
        """校验签名与过期，返回 OAuthFlow；无效返回 None。"""
        if not state or "." not in state:
            logger.warning("oauth state consume failed reason=malformed")
            return None

        body, sig = state.rsplit(".", 1)
        expected = _sign(body)
        if not hmac.compare_digest(sig, expected):
            logger.warning("oauth state consume failed reason=bad_signature")
            return None

        try:
            payload = json.loads(_b64d(body).decode("utf-8"))
            return_to = payload.get("return_to") or "/portrait"
            exp = int(payload.get("exp") or 0)
        except Exception:  # noqa: BLE001
            logger.warning("oauth state consume failed reason=bad_payload")
            return None

        if exp < int(time.time()):
            logger.warning("oauth state consume failed reason=expired")
            return None

        logger.info("oauth state consumed")
        return OAuthFlow(state=state, return_to=return_to)


oauth_store = OAuthStore()
