from __future__ import annotations

import pytest

from metrixa_engine.db import Database
from metrixa_engine.enrichment.email_verifier import EmailVerifier
from metrixa_engine.enrichment.scorer import LeadScorer, calculate_metrixa_lead_score
from metrixa_engine.enrichment.search_router import SearchResultItem
from metrixa_engine.models import UnitsSizeTier


def test_email_validation_generation_and_mx_cache(monkeypatch):
    import metrixa_engine.enrichment.email_verifier as module

    verifier = EmailVerifier()
    assert verifier.check_domain_mx_sync(None) == (False, None)
    monkeypatch.setattr(module.settings, "enable_dns_mx_check", False)
    assert verifier.check_domain_mx_sync(" Example.DE ") == (True, "mx.example.de")
    assert verifier.check_domain_mx_sync("example.de") == (True, "mx.example.de")

    class Answer:
        def __init__(self, preference, exchange):
            self.preference, self.exchange = preference, exchange

    class Resolver:
        timeout = lifetime = None

        def resolve(self, domain, record):
            assert (domain, record) == ("mx.example.de", "MX")
            return [Answer(20, "z.example.de."), Answer(10, "a.example.de.")]

    monkeypatch.setattr(module.settings, "enable_dns_mx_check", True)
    monkeypatch.setattr(module.dns.resolver, "Resolver", Resolver)
    verifier = EmailVerifier()
    assert verifier.check_domain_mx_sync("MX.EXAMPLE.DE") == (True, "a.example.de")
    assert verifier.check_domain_mx_sync("mx.example.de") == (True, "a.example.de")

    class BrokenResolver(Resolver):
        def resolve(self, *args):
            raise OSError("NXDOMAIN")

    monkeypatch.setattr(module.dns.resolver, "Resolver", BrokenResolver)
    assert EmailVerifier().check_domain_mx_sync("no-mx.example") == (False, None)
    assert not verifier.is_personal_email(None)
    assert not verifier.is_personal_email("not-an-email")
    assert not verifier.is_personal_email("@example.de")
    assert not verifier.is_personal_email("info@example.de")
    assert not verifier.is_personal_email("info.max@example.de")
    assert verifier.is_personal_email("max.mustermann@example.de")
    assert EmailVerifier.generate_german_b2b_personal_email("", "example.de") is None
    assert (
        EmailVerifier.generate_german_b2b_personal_email("Max Mustermann", None) is None
    )
    assert (
        EmailVerifier.generate_german_b2b_personal_email("Max Mustermann", "gmail.com")
        is None
    )
    assert EmailVerifier.generate_german_b2b_personal_email("Max", "example.de") is None
    assert (
        EmailVerifier.generate_german_b2b_personal_email(
            "Dr. Max Mustermann", "EXAMPLE.DE"
        )
        == "max.mustermann@example.de"
    )
    assert (
        EmailVerifier.generate_german_b2b_personal_email(
            "!!! Änne Müller", "example.de"
        )
        is None
    )


def test_scoring_pillars_and_database_updates(tmp_path):
    def score(**overrides):
        args = dict(
            exact_units=None,
            estimated_units_tier=None,
            employee_count=None,
            legal_form=None,
            has_website=False,
            manages_weg=False,
            manages_miet=False,
            manages_gewerbe=False,
            manages_sev=False,
            detected_erp_proptech=None,
            has_customer_portal=False,
            website_is_https=False,
            is_vdiv_member=False,
            has_hrb_or_established_year=False,
            source_count=0,
            has_named_decision_maker=False,
            has_personal_email=False,
            has_linkedin_or_direct_phone=False,
        )
        args.update(overrides)
        return calculate_metrixa_lead_score(**args)

    assert score()[1] == "Tier C (Long-Tail / Small)"
    assert score(exact_units=5000)[0] >= 35
    assert score(exact_units=1000)[0] >= 28
    assert score(exact_units=300)[0] >= 20
    assert score(legal_form="GmbH", has_website=True)[0] >= 16
    assert score(legal_form="GmbH")[0] >= 12
    assert (
        score(
            estimated_units_tier=UnitsSizeTier.ENTERPRISE.value,
            manages_weg=True,
            manages_miet=True,
            detected_erp_proptech="Casavi",
            has_customer_portal=True,
            has_website=True,
            website_is_https=True,
            is_vdiv_member=True,
            has_hrb_or_established_year=True,
            source_count=2,
            has_named_decision_maker=True,
            has_personal_email=True,
            has_linkedin_or_direct_phone=True,
        )[1]
        == "Tier A (High Priority)"
    )
    assert score(manages_weg=True)[0] >= 20
    assert score(manages_gewerbe=True)[0] >= 12
    assert score(manages_sev=True)[0] >= 4
    assert (
        score(exact_units=1000, manages_weg=True, manages_miet=True)[1]
        == "Tier B (Qualified Mid-Market)"
    )
    assert (
        score(legal_form="AG", has_website=True, manages_weg=True, manages_miet=True)[0]
        >= 41
    )

    db = Database(tmp_path / "score.db")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO companies_golden (canonical_name, display_name, sources_csv, pipeline_stage, updated_at) VALUES ('one','One GmbH','test','DEDUPED','old')"
        )
        conn.execute(
            "INSERT INTO companies_golden (canonical_name, display_name, sources_csv, pipeline_stage, updated_at) VALUES ('two','Two GmbH','test','DISQUALIFIED','old')"
        )
    result = LeadScorer(db).score_all_companies()
    assert sum(result.values()) == 1
    with db.connect() as conn:
        row = conn.execute(
            "SELECT pipeline_stage, lead_tier FROM companies_golden WHERE canonical_name='one'"
        ).fetchone()
    assert row["pipeline_stage"] == "SCORED"


