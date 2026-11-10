from __future__ import annotations

import pytest

from metrixa_engine.entity_resolution.normalizer import (
    canonicalize_company_name,
    check_listing_eligibility,
    extract_canonical_domain,
    extract_legal_form,
    normalize_address_key,
    normalize_phone_e164,
    normalize_website_url,
    transliterate_german,
)


def test_name_form_and_transliteration_fallbacks():
    assert extract_legal_form("") is None
    assert extract_legal_form("Unincorporated local association") is None
    assert extract_legal_form("North GmbH") == "GmbH"
    assert extract_legal_form("North AG") == "AG"
    assert (
        extract_legal_form("North UG (haftungsbeschränkt)") == "UG (haftungsbeschränkt)"
    )
    assert extract_legal_form("North e.K.") == "e.K."
    assert extract_legal_form("North GbR") == "GbR"
    assert transliterate_german("äöüÄÖÜß") == "aeoeueAeOeUess"
    assert canonicalize_company_name("") == ""
    assert canonicalize_company_name("GmbH & Co. KG") == ""
    assert canonicalize_company_name("Hausverwaltung") == "hausverwaltung"
    assert canonicalize_company_name("Muster Hausverwaltung GmbH") == "muster"


def test_phone_domain_url_and_address_edge_cases():
    assert normalize_phone_e164(None) is None
    assert normalize_phone_e164("x") is None
    assert normalize_phone_e164("garbage 123456") == "+49123456"
    assert normalize_phone_e164("0049 30 123456") == "+4930123456"
    assert extract_canonical_domain(None) is None
    assert (
        extract_canonical_domain("https://gelbeseiten.de/listing", "hello@company.de")
        == "company.de"
    )
    assert extract_canonical_domain("https://company.de/path") == "company.de"
    assert extract_canonical_domain(None, "info@gmail.com") is None
    assert extract_canonical_domain("https://localhost") is None
    assert normalize_website_url(None) is None
    assert normalize_website_url(None, "company.de") == "https://www.company.de"
    assert normalize_website_url("company.de") == "https://company.de"
    assert (
        normalize_website_url("https://linkedin.com/company/x", "company.de")
        == "https://www.company.de"
    )
    assert normalize_address_key(None, "10115") is None
    assert normalize_address_key("Main Street", None) is None
    assert normalize_address_key("Main Street", "1234") is None
    assert normalize_address_key("12", "10115") is None
    assert normalize_address_key("Uhlandstraße 165", "10719") == "10719_uhlandstr165"


@pytest.mark.parametrize(
    "name,plz,city,eligible,reason_fragment",
    [
        ("", None, None, False, "Empty"),
        ("X", None, None, False, "Empty"),
        ("Hausverwaltung Berlin GmbH", "80331", "Berlin", False, "Non-Berlin postal"),
        ("Hausverwaltung GmbH", "1234", "Munich", False, "Non-Berlin city"),
        ("Hausverwaltung GmbH", None, "Berlin", True, None),
        ("Hausverwaltung GmbH", "10719", "Munich", True, None),
        ("Gebäudereinigung GmbH", "10115", "Berlin", False, "Excluded"),
        ("Local Service GmbH", "10115", "Berlin", True, None),
    ],
)
def test_listing_eligibility_paths(name, plz, city, eligible, reason_fragment):
    result, reason = check_listing_eligibility(name, plz, city)
    assert result is eligible
    if reason_fragment:
        assert reason_fragment in (reason or "")
    else:
        assert reason is None
