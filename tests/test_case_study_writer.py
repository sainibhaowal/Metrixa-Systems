"""Case-study generation must stay bound to current Stage 3 evidence and SQLite facts."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from metrixa_engine.api import server
from metrixa_engine.config import settings
from metrixa_engine.db import Database
from metrixa_engine.llm import case_study_writer as writer_module
from metrixa_engine.llm.case_study_writer import (
    CaseStudyEvidenceUnavailable,
    CaseStudyNarrativeRejected,
    CaseStudyProviderUnavailable,
    CaseStudyWriter,
    CaseStudyWriterError,
)


def _seed_company(
    db: Database, *, with_page: bool = True, with_run: bool = False
) -> None:
    with db.connect() as conn:
        company_id = conn.execute(
            """
            INSERT INTO companies_golden (
                canonical_name, display_name, sources_csv, pipeline_stage,
                website_url, is_vdiv_member, updated_at
            ) VALUES ('Example Verwaltung', 'Example Verwaltung', 'test', 'SCORED',
                      'https://example.test', 1, 'now')
            """
        ).lastrowid
        if with_page:
            conn.execute(
                """
                INSERT INTO crawled_pages (
                    company_id,page_type,url,http_status,clean_markdown,
                    detected_erp_csv,detected_metering_csv,has_portal_link,crawled_at
                ) VALUES (?, 'portal',
                          'https://Example.test/portal?tracking=x#section',
                          200, 'portal and software signals', 'Domus', 'Ista', 1, '2026-11-10')
                """,
                (company_id,),
            )
            conn.execute(
                """
                INSERT INTO crawled_pages (
                    company_id,page_type,url,http_status,clean_markdown,
                    detected_erp_csv,has_portal_link,crawled_at
                ) VALUES (?, 'team', 'https://example.test/team', 200,
                          'team page', 'Casavi', 0, '2026-11-09')
                """,
                (company_id,),
            )
            conn.execute(
                """
                INSERT INTO crawled_pages (
                    company_id,page_type,url,http_status,detected_erp_csv,
                    has_portal_link,crawled_at
                ) VALUES (?, 'home', '', 200, 'Other ERP', 1, '2026-11-08')
                """,
                (company_id,),
            )
        if with_run:
            conn.execute(
                """
                INSERT INTO pipeline_runs (
                    run_id,run_number,trigger_type,status,started_at,finished_at,
                    summary_metrics_json
                ) VALUES ('run-current',1,'MANUAL_FULL','COMPLETED_WITH_WARNINGS',
                          'start','finish',?)
                """,
                (json.dumps({"warnings": ["source warning"]}),),
            )


class _FakeResponse:
    def __init__(self, status_code: int, data=None, parse_error: bool = False) -> None:
        self.status_code = status_code
        self.data = data
        self.parse_error = parse_error

    def json(self):
        if self.parse_error:
            raise ValueError("invalid JSON")
        return self.data


class _FakeAsyncClient:
    response = _FakeResponse(200, {})
    error = None
    posted = None

    def __init__(self, timeout: float) -> None:
        assert timeout == 45.0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, headers, json):
        type(self).posted = {"url": url, "headers": headers, "payload": json}
        if type(self).error:
            raise type(self).error
        return type(self).response


async def _resolve_provider(_provider=None):
    return {
        "provider": "test-provider",
        "base_url": "https://llm.test/v1",
        "api_key": "test-key",
        "model": "test-model",
    }


def test_evidence_packet_retrieves_unique_stage3_sources_and_latest_run(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "retrieval.db")
    _seed_company(db, with_run=True)
    with db.connect() as conn:
        company_id = conn.execute(
            "SELECT company_id FROM companies_golden WHERE canonical_name='Example Verwaltung'"
        ).fetchone()[0]
        conn.execute(
            "UPDATE companies_golden SET website_url='https://www.example.test' WHERE company_id=?",
            (company_id,),
        )
        conn.execute(
            "UPDATE crawled_pages SET url='https://www.Example.test/portal?tracking=x#section' "
            "WHERE company_id=? AND page_type='portal'",
            (company_id,),
        )
        conn.execute(
            """
            INSERT INTO crawled_pages (
                company_id,page_type,url,http_status,detected_erp_csv,crawled_at
            ) VALUES (?, 'portal', 'https://www.example.test/second', 200, 'Casavi',
                      '2026-11-09')
            """,
            (company_id,),
        )
        conn.execute(
            """
            INSERT INTO crawled_pages (
                company_id,page_type,url,http_status,detected_erp_csv,crawled_at
            ) VALUES (?, 'portal', 'https://external.example/portal', 200, 'Casavi',
                      '2026-11-08')
            """,
            (company_id,),
        )

    packet = CaseStudyWriter(db)._build_evidence_packet()

    assert packet["active_companies"] == 1
    assert packet["companies_with_website"] == 1
    assert packet["latest_run"]["run_id"] == "run-current"
    assert packet["latest_run_summary"]["warnings"] == ["source warning"]
    assert len(packet["retrieved_sources"]) == 1
    assert packet["retrieved_sources"][0]["host"] == "example.test"
    assert packet["retrieved_sources"][0]["url"] == "https://www.Example.test/portal"
    assert set(packet["retrieved_sources"][0]["signals"]) == {
        "customer portal link detected",
        "ERP signature detected: Domus",
        "metering technology signal detected: Ista",
    }


def test_evidence_packet_without_successful_signal_pages_fails(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "no-evidence.db")
    _seed_company(db, with_page=False)

    with pytest.raises(CaseStudyEvidenceUnavailable):
        CaseStudyWriter(db)._build_evidence_packet()


def test_evidence_packet_caps_retrieval_to_six_distinct_sources(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "source-cap.db")
    with db.connect() as conn:
        for index in range(7):
            company_id = conn.execute(
                """
                INSERT INTO companies_golden (
                    canonical_name,display_name,sources_csv,pipeline_stage,
                    website_url,is_vdiv_member,updated_at
                ) VALUES (?,?, 'test','SCORED',?,1,'now')
                """,
                (
                    f"Company {index}",
                    f"Company {index}",
                    f"https://company-{index}.test/",
                ),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO crawled_pages (
                    company_id,page_type,url,http_status,detected_erp_csv,has_portal_link,crawled_at
                ) VALUES (?, 'portal', ?, 200, 'Casavi', 1, ?)
                """,
                (
                    company_id,
                    f"https://company-{index}.test/",
                    f"2026-11-{index + 1:02d}",
                ),
            )

    packet = CaseStudyWriter(db)._build_evidence_packet()
    assert len(packet["retrieved_sources"]) == 6