@pytest.mark.asyncio
async def test_contact_enrichment_search_persistence_and_batch(tmp_path, monkeypatch):
    import metrixa_engine.enrichment.contact_finder as module

    db = Database(tmp_path / "contacts.db")
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO companies_golden (canonical_name, display_name, canonical_domain, general_email, phone_e164, sources_csv, pipeline_stage, updated_at) VALUES ('alpha','Alpha GmbH','alpha.de','info@alpha.de','+4930123','test','EXTRACTED','old')"
        )
        cid = cur.lastrowid
        conn.execute(
            "INSERT INTO companies_golden (canonical_name, display_name, canonical_domain, general_email, sources_csv, pipeline_stage, updated_at) VALUES ('beta','Beta GmbH','beta.de',NULL,'test','EXTRACTED','old')"
        )

    async def mx(domain):
        return True, f"mx.{domain}"

    monkeypatch.setattr(module.email_verifier, "check_domain_mx", mx)

    async def search(query, **kwargs):
        return [
            SearchResultItem(
                "Max Mustermann - Geschäftsführer",
                "https://linkedin.com/in/max-mustermann?trk=x",
                "",
                "test",
            ),
            SearchResultItem(
                "Alpha Company", "https://linkedin.com/company/alpha?trk=x", "", "test"
            ),
            SearchResultItem(
                "Geschäftsführer: Max Mustermann", "https://alpha.de/team", "", "test"
            ),
        ]

    monkeypatch.setattr(module.search_router, "search", search)
    enricher = module.ContactEnricher(db)
    found = await enricher._search_linkedin_and_director(
        "Alpha GmbH", enable_web_search=False
    )
    assert found == (None, None, None)
    result = await enricher.enrich_single_company(
        {
            "company_id": cid,
            "display_name": "Alpha GmbH",
            "canonical_domain": "alpha.de",
            "company_linkedin_url": None,
            "phone_e164": "+4930123",
            "general_email": "info@alpha.de",
        },
        enable_web_search_for_missing=True,
    )
    assert (
        result["mx_valid"]
        and result["has_linkedin"]
        and result["has_pattern_email_candidate"]
    )
    with db.connect() as conn:
        dm = conn.execute(
            "SELECT * FROM decision_makers WHERE company_id=?", (cid,)
        ).fetchone()
        company = conn.execute(
            "SELECT pipeline_stage, company_linkedin_url FROM companies_golden WHERE company_id=?",
            (cid,),
        ).fetchone()
    assert dm["full_name"] == "Max Mustermann"
    assert dm["personal_email"] == "max.mustermann@alpha.de"
    assert dm["email_status"] == "PATTERN_CANDIDATE_MX"
    assert company["pipeline_stage"] == "ENRICHED"

    # Exercise explicit public email handling and batch progress on a second row.
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO decision_makers (company_id, full_name, first_name, last_name, role, personal_email, email_status, is_primary_contact) VALUES (2,'Anna Schmidt','Anna','Schmidt','Director','anna@beta.de','PUBLIC_DIRECT_VERIFIED',1)"
        )

    async def mx_false(domain):
        return False, None

    monkeypatch.setattr(module.email_verifier, "check_domain_mx", mx_false)
    progress = []
    result = await enricher.enrich_batch(
        web_search_top_n=0,
        progress_callback=lambda n, total: progress.append((n, total)),
    )
    assert result["processed"] == 1 and result["public_emails_listed"] == 1
    assert progress == [(1, 1)]

    # Empty batch is an explicit no-op result.
    with db.connect() as conn:
        conn.execute("UPDATE companies_golden SET pipeline_stage='SCORED'")
    assert await enricher.enrich_batch() == {
        "processed": 0,
        "mx_valid_domains": 0,
        "public_emails_listed": 0,
        "pattern_email_candidates": 0,
    }
