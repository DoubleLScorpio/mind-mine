"""统一 LLM 服务。

业务模块只依赖本文件暴露的接口，不关心背后是哪家模型。
接任意兼容 OpenAI 协议的服务（OpenAI / 火山方舟 / DeepSeek / Moonshot …）。

两条硬约束：
1. 关键模块必须用 generate_structured + Pydantic，不解析自由文本。
2. 所有调用都有 timeout；失败 retry 一次，再失败抛 LLMUnavailable，
   由上层 fallback 到 Demo 内容 —— 绝不让用户无限等待。
"""

from __future__ import annotations

import json
import logging
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from config import settings

logger = logging.getLogger("mindmine.llm")

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    """真实 LLM 不可用。上层据此 fallback，不把错误栈暴露给用户。"""


class LLMService:
    """兼容 OpenAI 协议的 LLM 客户端。"""

    def __init__(self) -> None:
        self._client = None

    # ------------------------------------------------------------------
    # 客户端
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is not None:
            return self._client

        if not settings.llm_configured:
            raise LLMUnavailable("LLM_API_KEY 未配置")

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailable(f"openai 包不可用：{exc}") from exc

        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,  # 重试由本类控制，便于记录 latency
        )
        return self._client

    @property
    def available(self) -> bool:
        return settings.llm_mode() == "real" and settings.llm_configured

    # ------------------------------------------------------------------
    # 纯文本
    # ------------------------------------------------------------------

    async def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 600,
        stage: str = "-",
    ) -> str:
        client = self._get_client()
        last_err: Exception | None = None

        for attempt in range(settings.llm_max_retries + 1):
            t0 = time.perf_counter()
            try:
                resp = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = (resp.choices[0].message.content or "").strip()
                _log_call(stage, "real", t0, ok=True)
                if not text:
                    raise LLMUnavailable("模型返回空内容")
                return text
            except Exception as exc:
                last_err = exc
                _log_call(stage, "real", t0, ok=False, err=exc, attempt=attempt)

        raise LLMUnavailable(f"{type(last_err).__name__}: {last_err}")

    # ------------------------------------------------------------------
    # 结构化输出
    # ------------------------------------------------------------------

    async def generate_structured(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        temperature: float = 0.4,
        max_tokens: int = 900,
        stage: str = "-",
    ) -> T:
        """返回已校验的 Pydantic 对象。

        优先用服务端 JSON mode；不支持时回退到「提示 + 宽松解析」。
        两种情况都必须通过 Pydantic 校验才算成功。
        """
        client = self._get_client()
        hint = (
            f"{system}\n\n"
            "只输出一个 JSON 对象，不要 Markdown 代码块，不要额外说明。\n"
            f"JSON Schema：{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        )

        last_err: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            t0 = time.perf_counter()
            try:
                kwargs: dict = dict(
                    model=settings.llm_model,
                    messages=[
                        {"role": "system", "content": hint},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                # 第一次尝试用 JSON mode；失败后退回普通模式
                if attempt == 0:
                    kwargs["response_format"] = {"type": "json_object"}

                resp = await client.chat.completions.create(**kwargs)
                raw = (resp.choices[0].message.content or "").strip()
                obj = schema.model_validate(_loads(raw))
                _log_call(stage, "real", t0, ok=True)
                return obj
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_err = exc
                _log_call(stage, "real", t0, ok=False, err=exc, attempt=attempt)
            except Exception as exc:
                last_err = exc
                _log_call(stage, "real", t0, ok=False, err=exc, attempt=attempt)

        raise LLMUnavailable(f"结构化输出失败 {type(last_err).__name__}: {last_err}")


def _loads(raw: str) -> dict:
    """宽松 JSON 解析：容忍代码块包裹和前后缀噪声。"""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if "```" in s[3:] else s[3:]
        s = s.removeprefix("json").strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start >= 0 and end > start:
            return json.loads(s[start : end + 1])
        raise


def _log_call(
    stage: str,
    provider: str,
    t0: float,
    *,
    ok: bool,
    err: Exception | None = None,
    attempt: int = 0,
) -> None:
    """记录 provider / latency / 成败。绝不记录密钥或完整 token。"""
    if not settings.verbose_provider_log:
        return
    ms = int((time.perf_counter() - t0) * 1000)
    if ok:
        logger.info("llm stage=%s provider=%s latency=%dms ok", stage, provider, ms)
    else:
        logger.warning(
            "llm stage=%s provider=%s latency=%dms attempt=%d failed=%s",
            stage,
            provider,
            ms,
            attempt,
            type(err).__name__ if err else "?",
        )


llm = LLMService()
