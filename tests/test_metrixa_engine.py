"""
Unit & Integration Test Suite for Metrixa Engine.
Tests Berlin PLZ/Bezirk mapping, German Legal Normalization, Union-Find Deduplication,
DOM PropTech/ERP Detection, German Impressum & KPI Extraction, Email Verification,
and the Deterministic 0-100 Metrixa Lead Scoring Formula.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import pytest
from metrixa_engine.config import (
    Settings,
    is_valid_berlin_plz,
    map_berlin_plz_to_district,
)
from metrixa_engine.crawler.tech_detector import scan_html_for_tech_and_contacts
from metrixa_engine.db import Database
from metrixa_engine.enrichment.scorer import calculate_metrixa_lead_score
from metrixa_engine.entity_resolution.deduplicator import EntityDeduplicator
from metrixa_engine.entity_resolution.normalizer import (
    check_listing_eligibility,
    extract_canonical_domain,
    extract_legal_form,
    normalize_phone_e164,
)
from metrixa_engine.llm.router import extract_deterministic_german_kpis
from metrixa_engine.llm.extractor import KPIExtractionPipeline
from metrixa_engine.models import RawListing
from metrixa_engine.enrichment.search_router import SearchResultItem, SearchRouter
from metrixa_engine.scrapers.vdiv import VDIVScraper


def test_berlin_plz_and_district_mapping() -> None:
    assert is_valid_berlin_plz("10115") is True
    assert is_valid_berlin_plz("10719") is True
    assert is_valid_berlin_plz("14199") is True
    assert is_valid_berlin_plz("80331") is False  # Munich
    assert is_valid_berlin_plz("14467") is False  # Potsdam

    assert map_berlin_plz_to_district("10115") == "Mitte"
    assert map_berlin_plz_to_district("10719") == "Charlottenburg-Wilmersdorf"
    assert map_berlin_plz_to_district("10405") == "Pankow"
    assert map_berlin_plz_to_district("10997") == "Friedrichshain-Kreuzberg"


def test_configured_database_path_overrides_existing_project_database(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "isolated.db"
    monkeypatch.setenv("DATABASE_PATH", str(target))

    assert Settings().database_path == target.resolve()


def test_cors_configuration_rejects_wildcards_and_paths(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="cannot contain"):
        Settings()

    monkeypatch.setenv("CORS_ORIGINS", "https://example.com/app")
    with pytest.raises(ValueError, match="host only"):
        Settings()


def test_german_normalizer_and_eligibility() -> None:
    assert extract_legal_form("Muster Hausverwaltung GmbH & Co. KG") == "GmbH & Co. KG"
    assert extract_legal_form("BVBI Immobilienmanagement GmbH") == "GmbH"
    assert (
        extract_legal_form("Berlin Wohnen UG (haftungsbeschränkt)")
        == "UG (haftungsbeschränkt)"
    )

    assert normalize_phone_e164("030 / 88 42 100") == "+49308842100"
    assert extract_canonical_domain("https://www.bvbi.de/impressum") == "bvbi.de"
    assert extract_canonical_domain("https://www.gelbeseiten.de/gsbiz/123") is None
    assert extract_canonical_domain(None, "kontakt@gmx.de") is None

    ok, _ = check_listing_eligibility("BVBI Hausverwaltung GmbH", "10719", "Berlin")
    assert ok is True
    ok_clean, _ = check_listing_eligibility(
        "Blitz Gebäudereinigung GmbH", "10115", "Berlin"
    )
    assert ok_clean is False


def test_dom_tech_and_contact_scanner() -> None:
    sample_html = """
    <html>
      <body>
        <a href="https://berlin-hv.mycasavi.com/login">Unser Kundenportal</a>
        <p>Software: DOMUS 4000 und Abrechnung über Techem.</p>
        <p>Kontakt: info@berlin-hv.de sowie Geschäftsführer: t.mueller [at] berlin-hv.de</p>
        <a href="https://de.linkedin.com/in/thomas-mueller-berlin">LinkedIn</a>
      </body>
    </html>
    """
    res = scan_html_for_tech_and_contacts(sample_html)
    assert "Casavi" in res["erp_list"]
    assert "Domus" in res["erp_list"]
    assert "Techem" in res["metering_list"]
    assert res["has_portal"] is True
    assert "t.mueller@berlin-hv.de" in res["emails"]
    assert len(res["linkedin_urls"]) == 1


def test_deterministic_impressum_and_kpi_extractor() -> None:
    sample_text = """
    IMPRESSUM
    Spreeblick Hausverwaltung GmbH
    Uhlandstraße 165, 10719 Berlin
    Vertretungsberechtigter Geschäftsführer: Thomas Müller
    Handelsregister: Amtsgericht Charlottenburg, HRB 123456 B
    Gründung: Seit 1998 verwalten wir über 3.400 Wohneinheiten in Berlin.
    Unser Team von 14 Mitarbeitern betreut WEG-Verwaltung und Mietverwaltung.
    """
    kpi = extract_deterministic_german_kpis(
        company_name="Spreeblick Hausverwaltung GmbH",
        combined_text=sample_text,
        dom_erp_list=["Casavi"],
        dom_metering_list=[],
        dom_has_portal=True,
        dom_emails=["info@spreeblick-hv.de", "t.mueller@spreeblick-hv.de"],
        dom_linkedin_urls=["https://de.linkedin.com/in/thomas-mueller"],
    )
    assert kpi.legal_form == "GmbH"
    assert kpi.commercial_register_id == "HRB 123456 B"
    assert kpi.founding_year == 1998
    assert kpi.exact_units_managed == 3400
    assert "3.400 Wohneinheiten" in (kpi.units_evidence_quote or "")
    assert kpi.employee_count_mentioned == 14
    assert kpi.manages_weg is True
    assert kpi.manages_miet is True
    assert len(kpi.decision_makers) >= 1
    assert kpi.decision_makers[0].full_name == "Thomas Müller"
    assert kpi.decision_makers[0].direct_email == "t.mueller@spreeblick-hv.de"


def test_union_find_deduplication_and_scoring(tmp_path: Path) -> None:
    db = Database(tmp_path / "test_metrixa.db")
    listings = [
        RawListing(
            source_name="gelbe_seiten",
            raw_company_name="BVBI Berliner Vereinigung für Immobilienmanagement GmbH",
            raw_street="Uhlandstr. 165",
            raw_postal_code="10719",
            raw_phone="030 8842100",
            raw_website="https://www.bvbi.de",
        ),
        RawListing(
            source_name="vdiv",
            raw_company_name="BVBI Immobilienmanagement GmbH",
            raw_street="Uhlandstraße 165",
            raw_postal_code="10719",
            raw_phone="+49 30 8842100",
            raw_website="https://bvbi.de/kontakt",
            is_vdiv_member=True,
        ),
    ]
    db.insert_raw_listings(listings)
    deduper = EntityDeduplicator(db)
    stats = deduper.run_deduplication()
    assert stats["golden_clusters"] == 1
    assert stats["duplicates_merged"] == 1

    score, tier = calculate_metrixa_lead_score(
        exact_units=3400,
        estimated_units_tier="1,000-5,000",
        employee_count=14,
        legal_form="GmbH",
        has_website=True,
        manages_weg=True,
        manages_miet=True,
        manages_gewerbe=False,
        manages_sev=True,
        detected_erp_proptech="Casavi, Domus",
        has_customer_portal=True,
        website_is_https=True,
        is_vdiv_member=True,
        has_hrb_or_established_year=True,
        source_count=2,
        has_named_decision_maker=True,
        has_personal_email=True,
        has_linkedin_or_direct_phone=True,
    )
    assert score >= 90
    assert "Tier A" in tier


def test_postcode_match_compares_both_records() -> None:
    record_a = {
        "canonical_name": "alpha hausverwaltung gmbh",
        "canonical_domain": "alpha.example",
        "phone_e164": None,
        "address_key": None,
        "clean_plz": "10115",
    }
    record_b = {
        **record_a,
        "canonical_name": "alpha hausverwaltun gmbh",
        "canonical_domain": "beta.example",
        "clean_plz": "10997",
    }

    assert EntityDeduplicator.is_match(record_a, record_b) is False
    record_b["clean_plz"] = record_a["clean_plz"]
    assert EntityDeduplicator.is_match(record_a, record_b) is True


def test_extract_batch_uses_default_provider_when_none(
    tmp_path: Path, monkeypatch
) -> None:
    db = Database(tmp_path / "extractor.db")
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO companies_golden (
                canonical_name, display_name, sources_csv, pipeline_stage, updated_at
            ) VALUES (?, ?, ?, 'CRAWLED', ?)
            """,
            (
                "Test Hausverwaltung GmbH",
                "Test Hausverwaltung GmbH",
                "test",
                "2026-11-10T00:00:00Z",
            ),
        )
        company_id = conn.execute(
            "SELECT company_id FROM companies_golden WHERE canonical_name=?",
            ("Test Hausverwaltung GmbH",),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,clean_markdown,crawled_at) VALUES (?, 'homepage', 'https://test.example/', 200, 'Source evidence for a property manager', 'now')",
            (company_id,),
        )

    pipeline = KPIExtractionPipeline(db)

    async def fake_extract(row, requested_provider=None):
        return {
            "company_id": row["company_id"],
            "provider": "deterministic",
            "dms_found": 0,
            "has_erp": False,
        }

    monkeypatch.setattr(pipeline, "extract_single_company", fake_extract)
    result = asyncio.run(pipeline.extract_batch(requested_provider=None))

    assert result == {
        "processed": 1,
        "with_decision_maker": 0,
        "with_erp": 0,
        "failed": 0,
        "unverified_kpis_removed": 0,
        "unverified_contacts_removed": 0,
    }


