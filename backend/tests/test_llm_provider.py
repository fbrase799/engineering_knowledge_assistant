"""LLM provider resolution: OpenAI platform vs Azure."""

from __future__ import annotations

from backend.src.config import Settings


def test_auto_prefers_openai_platform_key():
    settings = Settings(
        openai_api_key="sk-test",
        azure_openai_api_key="azure-key",
        azure_openai_endpoint="https://example.openai.azure.com/",
        llm_provider="auto",
    )
    assert settings.resolved_llm_provider == "openai"
    assert settings.llm_configured is True


def test_auto_falls_back_to_azure():
    settings = Settings(
        openai_api_key=None,
        azure_openai_api_key="azure-key",
        azure_openai_endpoint="https://example.openai.azure.com/",
        llm_provider="auto",
    )
    assert settings.resolved_llm_provider == "azure"


def test_explicit_azure_ignores_openai_key():
    settings = Settings(
        openai_api_key="sk-test",
        azure_openai_api_key="azure-key",
        azure_openai_endpoint="https://example.openai.azure.com/",
        llm_provider="azure",
    )
    assert settings.resolved_llm_provider == "azure"
