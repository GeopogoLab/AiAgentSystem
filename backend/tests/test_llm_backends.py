"""测试 LLM 后端路由"""
from types import SimpleNamespace

from backend.llm.backends import LLMBackendRouter


def _config(**kwargs):
    defaults = dict(
        OPENROUTER_API_KEY="",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        OPENROUTER_MODEL="meta-llama/llama-3.3-70b-instruct",
        OPENROUTER_SITE_URL="",
        OPENROUTER_SITE_NAME="",
        VLLM_BASE_URL="",
        VLLM_API_KEY="",
        VLLM_MODEL="",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_builds_openrouter_then_vllm_when_configured():
    cfg = _config(
        OPENROUTER_API_KEY="or-key",
        VLLM_BASE_URL="https://modal.example/v1",
        VLLM_API_KEY="vk",
        VLLM_MODEL="meta-llama/Llama-3.1-70B-Instruct",
    )

    router = LLMBackendRouter(cfg)

    assert [backend.name for backend in router.backends] == ["openrouter", "vllm"]
    assert router.backends[0].model == cfg.OPENROUTER_MODEL
    assert router.backends[1].model == cfg.VLLM_MODEL


def test_uses_openrouter_model_as_vllm_default_when_not_set():
    cfg = _config(
        OPENROUTER_API_KEY="or-key",
        VLLM_BASE_URL="https://modal.example/v1",
        VLLM_API_KEY="vk",
        VLLM_MODEL="",
    )

    router = LLMBackendRouter(cfg)

    assert len(router.backends) == 2
    assert router.backends[1].model == cfg.OPENROUTER_MODEL


def test_returns_empty_when_no_backends_configured():
    router = LLMBackendRouter(_config())
    assert router.backends == []