def test_evidence_packet_handles_missing_run_and_malformed_summary(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "bad-summary.db")
    _seed_company(db, with_run=True)
    with db.connect() as conn:
        conn.execute(
            "UPDATE pipeline_runs SET summary_metrics_json='{' WHERE run_id='run-current'"
        )
    packet = CaseStudyWriter(db)._build_evidence_packet()
    assert packet["latest_run_summary"] == {}

    empty_db = Database(tmp_path / "no-run.db")
    _seed_company(empty_db)
    empty_packet = CaseStudyWriter(empty_db)._build_evidence_packet()
    assert empty_packet["latest_run"] is None


def test_narrative_validator_requires_known_citations_and_no_numbers() -> None:
    CaseStudyWriter._validate_narrative(
        "The retrieved pages show portal signals [S1].", {"S1"}
    )
    CaseStudyWriter._validate_narrative(
        "The service and portal pages contain signals [S1, S2, S3].",
        {"S1", "S2", "S3"},
    )
    with pytest.raises(CaseStudyNarrativeRejected, match="empty"):
        CaseStudyWriter._validate_narrative(" ", {"S1"})
    with pytest.raises(CaseStudyNarrativeRejected, match="cite"):
        CaseStudyWriter._validate_narrative("A statement [S9].", {"S1"})
    with pytest.raises(CaseStudyNarrativeRejected, match="cite"):
        CaseStudyWriter._validate_narrative("A statement [S1, S9].", {"S1", "S2"})
    with pytest.raises(CaseStudyNarrativeRejected, match="numeric"):
        CaseStudyWriter._validate_narrative("There are 4 signals [S1].", {"S1"})
    CaseStudyWriter._validate_narrative(
        "The ERP signature etg24 appears on the page [S1].", {"S1"}, {"etg24"}
    )
    with pytest.raises(CaseStudyNarrativeRejected, match="numeric"):
        CaseStudyWriter._validate_narrative(
            "The etg24 signal represents 4 deployments [S1].", {"S1"}, {"etg24"}
        )
    with pytest.raises(CaseStudyNarrativeRejected, match="inferred"):
        CaseStudyWriter._validate_narrative(
            "The page signatures prove system compatibility [S1].", {"S1"}
        )


