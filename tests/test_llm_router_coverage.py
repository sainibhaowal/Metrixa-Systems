from __future__ import annotations

import json

import pytest

from metrixa_engine.llm.router import (
    LLMRouter,
    clean_extracted_person_name,
    extract_deterministic_german_kpis,
)


class Response:
    def __init__(self, status=200, payload=None):
        self.status_code, self.payload = status, payload or {}

    def json(self):
        return self.payload


class ClientContext:
    response = None
    error = None
    calls = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.response

    async def post(self, *args, **kwargs):
        self.calls.append((args, kwargs, self.kwargs))
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_local_probe_cache_and_provider_configuration(monkeypatch):
    import metrixa_engine.llm.router as module

    router = LLMRouter()
    assert router.get_provider_config("") is None
    assert router.get_provider_config("unknown") is None
    settings = module.settings
    for provider, field in (
        ("openai", "openai_api_key"),
        ("deepseek", "deepseek_api_key"),
        ("nvidia_nim", "nvidia_nim_api_key"),
        ("gemini", "gemini_api_key"),
    ):
        monkeypatch.setattr(settings, field, "key")
        assert router.get_provider_config(provider)["provider"] == provider
    monkeypatch.setattr(settings, "ollama_model", "")
    assert router.get_provider_config("ollama")["model"] == "llama3.2"
    monkeypatch.setattr(settings, "llamacpp_model", "")
    assert router.get_provider_config("local_llamacpp")["model"] == "local-model"
    monkeypatch.setattr(settings, "lmstudio_model", "")
    assert router.get_provider_config("lm_studio")["model"] == "lfm3-1.7b"

    ClientContext.response = Response(200)
    ClientContext.error = None
    monkeypatch.setattr(module.httpx, "AsyncClient", ClientContext)
    assert await router._probe_local_server("http://localhost:1234/") is True
    ClientContext.response = Response(503)
    assert await router._probe_local_server("http://localhost:1235") is False
    # Cached results do not make another request.
    assert await router._probe_local_server("http://localhost:1234/") is True
    ClientContext.error = OSError("offline")
    assert await router._probe_local_server("http://localhost:1236") is False

    monkeypatch.setattr(settings, "default_llm_provider", "deterministic")
    assert await router.resolve_active_provider(None) is None
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "")
    monkeypatch.setattr(settings, "ollama_model", "local")
    monkeypatch.setattr(router, "_probe_local_server", lambda url: _true())
    auto = await router.resolve_active_provider("auto_fallback")
    assert auto and auto["provider"] == "ollama"
    monkeypatch.setattr(router, "_probe_local_server", lambda url: _false())
    assert await router.resolve_active_provider("ollama") is None
    assert await router.resolve_active_provider("unsupported") is None
    monkeypatch.setattr(settings, "openai_api_key", "cloud-key")
    assert (await router.resolve_active_provider("openai"))["provider"] == "openai"


async def _true():
    return True


async def _false():
    return False


