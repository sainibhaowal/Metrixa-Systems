"""
Canonical Normalization & Eligibility Filter for Berlin Property Management Listings.
Handles German Legal Form extraction, Umlaut normalization, E.164 phone parsing,
tldextract domain canonicalization, and Berlin PLZ / Category noise filtering.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple
import phonenumbers
import tldextract

from metrixa_engine.config import is_valid_berlin_plz

# Ordered from most specific to general so 'GmbH & Co. KG' matches before 'GmbH'
LEGAL_FORM_PATTERNS: list[tuple[str, str]] = [
    (r"\bgmbh\s*&\s*co\.?\s*kg\b", "GmbH & Co. KG"),
    (r"\bgmbh\s*&\s*co\.?\s*ohg\b", "GmbH & Co. OHG"),
    (r"\bug\s*\(haftungsbeschr[aä]nkt\)\s*&\s*co\.?\s*kg\b", "UG & Co. KG"),
    (r"\bug\s*\(haftungsbeschr[aä]nkt\)", "UG (haftungsbeschränkt)"),
    (
        r"\bhaftungsbeschr[aä]nkte\s+unternehmergesellschaft\b",
        "UG (haftungsbeschränkt)",
    ),
    (r"\bgmbh\b", "GmbH"),
    (r"\bgesellschaft\s+mit\s+beschr[aä]nkter\s+haftung\b", "GmbH"),
    (r"\bag\b", "AG"),
    (r"\baktiengesellschaft\b", "AG"),
    (r"\beg\b|\be\.?\s*g\.?\b", "eG"),
    (r"\be\.?\s*k\.?\b|\be\.?\s*kfm\.?\b|\be\.?\s*kffr\.?\b", "e.K."),
    (r"\bgbr\b", "GbR"),
    (r"\bohg\b", "OHG"),
    (r"\bkg\b", "KG"),
    (r"\bse\b", "SE"),
]

DIRECTORY_AND_SOCIAL_DOMAINS = {
    "gelbeseiten.de",
    "11880.com",
    "dasoertliche.de",
    "meinestadt.de",
    "golocal.de",
    "cylex.de",
    "immobilienscout24.de",
    "immowelt.de",
    "immonet.de",
    "kleinanzeigen.de",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "xing.com",
    "youtube.com",
    "google.com",
    "google.de",
    "berlin.de",
    "vdiv.de",
    "vdiv-bb.de",
    "openstreetmap.org",
}

FREEMAIL_DOMAINS = {
    "gmx.de",
    "gmx.net",
    "web.de",
    "t-online.de",
    "gmail.com",
    "googlemail.com",
    "yahoo.de",
    "yahoo.com",
    "outlook.de",
    "outlook.com",
    "hotmail.com",
    "hotmail.de",
    "icloud.com",
    "me.com",
    "aol.de",
    "aol.com",
    "freenet.de",
    "arcor.de",
    "vodafone.de",
    "1und1.de",
    "ionos.de",
    "posteo.de",
    "mailbox.org",
    "kabelmail.de",
    "berlin.de",
}

NON_HAUSVERWALTUNG_EXCLUSION_PATTERNS = [
    r"\bgeb[aä]udereinigung\b",
    r"\breinigungsservice\b",
    r"\bumz[uü]ge\b",
    r"\bumzugsunternehmen\b",
    r"\bschl[uü]sseldienst\b",
    r"\bcontainerdienst\b",
    r"\bschornsteinfeger\b",
    r"\bmalerbetrieb\b",
    r"\bdachdeckerei\b",
    r"\bpflegedienst\b",
    r"\bestrich\b",
    r"\bger[uü]stbau\b",
]

POSITIVE_HAUSVERWALTUNG_PATTERNS = [
    r"hausverwaltung",
    r"immobilienverwaltung",
    r"weg[\s\-]*verwaltung",
    r"mietverwaltung",
    r"grundst[uü]cksverwaltung",
    r"wohnungsverwaltung",
    r"zinshausverwaltung",
    r"liegenschaftsverwaltung",
    r"objektverwaltung",
    r"immobilienmanagement",
    r"property\s*management",
    r"hv\b",
]


def extract_legal_form(company_name: str) -> Optional[str]:
    """Extract standard German legal form (GmbH, AG, UG, e.K., etc.) from raw company name."""
    if not company_name:
        return None
    lower = company_name.lower()
    for pattern, label in LEGAL_FORM_PATTERNS:
        if re.search(pattern, lower):
            return label
    return None


def transliterate_german(text: str) -> str:
    """Replace German umlauts and ß with ASCII equivalents."""
    return (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("Ä", "Ae")
        .replace("Ö", "Oe")
        .replace("Ü", "Ue")
        .replace("ß", "ss")
    )


def canonicalize_company_name(raw_name: str) -> str:
    """
    Create a normalized name token string for entity resolution blocking and fuzzy matching.
    Strips legal suffixes, punctuation, and generic location words while keeping core identity tokens.
    """
    if not raw_name:
        return ""
    s = transliterate_german(raw_name.lower())

    # Remove legal form patterns
    for pattern, _ in LEGAL_FORM_PATTERNS:
        s = re.sub(pattern, " ", s)

    # Remove generic suffixes/filler words only if other distinguishing words exist
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    tokens = [t for t in s.split() if t]

    stop_tokens = {
        "gesellschaft",
        "fuer",
        "mbh",
        "haftungsbeschraenkt",
        "und",
        "co",
        "in",
        "berlin",
        "der",
        "die",
        "das",
    }
    core_tokens = [t for t in tokens if t not in stop_tokens]
    if not core_tokens:
        core_tokens = tokens

    # Also normalize 'hausverwaltung' / 'immobilienverwaltung' when comparing
    stripped_core = [
        t
        for t in core_tokens
        if t
        not in (
            "hausverwaltung",
            "immobilienverwaltung",
            "grundstuecksverwaltung",
            "immobilien",
            "verwaltung",
        )
    ]
    if stripped_core:
        return " ".join(stripped_core)
    return " ".join(core_tokens)


def normalize_phone_e164(raw_phone: Optional[str]) -> Optional[str]:
    """Normalize German phone string to E.164 (+4930...) format, stripping PBXs '-0' for matching."""
    if not raw_phone:
        return None
    cleaned = re.sub(r"[^\d\+]", "", raw_phone)
    if not cleaned or len(cleaned) < 6:
        return None
    try:
        parsed = phonenumbers.parse(raw_phone, "DE")
        if phonenumbers.is_possible_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except Exception:
        pass
    # Fallback manual normalization for Berlin 030 numbers
    if cleaned.startswith("0049"):
        cleaned = "+" + cleaned[2:]
    elif cleaned.startswith("0"):
        cleaned = "+49" + cleaned[1:]
    elif not cleaned.startswith("+"):
        cleaned = "+49" + cleaned
    return cleaned if len(cleaned) >= 9 else None


def extract_canonical_domain(
    raw_website: Optional[str], raw_email: Optional[str] = None
) -> Optional[str]:
    """
    Extract root registered domain (e.g., 'bvbi.de') from website URL or corporate email,
    excluding directories, social media, and freemail providers.
    """
    candidates = []
    if raw_website:
        candidates.append(raw_website.strip())
    if raw_email and "@" in raw_email:
        candidates.append(raw_email.split("@", 1)[1].strip())

    for cand in candidates:
        ext = tldextract.extract(cand.lower())
        if not ext.domain or not ext.suffix:
            continue
        reg_domain = f"{ext.domain}.{ext.suffix}"
        if reg_domain in DIRECTORY_AND_SOCIAL_DOMAINS or reg_domain in FREEMAIL_DOMAINS:
            continue
        return reg_domain
    return None


def normalize_website_url(
    raw_website: Optional[str], canonical_domain: Optional[str] = None
) -> Optional[str]:
    """Ensure clean https:// URL for crawling."""
    if raw_website:
        w = raw_website.strip()
        if not w.startswith("http://") and not w.startswith("https://"):
            w = "https://" + w
        ext = tldextract.extract(w.lower())
        reg_dom = f"{ext.domain}.{ext.suffix}" if ext.domain and ext.suffix else ""
        if reg_dom and reg_dom not in DIRECTORY_AND_SOCIAL_DOMAINS:
            return w
    if canonical_domain:
        return f"https://www.{canonical_domain}"
    return None