@pytest.mark.asyncio
async def test_search_router_uses_selected_provider_first(monkeypatch) -> None:
    from metrixa_engine.enrichment import search_router as search_module

    calls: list[str] = []

    class ClientContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args) -> None:
            return None

    async def selected(client, query, max_results=8):
        calls.append(query)
        return [
            SearchResultItem(
                "Actual result", "https://example.org", "Source snippet", "brave_api"
            )
        ]

    async def should_not_run(client, query, max_results=8):
        raise AssertionError(
            "A later fallback ran despite a successful selected provider."
        )

    monkeypatch.setattr(search_module.settings, "default_search_provider", "brave")
    monkeypatch.setattr(
        search_module.httpx, "AsyncClient", lambda **kwargs: ClientContext()
    )
    router = SearchRouter()
    monkeypatch.setattr(router, "_query_brave_api", selected)
    monkeypatch.setattr(router, "_query_local_searxng", should_not_run)
    monkeypatch.setattr(router, "_query_native_metasearch", should_not_run)

    results = await router.search("a real query", allow_tavily_fallback=False)

    assert calls == ["a real query"]
    assert len(results) == 1
    assert results[0].engine == "brave_api"


@pytest.mark.asyncio
async def test_vdiv_scraper_returns_no_registry_fallback_when_site_is_unavailable(
    monkeypatch,
) -> None:
    scraper = VDIVScraper()
    urls = []

    async def unavailable(client, url):
        urls.append(url)
        return ""

    monkeypatch.setattr(scraper, "fetch_text", unavailable)

    assert await scraper.scrape_berlin() == []
    assert urls == ["https://vdiv-bb.de/mitglieder/"]


