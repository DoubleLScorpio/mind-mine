"""集中配置。

原则（AGENTS.md）：
1. 环境变量只能通过本模块的 Settings 读取，
   业务代码禁止直接调用 os.environ.get。
2. 每个外部依赖都能独立 fallback —— 不是「全 Real」或「全 Mock」二选一。
3. 密钥只从环境变量/.env 读取，绝不写入源码或提交 Git。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderMode = Literal["real", "mock", "auto"]

# .env 必须按本文件位置解析为绝对路径。
# 用相对路径时，只有恰好从 backend/ 启动才能读到；
# 从仓库根或用 --app-dir 启动会静默读不到凭据，
# 于是 llm_configured=False，所有 Real 分支被悄悄封死。
ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    """运行时配置。

    provider 三态：
      real  强制真实能力，失败就报错（用于排查）
      mock  强制演示数据（Demo 兜底，永远可用）
      auto  优先真实，失败自动 fallback 到 mock（Demo 默认）
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- Provider 开关：每个外部依赖独立 fallback ----------
    llm_provider: ProviderMode = "auto"
    zhihu_provider: ProviderMode = "auto"
    profile_provider: ProviderMode = "auto"

    # ---------- LLM ----------
    # 兼容 OpenAI 协议的任意服务（含火山方舟 / DeepSeek / Moonshot 等）
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 24.0
    llm_max_retries: int = 1

    # ---------- 知乎 CLI ----------
    # 留空时回退到宿主内置 CLI 的默认路径（见 resolved_zhihu_cli_path）。
    # 注意：.env.example 里 ZHIHU_CLI_PATH= 是空值，会覆盖字段默认值，
    # 所以默认路径不能写在这里，必须在解析时兜底。
    zhihu_cli_path: str = ""
    zhihu_timeout_seconds: float = 20.0

    # ---------- 知乎 OAuth（用户登录） ----------
    # 关键区分：Access Secret 是「平台调用方」凭据，绝不代表当前访客。
    # 只有通过 OAuth 换取的 access_token（X-OAuth-Token）才代表当前授权用户。
    zhihu_access_secret: str = ""
    zhihu_app_id: str = ""
    zhihu_app_key: str = ""
    # 知乎授权完成后回调到后端的完整公开 URL（Railway），不是 localhost。
    zhihu_oauth_redirect_uri: str = ""
    # 前端公开地址（Vercel），callback 完成后 302 回这里。
    frontend_url: str = "http://localhost:5173"
    # 生产 HTTPS 下应置为 true，让 OAuth state cookie 只走 Secure。
    oauth_cookie_secure: bool = False

    # ---------- CORS ----------
    # 逗号分隔的前端 origin 白名单。不使用通配符 "*"。
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---------- 其他 ----------
    log_level: str = "INFO"
    # 开发模式记录 provider / latency / fallback，不记录任何凭据
    verbose_provider_log: bool = True

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.strip())

    @property
    def zhihu_oauth_configured(self) -> bool:
        """真实 OAuth 登录是否可用。

        Access Secret 是平台调用方凭据，只用于换取/携带用户 token；
        app_id + app_key 用于发起授权；redirect_uri 必须是非 localhost 的
        公开回调地址。任一缺失都视为 OAuth 未配置。
        """
        return bool(
            self.zhihu_app_id.strip()
            and self.zhihu_app_key.strip()
            and self.zhihu_access_secret.strip()
            and self.zhihu_oauth_redirect_uri.strip()
        )

    def llm_mode(self) -> Literal["real", "mock"]:
        """解析 LLM 的实际运行模式。

        auto 模式下没有凭据就退回 mock —— 保证 Demo 永远能跑。
        """
        if self.llm_provider == "mock":
            return "mock"
        if self.llm_provider == "real":
            return "real"
        return "real" if self.llm_configured else "mock"

    def zhihu_mode(self) -> Literal["real", "mock"]:
        if self.zhihu_provider == "mock":
            return "mock"
        return "real" if self.zhihu_provider == "real" else "real"

    # 宿主内置知乎 CLI 的默认位置。ZHIHU_CLI_PATH 为空时使用。
    DEFAULT_ZHIHU_CLI: ClassVar[str] = (
        "/Applications/看山工作台.app/Contents/Resources/"
        "cli-bundle/zhihu/current/zhihu-cli"
    )

    def resolved_zhihu_cli_path(self) -> str:
        """解析实际使用的 zhihu-cli 路径。

        .env.example 中 ZHIHU_CLI_PATH= 是空值，会覆盖字段默认值，
        因此必须在这里兜底，否则知乎能力会被静默关闭。
        """
        return self.zhihu_cli_path.strip() or self.DEFAULT_ZHIHU_CLI

    def cors_origin_list(self) -> list[str]:
        """解析 CORS 白名单。不使用通配符 "*"。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def masked_key(self) -> str:
        """只用于日志。永不输出完整密钥。"""
        k = self.llm_api_key.strip()
        if not k:
            return "(unset)"
        return f"{k[:4]}…{k[-2:]}" if len(k) > 8 else "(set)"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