def normalize_address_key(street: Optional[str], plz: Optional[str]) -> Optional[str]:
    """Create canonical street+PLZ blocking key (e.g., '10719_uhlandstr_165')."""
    if not street or not plz:
        return None
    clean_plz = "".join(ch for ch in str(plz) if ch.isdigit())
    if len(clean_plz) != 5:
        return None
    s = transliterate_german(street.lower())
    s = re.sub(r"strasse|straße|str\.", "str", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    if len(s) < 4:
        return None
    return f"{clean_plz}_{s}"


def check_listing_eligibility(
    company_name: str,
    postal_code: Optional[str],
    city: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """
    Validate whether a raw listing belongs in the Berlin Hausverwaltung Golden Dataset.
    Returns (is_eligible, disqualification_reason).
    """
    if not company_name or len(company_name.strip()) < 3:
        return False, "Empty or invalid company name"

    # 1. Check Berlin Postal Code (10115-14199) if provided
    if postal_code:
        clean_plz = "".join(ch for ch in str(postal_code) if ch.isdigit())
        if len(clean_plz) == 5 and not is_valid_berlin_plz(clean_plz):
            return False, f"Non-Berlin postal code ({clean_plz})"

    # 2. Check City if provided and no valid Berlin PLZ
    if city and not is_valid_berlin_plz(postal_code):
        if "berlin" not in city.lower():
            return False, f"Non-Berlin city ({city})"

    # 3. Check Category Exclusion (e.g., pure cleaning, moving, locksmith)
    lower_name = company_name.lower()
    has_positive = any(
        re.search(p, lower_name) for p in POSITIVE_HAUSVERWALTUNG_PATTERNS
    )
    if not has_positive:
        for excl in NON_HAUSVERWALTUNG_EXCLUSION_PATTERNS:
            if re.search(excl, lower_name):
                return False, f"Excluded non-Hausverwaltung category ({excl})"

    return True, None