def test_document_injects_measured_metrics_and_limitations(tmp_path: Path) -> None:
    db = Database(tmp_path / "doc.db")
    _seed_company(db, with_run=True)
    packet = CaseStudyWriter(db)._build_evidence_packet()
    text = CaseStudyWriter._build_document(
        packet,
        "The retrieved pages contain portal signals [S1].",
        "test-provider",
        "test-model",
    )
    assert "Active canonical companies | 1" in text
    assert "Latest run warnings: source warning." in text
    assert "https://Example.test/portal" in text
    assert "Review it and the cited source pages" in text

    with db.connect() as conn:
        conn.execute("DELETE FROM pipeline_runs")
    no_warning_packet = CaseStudyWriter(db)._build_evidence_packet()
    no_warning_text = CaseStudyWriter._build_document(
        no_warning_packet, "Narrative [S1].", "provider", "model"
    )
    assert "Latest run warnings: none recorded." in no_warning_text


@pytest.mark.asyncio
async def test_generate_requires_provider_and_retrieved_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "provider.db")

    async def no_provider(_provider=None):
        return None

    monkeypatch.setattr(
        writer_module.llm_router, "resolve_active_provider", no_provider
    )
    with pytest.raises(CaseStudyProviderUnavailable):
        await CaseStudyWriter(db).generate()

    monkeypatch.setattr(
        writer_module.llm_router, "resolve_active_provider", _resolve_provider
    )
    with pytest.raises(CaseStudyEvidenceUnavailable):
        await CaseStudyWriter(db).generate()


