"""STT backend registry - 管理 AssemblyAI / Whisper 降级"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class STTBackend:
    """STT 后端描述"""
    name: str
    websocket_url: str
    headers: dict[str, str]
    timeout: float


class STTBackendRouter:
    """STT 后端路由器 - 统一管理 primary/fallback"""

    def __init__(self, cfg: Any):
        self.config = cfg
        self.backends = self._build_backends(cfg)

    def _build_backends(self, cfg: Any) -> list[STTBackend]:
        """构建后端列表（AssemblyAI 优先，Whisper 降级）"""
        backends: list[STTBackend] = []

        # AssemblyAI（优先）
        assemblyai_key = (getattr(cfg, "ASSEMBLYAI_API_KEY", "") or "").strip()
        if assemblyai_key:
            backends.append(
                STTBackend(
                    name="assemblyai",
                    websocket_url=getattr(cfg, "ASSEMBLYAI_STREAMING_URL", ""),
                    headers={"Authorization": assemblyai_key},
                    timeout=getattr(cfg, "ASSEMBLYAI_CONNECTION_TIMEOUT", 3.0),
                )
            )

        # Whisper（降级）
        whisper_enabled = getattr(cfg, "WHISPER_ENABLED", False)
        whisper_url = (getattr(cfg, "WHISPER_SERVICE_URL", "") or "").strip()
        if whisper_enabled and whisper_url:
            backends.append(
                STTBackend(
                    name="whisper",
                    websocket_url=whisper_url,
                    headers={},  # Whisper 不需要认证头
                    timeout=getattr(cfg, "WHISPER_TIMEOUT", 10.0),
                )
            )

        return backends

    @property
    def primary(self) -> Optional[STTBackend]:
        """主后端（第一个可用）"""
        return self.backends[0] if self.backends else None

    @property
    def fallback(self) -> Optional[STTBackend]:
        """降级后端（第二个可用）"""
        return self.backends[1] if len(self.backends) > 1 else None
