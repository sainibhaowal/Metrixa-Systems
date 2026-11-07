"""
Deterministic DOM & Regex Scanner for PropTech ERP Stacks, Customer Portals,
Incumbent Submetering Providers, Social LinkedIn Links, and Obfuscated Emails.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set


PROPTECH_ERP_SIGNATURES: Dict[str, List[str]] = {
    "Casavi": [r"casavi\.de", r"mycasavi\.com", r"casavi"],
    "etg24": [r"etg24\.de", r"etg24\.com", r"\betg24\b"],
    "Facilioo": [r"facilioo\.de", r"\bfacilioo\b"],
    "Domus": [r"domus-software\.de", r"domus\s*4000", r"domus\s*1000", r"domus\s*erp", r"homeday-domus"],
    "Wodis Sigma / Aareon": [r"\bwodis\b", r"aareon\.de", r"aareon\.com", r"mareon"],
    "Haufe PowerHaus / axera": [r"powerhaus", r"haufe-axera", r"\baxera\b", r"haufe\s*immobilien"],
    "Immoware24": [r"immoware24\.de", r"\bimmoware24\b"],
    "Karthago": [r"karthago-software", r"karthago\s*2000"],
    "WinCASA": [r"wincasa", r"software24\.com"],
    "Homecase": [r"homecase\.de", r"\bhomecase\b"],
    "Objego": [r"objego\.de", r"\bobjego\b"],
}

METERING_INCUMBENT_SIGNATURES: Dict[str, List[str]] = {
    "Techem": [r"techem\.de", r"\btechem\b"],
    "Ista": [r"\bista\.com", r"\bista\.de", r"ista\s+deutschland"],
    "Brunata-Metrona": [r"\bbrunata\b", r"\bmetrona\b"],
    "Kalorimeta (Kalo)": [r"kalorimeta", r"\bkalo\.de\b"],
    "Minol": [r"minol\.de", r"\bminol\b"],
    "Qundis": [r"qundis\.de", r"\bqundis\b"],
    "BFW": [r"bfw-berlin", r"bfw\s+messdienst"],
}

PORTAL_PATTERNS: List[str] = [
    r"kundenportal",
    r"eigent[uü]merportal",
    r"mieterportal",
    r"kunden[\-\s]*login",
    r"service[\-\s]*portal",
    r"online[\-\s]*schadensmeldung",
    r"mycasavi\.com",
    r"etg24\.de",
    r"facilioo",
]

EMAIL_REGEX = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,10}\b"
)

LINKEDIN_REGEX = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9\-_%]+",
    re.IGNORECASE,
)


def scan_html_for_tech_and_contacts(raw_html: str) -> Dict[str, any]:
    """
    Scan raw HTML string for PropTech/ERP signatures, Metering incumbents,
    Customer Portal presence, LinkedIn URLs, and emails (including [at]/(at) de-obfuscation).
    """
    if not raw_html:
        return {
            "erp_list": [],
            "metering_list": [],
            "has_portal": False,
            "linkedin_urls": [],
            "emails": [],
        }

    lower_html = raw_html.lower()

    # 1. Detect PropTech / ERP software
    erp_found: List[str] = []
    for name, patterns in PROPTECH_ERP_SIGNATURES.items():
        if any(re.search(p, lower_html) for p in patterns):
            erp_found.append(name)

    # 2. Detect Metering Incumbents
    metering_found: List[str] = []
    for name, patterns in METERING_INCUMBENT_SIGNATURES.items():
        if any(re.search(p, lower_html) for p in patterns):
            metering_found.append(name)

    # 3. Detect Customer / Tenant / Owner Portal
    has_portal = bool(erp_found) or any(re.search(p, lower_html) for p in PORTAL_PATTERNS)

    # 4. Extract LinkedIn URLs
    linkedin_set: Set[str] = set()
    for match in LINKEDIN_REGEX.findall(raw_html):
        clean_li = match.rstrip("/\"'\\")
        linkedin_set.add(clean_li)

    # 5. Extract Emails (including common German Impressum obfuscations like ' (at) ' or ' [at] ')
    deobfuscated = re.sub(
        r"\s*(?:\[at\]|\(at\)|\{at\}|\s+at\s+)\s*",
        "@",
        raw_html,
        flags=re.IGNORECASE,
    )
    deobfuscated = re.sub(
        r"\s*(?:\[dot\]|\(dot\)|\[punkt\]|\(punkt\))\s*",
        ".",
        deobfuscated,
        flags=re.IGNORECASE,
    )

    email_set: Set[str] = set()
    for em in EMAIL_REGEX.findall(deobfuscated):
        em_low = em.lower().strip(".,;:")
        # Exclude image extensions or sentry/webpack artifacts
        if any(
            em_low.endswith(ext)
            for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".js", ".css", ".woff", ".ttf")
        ):
            continue
        if "sentry.io" in em_low or "example.com" in em_low or "wixpress.com" in em_low or "wordpress.org" in em_low:
            continue
        email_set.add(em_low)

    return {
        "erp_list": erp_found,
        "metering_list": metering_found,
        "has_portal": has_portal,
        "linkedin_urls": sorted(linkedin_set),
        "emails": sorted(email_set),
    }
