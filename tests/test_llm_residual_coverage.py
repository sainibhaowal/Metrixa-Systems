from __future__ import annotations

import pytest

from metrixa_engine.llm.router import LLMRouter, extract_deterministic_german_kpis


def test_deterministic_reasoning_employee_count_and_weg_only():
    result = extract_deterministic_german_kpis(
        "Weg Verwaltung GmbH",
        "Wir beschäftigen 12 Mitarbeiter für die WEG-Verwaltung.",
        [],
        [],
        False,
        [],
        [],
    )
    assert result.employee_count_mentioned == 12
    assert result.manages_weg is True and result.manages_miet is False
    assert "Team of 12 employees" in result.qualification_reasoning
    assert "active in WEG-Verwaltung" in result.qualification_reasoning


@pytest.mark.asyncio
async def test_local_provider_unreachable_and_cloud_autofallback(monkeypatch):
    import metrixa_engine.llm.router as module

    router = LLMRouter()
    monkeypatch.setattr(module.settings, "ollama_model", "llama-test")

    async def unreachable(url):
        return False

    monkeypatch.setattr(router, "_probe_local_server", unreachable)
    assert await router.resolve_active_provider("ollama") is None

    async def reachable(url):
        return True

    monkeypatch.setattr(router, "_probe_local_server", reachable)
    assert (await router.resolve_active_provider("ollama"))["provider"] == "ollama"

    monkeypatch.setattr(module.settings, "openai_api_key", "fake-test-key")
    resolved = await router.resolve_active_provider("auto_fallback")
    assert resolved and resolved["provider"] == "openai"
