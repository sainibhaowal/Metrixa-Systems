from __future__ import annotations

import pytest

from metrixa_engine.db import Database
from metrixa_engine.enrichment.search_router import SearchResultItem


@pytest.mark.asyncio
async def test_contact_search_with_known_director_and_refresh_generic_only_contact(
    tmp_path, monkeypatch
):
    import metrixa_engine.enrichment.contact_finder as module

    db = Database(tmp_path / "contact-residual.db")
    with db.connect() as conn:
        company_id = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,canonical_domain,general_email,phone_e164,sources_csv,pipeline_stage,updated_at) VALUES ('alpha','Alpha GmbH','alpha.de','info@alpha.de','+4930555','test','EXTRACTED','now')"
        ).lastrowid
        conn.execute(
            "INSERT INTO decision_makers (company_id,full_name,first_name,last_name,role,email_status,source_url,evidence_quote,is_primary_contact) VALUES (?, 'Max Mustermann','Max','Mustermann','Geschäftsführer','NONE','https://alpha.de/impressum','Geschäftsführer Max Mustermann',1)",
            (company_id,),
        )

    queries = []

    async def search(query, **kwargs):
        queries.append(query)
        return [
            SearchResultItem(
                "Geschäftsführer: Max Mustermann",
                "https://linkedin.com/in/max?x=1",
                "",
                "test",
            ),
            SearchResultItem(
                "Alpha", "https://linkedin.com/company/alpha?x=1", "", "test"
            ),
        ]

    monkeypatch.setattr(module.search_router, "search", search)
    enricher = module.ContactEnricher(db)
    result = await enricher._search_linkedin_and_director(
        "Alpha GmbH", "Max Mustermann", True
    )
    assert result == (
        "https://linkedin.com/in/max",
        "https://linkedin.com/company/alpha",
        None,
    )
    assert '"Max Mustermann"' in queries[0]

    async def mx_false(domain):
        return False, None

    monkeypatch.setattr(module.email_verifier, "check_domain_mx", mx_false)
    enriched = await enricher.enrich_single_company(
        {
            "company_id": company_id,
            "display_name": "Alpha GmbH",
            "canonical_domain": "alpha.de",
            "company_linkedin_url": None,
            "phone_e164": "+4930555",
            "general_email": "info@alpha.de",
        },
        enable_web_search_for_missing=True,
    )
    assert enriched["has_linkedin"] and not enriched["has_pattern_email_candidate"]
    with db.connect() as conn:
        row = conn.execute(
            "SELECT personal_email,email_status,linkedin_url FROM decision_makers WHERE company_id=?",
            (company_id,),
        ).fetchone()
    assert row["personal_email"] is None and row["email_status"] == "GENERIC_ONLY"
    assert row["linkedin_url"] == "https://linkedin.com/in/max"


@pytest.mark.asyncio
async def test_enrich_batch_limit_counts_flags_and_progress(tmp_path, monkeypatch):
    import metrixa_engine.enrichment.contact_finder as module

    db = Database(tmp_path / "batch-counts.db")
    with db.connect() as conn:
        for name in ("A GmbH", "B GmbH", "C GmbH"):
            conn.execute(
                "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,updated_at) VALUES (?,?, 'test','EXTRACTED','now')",
                (name.lower(), name),
            )

    enricher = module.ContactEnricher(db)

    async def result_for(row, **kwargs):
        return {
            "mx_valid": row["display_name"].startswith(("A", "B")),
            "has_public_email": row["display_name"].startswith("B"),
            "has_pattern_email_candidate": row["display_name"].startswith("A"),
        }

    monkeypatch.setattr(enricher, "enrich_single_company", result_for)
    progress = []
    result = await enricher.enrich_batch(
        limit=2,
        web_search_top_n=0,
        progress_callback=lambda done, total: progress.append((done, total)),
    )
    assert result == {
        "processed": 2,
        "mx_valid_domains": 2,
        "public_emails_listed": 1,
        "pattern_email_candidates": 1,
    }
    assert sorted(progress) == [(1, 2), (2, 2)]


@pytest.mark.asyncio
async def test_async_mx_verifier_wraps_sync_lookup(monkeypatch):
    from metrixa_engine.enrichment.email_verifier import EmailVerifier

    verifier = EmailVerifier()
    monkeypatch.setattr(
        verifier, "check_domain_mx_sync", lambda domain: (True, f"mx.{domain}")
    )
    assert await verifier.check_domain_mx("sample.example") == (
        True,
        "mx.sample.example",
    )
