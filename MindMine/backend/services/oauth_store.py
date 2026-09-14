"""OAuth 流程存储：把一次知乎授权请求绑定到「当前浏览器会话」。

为什么需要它：
    知乎授权回调实测不回传 state，所以不能只靠 query 里的 state 判断
    「这个 callback 是谁发起的」。我们改用 HttpOnly cookie 携带 state，
    callback 时校验 cookie.state == query 参数（若知乎回传）且 state 尚未消费。

隔离原则：
    state 随机生成，一次有效，绑定一个 return_to，
    callback 消费后立即失效。不同浏览器持有不同 cookie，
    因此 OAuth 身份不会跨会话污染。

Phase 1 用进程内存储。上线多实例时需换成 Redis 等共享存储。
"""

from __future__ import annotations

import logging
import secrets
import time

logger = logging.getLogger("mindmine.oauth_store")

# state 有效时长（秒）。超过即视为过期，防止旧链接被重放。
_STATE_TTL_SECONDS = 600


class OAuthFlow:
    """一次待完成的 OAuth 授权请求。"""

    def __init__(self, state: str, return_to: str) -> None:
        self.state = state
        self.return_to = return_to
        self.created_at = time.monotonic()

    def expired(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return now - self.created_at > _STATE_TTL_SECONDS


class OAuthStore:
    """进程内 OAuth flow 存储。"""

    def __init__(self) -> None:
        self._flows: dict[str, OAuthFlow] = {}

    def create(self, return_to: str) -> str:
        """新建一次授权请求，返回随机 state。"""
        state = secrets.token_urlsafe(32)
        self._flows[state] = OAuthFlow(state=state, return_to=return_to)
        logger.info("oauth flow created state=%s…", state[:8])
        return state

    def consume(self, state: str) -> OAuthFlow | None:
        """校验并消费一个 state。返回 None 表示无效、过期或已被使用。

        一旦消费成功，该 state 立即失效，无法被二次 callback 重放。
        """
        flow = self._flows.get(state)
        if flow is None:
            logger.warning("oauth flow consume failed state=%s… reason=unknown", state[:8])
            return None
        if flow.expired():
            self._flows.pop(state, None)
            logger.warning("oauth flow consume failed state=%s… reason=expired", state[:8])
            return None
        # 使用后立即失效
        self._flows.pop(state, None)
        logger.info("oauth flow consumed state=%s…", state[:8])
        return flow


oauth_store = OAuthStore()
