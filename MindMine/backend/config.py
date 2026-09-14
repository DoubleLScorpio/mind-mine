"""集中配置。

原则（AGENTS.md）：
1. 环境变量只能通过本模块的 Settings 读取，
   业务代码禁止直接调用 os.environ.get。
2. 每个外部依赖都能独立 fallback —— 不是「全 Real」或「全 Mock」二选一。
3. 密钥只从环境变量/.env 读取，绝不写入源码或提交 Git。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderMode = Literal["real", "mock", "auto"]


class Settings(BaseSettings):
    """运行时配置。

    provider 三态：
      real  强制真实能力，失败就报错（用于排查）
      mock  强制演示数据（Demo 兜底，永远可用）
      auto  优先真实，失败自动 fallback 到 mock（Demo 默认）
    """

    model_config = SettingsConfigDict(
        env_file=".env",
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
    # 由宿主注入的内置 CLI 绝对路径；留空则用 skill 的 run.sh 解析
    zhihu_cli_path: str = (
        "/Applications/看山工作台.app/Contents/Resources/"
        "cli-bundle/zhihu/current/zhihu-cli"
    )
    zhihu_timeout_seconds: float = 20.0

    # ---------- 其他 ----------
    log_level: str = "INFO"
    # 开发模式记录 provider / latency / fallback，不记录任何凭据
    verbose_provider_log: bool = True

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.strip())

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