@pytest.mark.asyncio
async def test_vdiv_scraper_parses_and_deduplicates_current_directory(monkeypatch):
    scraper = VDIVScraper()
    urls = []
    html = """
    <div class="contact-list-contact-container">
      <span class="contact-list-contact-name">Alpha Hausverwaltung GmbH</span>
      <div class="contact-list-address"><span>10115 Berlin</span></div>
    </div>
    <div class="contact-list-contact-container">
      <span class="contact-list-contact-name">Alpha Hausverwaltung GmbH</span>
      <div class="contact-list-address"><span>10719 Berlin</span></div>
    </div>
    <div class="contact-list-contact-container">
      <span class="contact-list-contact-name">Alpha Hausverwaltung GmbH</span>
      <div class="contact-list-address"><span>10115 Berlin</span></div>
    </div>
    """

    async def live_page(client, url):
        urls.append(url)
        return html

    monkeypatch.setattr(scraper, "fetch_text", live_page)

    rows = await scraper.scrape_berlin()

    assert urls == ["https://vdiv-bb.de/mitglieder/"]
    assert len(rows) == 2
    assert rows[0].raw_company_name == "Alpha Hausverwaltung GmbH"
    assert rows[0].is_vdiv_member is True
    assert rows[1].raw_postal_code == "10719"