@pytest.mark.asyncio
async def test_generate_writes_source_backed_case_study_and_audit(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "generate.db")
    _seed_company(db, with_run=True)
    monkeypatch.setattr(
        writer_module.llm_router, "resolve_active_provider", _resolve_provider
    )
    monkeypatch.setattr(writer_module.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(settings, "export_dir", tmp_path / "exports")
    _FakeAsyncClient.response = _FakeResponse(
        200,
        {
            "choices": [
                {
                    "message": {
                        "content": "Retrieved pages show portal and ERP signals [S1]."
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 25},
        },
    )
    _FakeAsyncClient.error = None

    result = await CaseStudyWriter(db).generate()

    assert result["status"] == "ready"
    assert result["source_count"] == 1
    assert result["latest_run_id"] == "run-current"
    assert Path(result["path"]).exists()
    assert "Retrieved pages show portal and ERP signals [S1]." in result["markdown"]
    assert "| Active canonical companies | 1 |" in result["markdown"]
    assert _FakeAsyncClient.posted["url"] == "https://llm.test/v1/chat/completions"
    assert "clean_markdown" not in json.dumps(_FakeAsyncClient.posted["payload"])
    assert (
        "include at least one tag"
        in _FakeAsyncClient.posted["payload"]["messages"][0]["content"]
    )
    assert (
        "unverified page observations"
        in _FakeAsyncClient.posted["payload"]["messages"][0]["content"]
    )
    assert (
        "Do not infer infrastructure, deployment, compatibility"
        in _FakeAsyncClient.posted["payload"]["messages"][0]["content"]
    )
    with db.connect() as conn:
        audit = conn.execute(
            "SELECT stage,provider,model_name,prompt_tokens,completion_tokens,hallucination_blocked FROM llm_audit_logs"
        ).fetchone()
    assert tuple(audit) == (
        "CASE_STUDY_WRITER",
        "test-provider",
        "test-model",
        100,
        25,
        0,
    )


@pytest.mark.asyncio
async def test_generate_disables_reasoning_for_nemotron_narrative_model(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "nemotron-writer.db")
    _seed_company(db)

    async def resolve_nemotron(_provider=None):
        return {
            "provider": "nvidia_nim",
            "base_url": "https://llm.test/v1",
            "api_key": "test-key",
            "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
        }

    monkeypatch.setattr(
        writer_module.llm_router, "resolve_active_provider", resolve_nemotron
    )
    monkeypatch.setattr(writer_module.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(settings, "export_dir", tmp_path / "exports")
    _FakeAsyncClient.response = _FakeResponse(
        200,
        {
            "choices": [
                {"message": {"content": "Retrieved pages show portal signals [S1]."}}
            ]
        },
    )
    _FakeAsyncClient.error = None

    await CaseStudyWriter(db).generate()

    assert _FakeAsyncClient.posted["payload"]["chat_template_kwargs"] == {
        "enable_thinking": False
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "choice_text", "expected"),
    [
        (
            {"content": "Retrieved pages describe portal features [S1]."},
            None,
            "Retrieved pages describe portal features [S1].",
        ),
        (
            None,
            "Retrieved pages include an ERP signal [S1].",
            "Retrieved pages include an ERP signal [S1].",
        ),
        (
            {
                "reasoning_content": "1. I should summarize the retrieved signals.",
                "content": "",
            },
            "Retrieved pages show a portal signal [S1].",
            "Retrieved pages show a portal signal [S1].",
        ),
    ],
)
async def test_generate_supports_final_content_and_legacy_text_response_fields(
    tmp_path: Path, monkeypatch, message, choice_text, expected
) -> None:
    db = Database(tmp_path / "alternate-response.db")
    _seed_company(db)
    monkeypatch.setattr(
        writer_module.llm_router, "resolve_active_provider", _resolve_provider
    )
    monkeypatch.setattr(writer_module.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(settings, "export_dir", tmp_path / "exports")
    _FakeAsyncClient.response = _FakeResponse(
        200,
        {"choices": [{"message": message, "text": choice_text}]},
    )
    _FakeAsyncClient.error = None

    result = await CaseStudyWriter(db).generate()
    assert expected in result["markdown"]


@pytest.mark.asyncio
async def test_generate_discards_reasoning_only_provider_output(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "reasoning-only.db")
    _seed_company(db)
    monkeypatch.setattr(
        writer_module.llm_router, "resolve_active_provider", _resolve_provider
    )
    monkeypatch.setattr(writer_module.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(settings, "export_dir", tmp_path / "exports")
    _FakeAsyncClient.response = _FakeResponse(
        200,
        {
            "choices": [
                {"message": {"reasoning_content": "1. This is private reasoning [S1]."}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        },
    )
    _FakeAsyncClient.error = None

    with pytest.raises(CaseStudyWriterError, match="no final narrative content"):
        await CaseStudyWriter(db).generate()

    assert not (tmp_path / "exports" / "metrixa_current_case_study.md").exists()
    with db.connect() as conn:
        audit = conn.execute(
            "SELECT hallucination_blocked,completion_tokens,notes FROM llm_audit_logs"
        ).fetchone()
    assert tuple(audit) == (
        1,
        20,
        "Provider returned no final narrative content; reasoning-only output was discarded.",
    )


@pytest.mark.asyncio
async def test_generate_audits_provider_status_failure(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "provider-error.db")
    _seed_company(db)
    monkeypatch.setattr(
        writer_module.llm_router, "resolve_active_provider", _resolve_provider
    )
    monkeypatch.setattr(writer_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response = _FakeResponse(429, {})
    _FakeAsyncClient.error = None

    with pytest.raises(CaseStudyWriterError, match="HTTP 429"):
        await CaseStudyWriter(db).generate()
    with db.connect() as conn:
        blocked = conn.execute(
            "SELECT hallucination_blocked FROM llm_audit_logs"
        ).fetchone()[0]
    assert blocked == 1


@pytest.mark.asyncio
async def test_generate_rejects_numeric_narrative_and_audits_block(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "blocked-narrative.db")
    _seed_company(db)
    monkeypatch.setattr(
        writer_module.llm_router, "resolve_active_provider", _resolve_provider
    )
    monkeypatch.setattr(writer_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response = _FakeResponse(
        200,
        {
            "choices": [{"message": {"content": "The firm has 12 portal users [S1]."}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
        },
    )
    _FakeAsyncClient.error = None

    with pytest.raises(CaseStudyNarrativeRejected, match="numeric"):
        await CaseStudyWriter(db).generate()
    with db.connect() as conn:
        audit = conn.execute(
            "SELECT hallucination_blocked,prompt_tokens,completion_tokens FROM llm_audit_logs"
        ).fetchone()
    assert tuple(audit) == (1, 10, 10)


@pytest.mark.asyncio
async def test_generate_handles_network_and_invalid_response_errors(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "network-error.db")
    _seed_company(db)
    monkeypatch.setattr(
        writer_module.llm_router, "resolve_active_provider", _resolve_provider
    )
    monkeypatch.setattr(writer_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.error = httpx.ConnectError("offline")

    with pytest.raises(CaseStudyWriterError, match="could not be reached"):
        await CaseStudyWriter(db).generate()
    _FakeAsyncClient.error = None
    _FakeAsyncClient.response = _FakeResponse(200, None, parse_error=True)
    with pytest.raises(CaseStudyWriterError, match="invalid response"):
        await CaseStudyWriter(db).generate()
    with db.connect() as conn:
        blocked_rows = conn.execute(
            "SELECT COUNT(*) FROM llm_audit_logs WHERE hallucination_blocked=1"
        ).fetchone()[0]
    assert blocked_rows == 2


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (CaseStudyProviderUnavailable("no provider"), 503),
        (CaseStudyEvidenceUnavailable("no evidence"), 409),
        (CaseStudyNarrativeRejected("bad narrative"), 502),
        (CaseStudyWriterError("provider failure"), 502),
    ],
)
def test_case_study_api_maps_errors_to_http_statuses(
    tmp_path: Path, monkeypatch, error, expected_status
) -> None:
    class FakeWriter:
        def __init__(self, _db):
            pass

        async def generate(self, provider=None):
            assert provider == "nvidia_nim"
            raise error

    monkeypatch.setattr(server, "db", Database(tmp_path / "api-errors.db"))
    monkeypatch.setattr(server, "CaseStudyWriter", FakeWriter)
    response = TestClient(server.app).post(
        "/api/case-study/generate", json={"provider": "nvidia_nim"}
    )
    assert response.status_code == expected_status


def test_case_study_api_returns_generated_artifact_links(
    tmp_path: Path, monkeypatch
) -> None:
    class FakeWriter:
        def __init__(self, _db):
            pass

        async def generate(self, provider=None):
            return {"status": "ready", "provider": provider, "source_count": 1}

    monkeypatch.setattr(server, "db", Database(tmp_path / "api-success.db"))
    monkeypatch.setattr(server, "CaseStudyWriter", FakeWriter)
    response = TestClient(server.app).post(
        "/api/case-study/generate", json={"provider": "nvidia_nim"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "provider": "nvidia_nim",
        "source_count": 1,
    }


def test_current_case_study_artifact_preview_download_and_missing_file(
    tmp_path: Path, monkeypatch
) -> None:
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    artifact = export_dir / "metrixa_current_case_study.md"
    artifact.write_text("# Current case study\n", encoding="utf-8")
    monkeypatch.setattr(server, "db", Database(tmp_path / "artifact-api.db"))
    monkeypatch.setattr(settings, "export_dir", export_dir)
    client = TestClient(server.app)

    files = client.get("/api/artifacts/files").json()
    assert any(item["id"] == "current-case-study" for item in files["items"])
    preview = client.get("/api/artifacts/preview/current-case-study")
    assert preview.status_code == 200
    assert preview.json()["content"] == "# Current case study\n"
    download = client.get("/api/artifacts/download/current-case-study")
    assert download.status_code == 200
    assert download.text.strip() == "# Current case study"

    artifact.unlink()
    missing_preview = client.get("/api/artifacts/preview/current-case-study")
    missing_download = client.get("/api/artifacts/download/current-case-study")
    assert missing_preview.status_code == 404
    assert missing_download.status_code == 404
