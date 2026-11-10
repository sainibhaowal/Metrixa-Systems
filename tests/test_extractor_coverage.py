from __future__ import annotations

import pytest

from metrixa_engine.db import Database
from metrixa_engine.llm.extractor import (
    KPIExtractionPipeline,
    compute_digital_maturity_score,
    infer_portfolio_units_tier,
)
from metrixa_engine.models import (
    CompanyKPIExtraction,
    DecisionMakerExtracted,
    UnitsSizeTier,
)


def test_portfolio_tier_and_digital_score_thresholds():
    assert (
        infer_portfolio_units_tier(5000, None, None, False, False)
        == UnitsSizeTier.ENTERPRISE.value
    )
    assert (
        infer_portfolio_units_tier(1000, None, None, False, False)
        == UnitsSizeTier.LARGE.value
    )
    assert (
        infer_portfolio_units_tier(250, None, None, False, False)
        == UnitsSizeTier.MEDIUM.value
    )
    assert (
        infer_portfolio_units_tier(249, None, None, True, True)
        == UnitsSizeTier.SMALL.value
    )
    assert (
        infer_portfolio_units_tier(None, 15, None, False, False)
        == UnitsSizeTier.ENTERPRISE.value
    )
    assert (
        infer_portfolio_units_tier(None, 5, None, False, False)
        == UnitsSizeTier.LARGE.value
    )
    assert (
        infer_portfolio_units_tier(None, 2, None, False, False)
        == UnitsSizeTier.MEDIUM.value
    )
    assert (
        infer_portfolio_units_tier(None, 1, "AG", False, False)
        == UnitsSizeTier.LARGE.value
    )
    assert (
        infer_portfolio_units_tier(None, None, "GmbH", False, True)
        == UnitsSizeTier.LARGE.value
    )
    assert (
        infer_portfolio_units_tier(None, None, "GmbH", False, False)
        == UnitsSizeTier.MEDIUM.value
    )
    assert (
        infer_portfolio_units_tier(None, None, None, False, False)
        == UnitsSizeTier.SMALL.value
    )
    assert compute_digital_maturity_score(False, True, True, ["x"], True) == 1
    assert compute_digital_maturity_score(True, False, False, [], False) == 2
    assert compute_digital_maturity_score(True, True, False, [], False) == 3
    assert compute_digital_maturity_score(True, False, True, [], False) == 3
    assert compute_digital_maturity_score(True, False, False, ["Casavi"], False) == 3
    assert compute_digital_maturity_score(True, True, True, ["Casavi"], True) == 5


def _company(db: Database, name: str, stage: str, website: str | None = None) -> dict:
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO companies_golden (canonical_name, display_name, legal_form, general_email, website_url, is_vdiv_member, sources_csv, pipeline_stage, updated_at) VALUES (?, ?, 'GmbH', 'info@example.de', ?, 1, 'test', ?, 'old')",
            (name.lower(), name, website, stage),
        )
        row = conn.execute(
            "SELECT * FROM companies_golden WHERE company_id=?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)


def _source_page(
    db: Database, company_id: int, text: str = "Real company source text"
) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,clean_markdown,crawled_at) VALUES (?, 'homepage', 'https://source.example/', 200, ?, 'now')",
            (company_id, text),
        )


@pytest.mark.asyncio
async def test_contact_source_url_points_to_the_page_with_its_quote(
    tmp_path, monkeypatch
):
    import metrixa_engine.llm.extractor as module

    db = Database(tmp_path / "contact-source.db")
    company = _company(db, "Alpha GmbH", "CRAWLED", "https://alpha.example")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,clean_markdown,crawled_at) VALUES (?, 'impressum','https://alpha.example/impressum',200,'Legal notice','now')",
            (company["company_id"],),
        )
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,clean_markdown,crawled_at) VALUES (?, 'team','https://alpha.example/team',200,?,'now')",
            (company["company_id"], "Michael Wolf\nProkurist"),
        )

    async def extracted(**kwargs):
        return CompanyKPIExtraction(
            decision_makers=[
                DecisionMakerExtracted(
                    full_name="Michael Wolf",
                    role="Prokurist",
                    source_quote="Michael Wolf Prokurist",
                )
            ]
        ), {
            "provider": "deterministic",
            "model_name": "rules",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": 1,
            "schema_valid": True,
            "hallucination_blocked": False,
        }

    monkeypatch.setattr(
        module.llm_router, "extract_kpis_with_llm_and_deterministic_guard", extracted
    )
    await KPIExtractionPipeline(db).extract_single_company(company)
    with db.connect() as conn:
        source = conn.execute(
            "SELECT source_url FROM decision_makers WHERE company_id=?",
            (company["company_id"],),
        ).fetchone()[0]
    assert source == "https://alpha.example/team"