def test_person_name_cleaning_and_deterministic_default_assumptions():
    assert clean_extracted_person_name("") is None
    assert clean_extracted_person_name("Unsere Werte") is None
    assert clean_extracted_person_name("Ihre Immobilie") is None
    assert (
        clean_extracted_person_name("Herr Max Mustermann, Tel: 030123")
        == "Max Mustermann"
    )
    assert clean_extracted_person_name("Max 123 Test") is None
    assert (
        clean_extracted_person_name("Max Mustermann Geschäftsführer Bereich")
        == "Max Mustermann Geschäftsführer Bereich"
    )
    assert (
        clean_extracted_person_name("Max Mustermann Geschäftsführer Bereich Alpha")
        is None
    )
    assert clean_extracted_person_name("Max") is None
    grounded = extract_deterministic_german_kpis(
        "Beispiel GmbH",
        "Geschäftsführer Unsere Werte. Geschäftsführer Max Mustermann. Wir verwalten 2.000 Einheiten.",
        [],
        [],
        False,
        [],
        [],
    )
    assert grounded.exact_units_managed == 2000
    assert [person.full_name for person in grounded.decision_makers] == [
        "Max Mustermann"
    ]
    assert "source-listed decision maker" in grounded.qualification_reasoning
    assert "verified decision maker" not in grounded.qualification_reasoning
    result = extract_deterministic_german_kpis(
        company_name="Berliner Verwaltung GmbH",
        combined_text="Berliner Verwaltung GmbH",
        dom_erp_list=[],
        dom_metering_list=[],
        dom_has_portal=False,
        dom_emails=[],
        dom_linkedin_urls=[],
    )
    assert not result.manages_weg and not result.manages_miet
    assert "Active Berlin property management company" in result.qualification_reasoning
    no_reason = extract_deterministic_german_kpis(
        "Gewerbeverwaltung GmbH", "Gewerbeverwaltung", [], [], False, [], []
    )
    assert (
        no_reason.qualification_reasoning
        == "Active Berlin property management company (GmbH)."
    )
    assert (
        extract_deterministic_german_kpis(
            "Makler", "Makler", [], [], False, [], []
        ).is_actual_hausverwaltung
        is True
    )


def test_team_page_roles_belong_to_the_preceding_person():
    text = (
        "Martin Thurnbacher\nInhaber und Geschäftsführer\n"
        "Michael Wolf\nProkurist\nAnnika Hauß-Thurnbacher\nProkuristin\n"
        "Jacqueline Spitzner\n\u00adAssistentin der Geschäftsführung\n"
        "Juliane Seifert\nLeiterin Buchhaltung"
    )
    result = extract_deterministic_german_kpis(
        "Firma GmbH", text, [], [], False, [], []
    )
    people = {person.full_name: person.role for person in result.decision_makers}
    assert people == {
        "Martin Thurnbacher": "Geschäftsführer",
        "Michael Wolf": "Prokurist",
        "Annika Hauß-Thurnbacher": "Prokurist",
    }
    repeated = extract_deterministic_german_kpis(
        "Firma GmbH",
        "Geschäftsführer: Max Mustermann\nMax Mustermann\nGeschäftsführer",
        [],
        [],
        False,
        [],
        [],
    )
    assert [person.full_name for person in repeated.decision_makers] == [
        "Max Mustermann"
    ]


def test_generic_hausverwaltung_is_not_a_rental_management_signal():
    no_rental = extract_deterministic_german_kpis(
        "Firma GmbH", "Hausverwaltung und WEG-Verwaltung", [], [], False, [], []
    )
    assert no_rental.manages_weg and not no_rental.manages_miet
    rental = extract_deterministic_german_kpis(
        "Firma GmbH", "Wir übernehmen die Mietobjektverwaltung.", [], [], False, [], []
    )
    assert rental.manages_miet