def test_legacy_vdiv_registry_is_preserved_but_excluded_from_active_leads(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "legacy-vdiv.db")
    db.insert_raw_listings(
        [
            RawListing(
                source_name="vdiv",
                raw_company_name="Curated Hausverwaltung GmbH",
                raw_postal_code="10719",
                raw_city="Berlin",
                raw_website="https://curated.example",
                is_vdiv_member=True,
                raw_payload={"verified_vdiv_member": True},
            )
        ]
    )
    db.init_schema()
    stats = EntityDeduplicator(db).run_deduplication()

    db.init_schema()
    db.init_schema()  # The migration is safe to run on every app startup.

    with db.connect() as conn:
        raw = conn.execute(
            "SELECT * FROM raw_listings WHERE source_name = 'vdiv'"
        ).fetchone()
        active_count = conn.execute(
            "SELECT COUNT(*) FROM companies_golden WHERE pipeline_stage != 'DISQUALIFIED'"
        ).fetchone()[0]

    payload = json.loads(raw["raw_json_payload"])
    assert raw["raw_company_name"] == "Curated Hausverwaltung GmbH"
    assert raw["is_vdiv_member"] == 0
    assert payload == {"legacy_curated_vdiv_registry_requires_review": True}
    assert stats["source_review_excluded"] == 1
    assert stats["golden_clusters"] == 0
    assert active_count == 0


def test_legacy_vdiv_only_company_is_quarantined_on_database_migration(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "legacy-vdiv-company.db")
    listing = RawListing(
        source_name="vdiv",
        raw_company_name="Legacy Hausverwaltung GmbH",
        raw_postal_code="10719",
        raw_city="Berlin",
        raw_payload={"legacy_curated_vdiv_registry_requires_review": True},
    )
    db.insert_raw_listings([listing])
    with db.connect() as conn:
        raw_id = conn.execute("SELECT id FROM raw_listings").fetchone()[0]
        company_id = conn.execute(
            """
            INSERT INTO companies_golden (
                canonical_name, display_name, sources_csv, updated_at
            ) VALUES ('legacy hausverwaltung', 'Legacy Hausverwaltung GmbH', 'vdiv', '2026-11-10T00:00:00+00:00')
            """
        ).lastrowid
        conn.execute(
            "INSERT INTO company_sources_map (company_id, raw_listing_id) VALUES (?, ?)",
            (company_id, raw_id),
        )

    db.init_schema()

    with db.connect() as conn:
        company = conn.execute(
            "SELECT pipeline_stage, disqualification_reason, is_vdiv_member FROM companies_golden WHERE company_id = ?",
            (company_id,),
        ).fetchone()

    assert company["pipeline_stage"] == "DISQUALIFIED"
    assert (
        company["disqualification_reason"] == "legacy_vdiv_source_requires_live_review"
    )
    assert company["is_vdiv_member"] == 0
