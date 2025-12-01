"""LLM backend registry."""

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class LLMBackend:
    """描述一个可用的 LLM 端点"""

    name: str
    client: AsyncOpenAI
    model: str


class LLMBackendRouter:
    """集中管理 OpenRouter / vLLM 后端，负责降级"""

    def __init__(self, cfg: Any):
        self.config = cfg
        self.backends = self._build_backends()

    def _build_backends(self) -> List[LLMBackend]:
        """根据配置构建后端列表（OpenRouter 优先，vLLM 备选）"""
        backends: List[LLMBackend] = []

        openrouter_key = (getattr(self.config, "OPENROUTER_API_KEY", "") or "").strip()
        if openrouter_key:
            backends.append(
                LLMBackend(
                    name="openrouter",
                    client=AsyncOpenAI(
                        api_key=openrouter_key,
                        base_url=getattr(self.config, "OPENROUTER_BASE_URL", ""),
                        default_headers=self._build_default_headers(),
                    ),
                    model=getattr(self.config, "OPENROUTER_MODEL", ""),
                )
            )

        vllm_base = (getattr(self.config, "VLLM_BASE_URL", "") or "").strip()
        if vllm_base:
            vllm_key = (getattr(self.config, "VLLM_API_KEY", "") or "EMPTY").strip() or "EMPTY"
            vllm_model = getattr(self.config, "VLLM_MODEL", "") or getattr(
                self.config, "OPENROUTER_MODEL", ""
            )
            backends.append(
                LLMBackend(
                    name="vllm",
                    client=AsyncOpenAI(api_key=vllm_key, base_url=vllm_base.rstrip("/")),
                    model=vllm_model,
                )
            )

        return backends

    def _build_default_headers(self) -> Dict[str, str]:
        """构建 OpenRouter 默认请求头"""
        headers: Dict[str, str] = {}
        site_url = getattr(self.config, "OPENROUTER_SITE_URL", "")
        site_name = getattr(self.config, "OPENROUTER_SITE_NAME", "")
        if site_url:
            headers["HTTP-Referer"] = site_url
        if site_name:
            headers["X-Title"] = site_name
        return headers

    def _ordered_backends(self, primary: Optional[LLMBackend] = None) -> List[LLMBackend]:
        """返回带优先级的后端列表"""
        if not primary:
            return list(self.backends)
        ordered = [primary]
        ordered.extend([backend for backend in self.backends if backend.name != primary.name])
        return ordered

    async def call_with_fallback(
        self,
        *,
        messages: List[Dict[str, Any]],
        primary: Optional[LLMBackend] = None,
        **kwargs: Any,
    ) -> Tuple[Any, LLMBackend]:
        """顺序尝试所有在线 LLM，保证 OpenRouter 不可用时自动降级 vLLM"""
        errors: List[str] = []
        for backend in self._ordered_backends(primary):
            try:
                response = await backend.client.chat.completions.create(
                    model=backend.model, messages=messages, **kwargs
                )
                return response, backend
            except Exception as exc:  # pragma: no cover - 网络/服务异常
                err_msg = f"{backend.name}: {type(exc).__name__}: {exc}"
                logger.error("LLM 调用失败，尝试下一个备选：%s", err_msg)
                errors.append(err_msg)
                continue
        raise RuntimeError("; ".join(errors) if errors else "没有可用的 LLM 提供者")