@pytest.mark.asyncio
async def test_llm_success_grounding_fences_reasoning_and_fallbacks(monkeypatch):
    import metrixa_engine.llm.router as module

    router = LLMRouter()
    settings = module.settings
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_model", "o3-mini")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.example/v1/")
    monkeypatch.setattr(settings, "default_llm_provider", "openai")
    monkeypatch.setattr(module.httpx, "AsyncClient", ClientContext)
    ClientContext.error = None
    source = "Impressum: Hausverwaltung GmbH, HRB 123 B. Wir verwalten 3.400 Wohneinheiten. Geschäftsführer Max Mustermann. Casavi Kundenportal."
    valid = {
        "is_actual_hausverwaltung": True,
        "legal_form": None,
        "exact_units_managed": 3400,
        "units_evidence_quote": "3.400 Wohneinheiten",
        "decision_makers": [
            {
                "full_name": "Max Mustermann",
                "source_quote": "Geschäftsführer Max Mustermann",
            }
        ],
        "software_mentioned": [],
        "has_online_portal": False,
    }
    ClientContext.response = Response(
        payload={
            "choices": [
                {
                    "message": {
                        "content": "```json\n"
                        + json.dumps(valid, ensure_ascii=False)
                        + "\n```"
                    }
                }
            ],
            "usage": {"prompt_tokens": 22, "completion_tokens": 11},
        }
    )
    extraction, audit = await router.extract_kpis_with_llm_and_deterministic_guard(
        "Alpha GmbH",
        "https://alpha.de",
        source,
        ["Casavi"],
        [],
        False,
        [],
        [],
        "openai",
    )
    assert extraction.exact_units_managed == 3400
    assert extraction.decision_makers[0].full_name == "Max Mustermann"
    assert extraction.commercial_register_id == "HRB 123 B"
    assert extraction.has_online_portal is True
    assert extraction.software_mentioned == ["Casavi"]
    assert (
        audit["provider"] == "openai"
        and audit["schema_valid"]
        and not audit["hallucination_blocked"]
    ), audit
    assert ClientContext.calls[-1][1]["json"]["max_completion_tokens"] == 1600
    assert "temperature" not in ClientContext.calls[-1][1]["json"]

    # Unverifiable counts and names are rejected and a grounded deterministic name is retained.
    hallucinated = {
        "exact_units_managed": 9999,
        "decision_makers": [{"full_name": "John Fake"}],
    }
    ClientContext.response = Response(
        payload={"choices": [{"message": {"content": json.dumps(hallucinated)}}]}
    )
    extraction, audit = await router.extract_kpis_with_llm_and_deterministic_guard(
        "Alpha GmbH", "https://alpha.de", source, [], [], False, [], [], "openai"
    )
    assert extraction.exact_units_managed == 3400
    assert extraction.decision_makers[0].full_name == "Max Mustermann"
    assert audit["hallucination_blocked"] is True

    # Reasoning models may place the answer in reasoning_content, with estimates when usage is absent.
    monkeypatch.setattr(settings, "openai_model", "gpt-4o-mini")
    ClientContext.response = Response(
        payload={
            "choices": [
                {
                    "message": {
                        "reasoning_content": json.dumps(
                            {"is_actual_hausverwaltung": True}
                        )
                    }
                }
            ]
        }
    )
    _, audit = await router.extract_kpis_with_llm_and_deterministic_guard(
        "Alpha GmbH", "https://alpha.de", source, [], [], False, [], [], "openai"
    )
    assert audit["provider"] == "openai"
    assert "max_tokens" in ClientContext.calls[-1][1]["json"]

    # Output text alternative and invalid provider output both fall back safely.
    ClientContext.response = Response(
        payload={"choices": [{"text": json.dumps({"is_actual_hausverwaltung": True})}]}
    )
    assert (
        await router.extract_kpis_with_llm_and_deterministic_guard(
            "Alpha", "", source, [], [], False, [], [], "openai"
        )
    )[1]["provider"] == "openai"
    for content in ("no json", "{bad json}"):
        ClientContext.response = Response(
            payload={"choices": [{"message": {"content": content}}]}
        )
        _, audit = await router.extract_kpis_with_llm_and_deterministic_guard(
            "Alpha GmbH", "https://alpha.de", source, [], [], False, [], [], "openai"
        )
        assert audit["provider"] == "deterministic_fallback"
    ClientContext.response = Response(503)
    _, audit = await router.extract_kpis_with_llm_and_deterministic_guard(
        "Alpha GmbH", "https://alpha.de", source, [], [], False, [], [], "openai"
    )
    assert audit["provider"] == "deterministic_fallback"
    ClientContext.error = OSError("offline")
    _, audit = await router.extract_kpis_with_llm_and_deterministic_guard(
        "Alpha GmbH", "https://alpha.de", source, [], [], False, [], [], "openai"
    )
    assert audit["provider"] == "deterministic_fallback"
    ClientContext.error = None
    # Short source bypasses the external provider even when configured.
    _, audit = await router.extract_kpis_with_llm_and_deterministic_guard(
        "Alpha", "", "short", [], [], False, [], [], "openai"
    )
    assert audit["provider"] == "deterministic_german_nlp"