@pytest.mark.asyncio
async def test_extract_single_company_aggregates_pages_and_persists_every_output(
    tmp_path, monkeypatch
):
    import metrixa_engine.llm.extractor as module

    db = Database(tmp_path / "extract-single.db")
    company = _company(
        db, "Alpha Hausverwaltung GmbH", "CRAWLED", "https://alpha.example"
    )
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO crawled_pages (company_id,page_type,url,http_status,clean_markdown,detected_erp_csv,detected_metering_csv,has_portal_link,social_linkedin_csv,extracted_emails_csv,crawled_at) VALUES
            (?, 'homepage','https://alpha.example/',200,'Wegverwaltung with 3200 Wohneinheiten','Casavi, Domus','techem',1,'https://linkedin.com/company/alpha, https://linkedin.com/in/max','info@alpha.example', 'now'),
            (?, 'impressum','https://alpha.example/impressum',200,'Geschäftsführer Max Mustermann','Domus','ista',0,'https://linkedin.com/in/max','max@alpha.example', 'now'),
            (?, 'team','https://alpha.example/team',503,'ignored','ignored','ignored',0,'','','now')""",
            (company["company_id"], company["company_id"], company["company_id"]),
        )
    extraction = CompanyKPIExtraction(
        is_actual_hausverwaltung=True,
        legal_form="GmbH",
        commercial_register_id="HRB 1",
        founding_year=2001,
        exact_units_managed=3200,
        units_evidence_quote="3200 Wohneinheiten",
        employee_count_mentioned=12,
        reference_buildings_count=42,
        manages_weg=True,
        manages_miet=True,
        has_online_portal=False,
        software_mentioned=["Casavi"],
        general_emails=[],
        qualification_reasoning="Source-backed",
        decision_makers=[
            DecisionMakerExtracted(
                full_name="Max Mustermann",
                role="Geschäftsführer",
                direct_email="max@alpha.example",
                source_quote="Geschäftsführer Max Mustermann",
            )
        ],
    )
    seen = {}

    async def fake_extract(**kwargs):
        seen.update(kwargs)
        return extraction, {
            "provider": "deterministic",
            "model_name": "rules",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": 1,
            "schema_valid": True,
            "hallucination_blocked": False,
        }

    monkeypatch.setattr(
        module.llm_router, "extract_kpis_with_llm_and_deterministic_guard", fake_extract
    )
    pipeline = KPIExtractionPipeline(db)
    result = await pipeline.extract_single_company(company)
    assert result == {
        "company_id": company["company_id"],
        "provider": "deterministic",
        "dms_found": 1,
        "has_erp": True,
    }
    assert seen["dom_erp_list"] == ["Casavi", "Domus"]
    assert seen["dom_metering_list"] == ["ista", "techem"]
    assert seen["dom_emails"] == ["info@alpha.example", "max@alpha.example"]
    assert seen["dom_linkedin_urls"] == [
        "https://linkedin.com/company/alpha",
        "https://linkedin.com/in/max",
    ]
    with db.connect() as conn:
        kpi = conn.execute(
            "SELECT * FROM kpi_extractions WHERE company_id=?", (company["company_id"],)
        ).fetchone()
        dm = conn.execute(
            "SELECT * FROM decision_makers WHERE company_id=?", (company["company_id"],)
        ).fetchone()
        updated = conn.execute(
            "SELECT * FROM companies_golden WHERE company_id=?",
            (company["company_id"],),
        ).fetchone()
        audit = conn.execute(
            "SELECT * FROM llm_audit_logs WHERE company_id=?", (company["company_id"],)
        ).fetchone()
    assert kpi["estimated_units_tier"] == UnitsSizeTier.LARGE.value
    assert kpi["detected_erp_proptech"] == "Casavi, Domus"
    assert kpi["digital_maturity_score"] == 5
    assert dm["first_name"] == "Max" and dm["last_name"] == "Mustermann"
    assert dm["source_url"] == "https://alpha.example/impressum"
    assert dm["email_status"] == "PUBLIC_LISTED"
    assert kpi["extraction_confidence"] is None
    assert updated["pipeline_stage"] == "EXTRACTED"
    assert updated["company_linkedin_url"] == "https://linkedin.com/company/alpha"
    assert updated["general_email"] == "info@example.de"
    assert audit["schema_valid"] == 1

    # A second extraction takes the UPSERT branch, clears stale confidence, and
    # preserves the single KPI row.
    with db.connect() as conn:
        conn.execute(
            "UPDATE kpi_extractions SET extraction_confidence=0.92 WHERE company_id=?",
            (company["company_id"],),
        )
    await pipeline.extract_single_company(company, requested_provider="deterministic")
    with db.connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM kpi_extractions WHERE company_id=?",
                (company["company_id"],),
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT extraction_confidence FROM kpi_extractions WHERE company_id=?",
                (company["company_id"],),
            ).fetchone()[0]
            is None
        )


@pytest.mark.asyncio
async def test_extract_disqualified_and_batch_empty_limit_error_and_progress(
    tmp_path, monkeypatch
):
    db = Database(tmp_path / "extract-batch.db")
    disqualified = _company(db, "Disqualified GmbH", "CRAWLED")
    _source_page(db, disqualified["company_id"])
    pipeline = KPIExtractionPipeline(db)

    async def invalid(**kwargs):
        return CompanyKPIExtraction(is_actual_hausverwaltung=False), {
            "provider": "deterministic",
            "model_name": "rules",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": 0,
            "schema_valid": True,
            "hallucination_blocked": False,
        }

    monkeypatch.setattr(
        "metrixa_engine.llm.extractor.llm_router.extract_kpis_with_llm_and_deterministic_guard",
        invalid,
    )
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM companies_golden").fetchone()
    await pipeline.extract_single_company(dict(row))
    with db.connect() as conn:
        assert (
            conn.execute("SELECT pipeline_stage FROM companies_golden").fetchone()[0]
            == "DISQUALIFIED"
        )
    assert await pipeline.extract_batch() == {
        "processed": 0,
        "with_decision_maker": 0,
        "with_erp": 0,
        "failed": 0,
        "unverified_kpis_removed": 0,
        "unverified_contacts_removed": 0,
    }

    # reprocess_all selects a broad batch; exceptions are counted safely and callbacks progress.
    retry = _company(db, "Retry GmbH", "SCORED")
    _source_page(db, retry["company_id"])
    attempts = []

    async def raises(row, requested_provider=None):
        attempts.append(requested_provider)
        raise RuntimeError("provider error")

    monkeypatch.setattr(pipeline, "extract_single_company", raises)
    progress = []
    result = await pipeline.extract_batch(
        requested_provider="ollama",
        reprocess_all=True,
        progress_callback=lambda n, t: progress.append((n, t)),
    )
    assert result == {
        "processed": 1,
        "with_decision_maker": 0,
        "with_erp": 0,
        "failed": 1,
        "unverified_kpis_removed": 0,
        "unverified_contacts_removed": 0,
    }
    assert attempts == ["ollama"] and progress == [(1, 1)]

    # The idle on-demand branch limits extraction to 10 unless the caller supplies a limit.
    db2 = Database(tmp_path / "extract-on-demand.db")
    for i in range(12):
        lead = _company(db2, f"Lead {i} GmbH", "SCORED")
        _source_page(db2, lead["company_id"])
    pipeline2 = KPIExtractionPipeline(db2)
    processed = []

    async def succeeds(row, requested_provider=None):
        processed.append(row["company_id"])
        return {
            "company_id": row["company_id"],
            "provider": "x",
            "dms_found": 1,
            "has_erp": True,
        }

    monkeypatch.setattr(pipeline2, "extract_single_company", succeeds)
    result = await pipeline2.extract_batch(requested_provider=None)
    assert result == {
        "processed": 10,
        "with_decision_maker": 10,
        "with_erp": 10,
        "failed": 0,
        "unverified_kpis_removed": 0,
        "unverified_contacts_removed": 0,
    }


@pytest.mark.asyncio
async def test_extract_skips_company_without_source_evidence(tmp_path):
    db = Database(tmp_path / "extract-no-evidence.db")
    company = _company(db, "No Evidence GmbH", "CRAWLED")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO kpi_extractions (company_id,exact_units_managed,manages_weg,manages_miet,extracted_at) VALUES (?,1200,1,1,'old')",
            (company["company_id"],),
        )
        conn.execute(
            "INSERT INTO decision_makers (company_id,full_name,personal_email,email_status,source_url,evidence_quote) VALUES (?, 'Max Mustermann','max@example.de','PUBLIC_LISTED','https://no-source.example/impressum','Director Max Mustermann')",
            (company["company_id"],),
        )
    pipeline = KPIExtractionPipeline(db)

    result = await pipeline.extract_single_company(company)
    assert result == {
        "company_id": company["company_id"],
        "provider": "no_source_evidence",
        "dms_found": 0,
        "has_erp": False,
    }
    assert await pipeline.extract_batch(reprocess_all=True) == {
        "processed": 0,
        "with_decision_maker": 0,
        "with_erp": 0,
        "failed": 0,
        "unverified_kpis_removed": 1,
        "unverified_contacts_removed": 1,
    }
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM kpi_extractions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM decision_makers").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_extract_blocks_units_names_and_emails_without_source_quotes(
    tmp_path, monkeypatch
):
    import metrixa_engine.llm.extractor as module

    db = Database(tmp_path / "extract-quote-gates.db")
    company = _company(db, "Alpha GmbH", "CRAWLED", "https://alpha.example")
    _source_page(db, company["company_id"], "Owner Robin Sample")
    extraction = CompanyKPIExtraction(
        is_actual_hausverwaltung=True,
        exact_units_managed=999,
        units_evidence_quote="999 units at another company",
        decision_makers=[
            DecisionMakerExtracted(
                full_name="Alex Example",
                role="Director",
                source_quote="Director Alex Example",
            ),
            DecisionMakerExtracted(
                full_name="Robin Sample",
                role="Owner",
                direct_email="robin@unlisted.example",
                source_quote="Owner Robin Sample",
            ),
        ],
    )

    async def fake_extract(**kwargs):
        return extraction, {
            "provider": "deterministic",
            "model_name": "rules",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": 1,
            "schema_valid": True,
            "hallucination_blocked": False,
        }

    monkeypatch.setattr(
        module.llm_router, "extract_kpis_with_llm_and_deterministic_guard", fake_extract
    )
    await KPIExtractionPipeline(db).extract_single_company(company)

    with db.connect() as conn:
        kpi = conn.execute(
            "SELECT exact_units_managed,units_evidence_quote FROM kpi_extractions WHERE company_id=?",
            (company["company_id"],),
        ).fetchone()
        contacts = conn.execute(
            "SELECT full_name,personal_email,email_status FROM decision_makers WHERE company_id=?",
            (company["company_id"],),
        ).fetchall()
        audit = conn.execute(
            "SELECT hallucination_blocked FROM llm_audit_logs WHERE company_id=?",
            (company["company_id"],),
        ).fetchone()
    assert kpi["exact_units_managed"] is None and kpi["units_evidence_quote"] is None
    assert len(contacts) == 1 and contacts[0]["full_name"] == "Robin Sample"
    assert (
        contacts[0]["personal_email"] is None and contacts[0]["email_status"] == "NONE"
    )
    assert audit["hallucination_blocked"] == 1
