"""LLM backend registry."""

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI, APITimeoutError, APIConnectionError, RateLimitError, APIStatusError

logger = logging.getLogger(__name__)


@dataclass
class LLMBackend:
    """描述一个可用的 LLM 端点"""

    name: str
    client: AsyncOpenAI
    model: str
    timeout: float = 30.0  # 默认超时 30 秒


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
                    timeout=getattr(self.config, "OPENROUTER_TIMEOUT", 5.0),  # OpenRouter 5秒超时
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
                    timeout=getattr(self.config, "VLLM_TIMEOUT", 10.0),  # vLLM 10秒超时
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

    def _is_retriable_error(self, exc: Exception) -> bool:
        """判断错误是否可重试（应该降级到下一个后端）"""
        # 超时错误 - 主要目标
        if isinstance(exc, APITimeoutError):
            return True

        # 网络连接错误
        if isinstance(exc, APIConnectionError):
            return True

        # 429 限流错误
        if isinstance(exc, RateLimitError):
            return True

        # 5xx 服务器错误
        if isinstance(exc, APIStatusError) and exc.status_code >= 500:
            return True

        # 其他错误（如 400 参数错误）不降级
        return False

    async def call_with_fallback(
        self,
        *,
        messages: List[Dict[str, Any]],
        primary: Optional[LLMBackend] = None,
        **kwargs: Any,
    ) -> Tuple[Any, LLMBackend]:
        """顺序尝试所有在线 LLM，支持超时降级"""
        errors: List[str] = []

        for backend in self._ordered_backends(primary):
            try:
                logger.info(f"调用 {backend.name}，超时设置: {backend.timeout}秒")

                # 关键：传入 timeout 参数启用超时检测
                response = await backend.client.chat.completions.create(
                    model=backend.model,
                    messages=messages,
                    timeout=backend.timeout,  # 启用超时
                    **kwargs
                )

                logger.info(f"✅ {backend.name} 调用成功")
                return response, backend

            except Exception as exc:  # pragma: no cover - 网络/服务异常
                # 使用错误分类判断是否应该降级
                if self._is_retriable_error(exc):
                    logger.warning(
                        f"⚠️ {backend.name} 可重试错误: {type(exc).__name__}: {exc}"
                    )
                    errors.append(f"{backend.name}: {type(exc).__name__}")
                    continue  # 尝试下一个后端
                else:
                    # 不可重试错误（如 400 参数错误），直接抛出
                    logger.error(f"❌ {backend.name} 不可重试错误: {exc}")
                    raise

        # 所有后端失败
        raise RuntimeError(f"所有 LLM 后端失败: {'; '.join(errors)}")
