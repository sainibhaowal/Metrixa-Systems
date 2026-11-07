"""
Unit & Integration Test Suite for Heidi Engine.
Tests Berlin PLZ/Bezirk mapping, German Legal Normalization, Union-Find Deduplication,
DOM PropTech/ERP Detection, German Impressum & KPI Extraction, Email Verification,
and the Deterministic 0-100 Heidi Lead Scoring Formula.
"""

from __future__ import annotations

from pathlib import Path
from heidi_engine.config import is_valid_berlin_plz, map_berlin_plz_to_district
from heidi_engine.crawler.tech_detector import scan_html_for_tech_and_contacts
from heidi_engine.db import Database
from heidi_engine.enrichment.email_verifier import email_verifier
from heidi_engine.enrichment.scorer import calculate_heidi_lead_score
from heidi_engine.entity_resolution.deduplicator import EntityDeduplicator
from heidi_engine.entity_resolution.normalizer import (
    canonicalize_company_name,
    check_listing_eligibility,
    extract_canonical_domain,
    extract_legal_form,
    normalize_phone_e164,
)
from heidi_engine.llm.router import extract_deterministic_german_kpis
from heidi_engine.models import RawListing


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


def test_german_normalizer_and_eligibility() -> None:
    assert extract_legal_form("Muster Hausverwaltung GmbH & Co. KG") == "GmbH & Co. KG"
    assert extract_legal_form("BVBI Immobilienmanagement GmbH") == "GmbH"
    assert extract_legal_form("Berlin Wohnen UG (haftungsbeschränkt)") == "UG (haftungsbeschränkt)"

    assert normalize_phone_e164("030 / 88 42 100") == "+49308842100"
    assert extract_canonical_domain("https://www.bvbi.de/impressum") == "bvbi.de"
    assert extract_canonical_domain("https://www.gelbeseiten.de/gsbiz/123") is None
    assert extract_canonical_domain(None, "kontakt@gmx.de") is None

    ok, _ = check_listing_eligibility("BVBI Hausverwaltung GmbH", "10719", "Berlin")
    assert ok is True
    ok_clean, _ = check_listing_eligibility("Blitz Gebäudereinigung GmbH", "10115", "Berlin")
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
    db = Database(tmp_path / "test_heidi.db")
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

    score, tier = calculate_heidi_lead_score(
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

