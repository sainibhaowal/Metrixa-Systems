"""
Pydantic v2 Data Schemas for Heidi Engine.
Enforces strict validation across Stage 1 (Scrapers), Stage 2 (Deduplication),
Stage 3 (Crawler), Stage 4 (Multi-LLM Extraction), Stage 5 (Enrichment & Scoring),
and Stage 6 (Export & Evaluation).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    DEDUPED = "DEDUPED"
    CRAWLED = "CRAWLED"
    EXTRACTED = "EXTRACTED"
    ENRICHED = "ENRICHED"
    SCORED = "SCORED"
    DISQUALIFIED = "DISQUALIFIED"


class LeadTier(str, Enum):
    TIER_A = "Tier A (High Priority)"
    TIER_B = "Tier B (Qualified Mid-Market)"
    TIER_C = "Tier C (Long-Tail / Small)"
    DISQUALIFIED = "Disqualified"


class EmailVerificationStatus(str, Enum):
    PUBLIC_DIRECT_VERIFIED = "PUBLIC_DIRECT_VERIFIED"
    PATTERN_MX_VERIFIED = "PATTERN_MX_VERIFIED"
    GENERIC_ONLY = "GENERIC_ONLY"
    NONE = "NONE"


class UnitsSizeTier(str, Enum):
    SMALL = "<250"
    MEDIUM = "250-1,000"
    LARGE = "1,000-5,000"
    ENTERPRISE = "5,000+"


class RawListing(BaseModel):
    """Stage 1 Raw Scraped Record before Entity Resolution."""

    source_name: str = Field(description="gelbe_seiten | 11880 | vdiv | osm | searxng")
    external_id: Optional[str] = None
    raw_company_name: str
    raw_street: Optional[str] = None
    raw_postal_code: Optional[str] = None
    raw_city: Optional[str] = "Berlin"
    raw_district: Optional[str] = None
    raw_phone: Optional[str] = None
    raw_email: Optional[str] = None
    raw_website: Optional[str] = None
    source_url: Optional[str] = None
    is_vdiv_member: bool = False
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionMakerExtracted(BaseModel):
    """Decision-Maker (Geschäftsführer / Inhaber / Prokurist / Team Lead) schema."""

    full_name: str = Field(
        description="Full name of Geschäftsführer, Inhaber, Vorstand, Prokurist, or Team Lead"
    )
    role: str = Field(
        default="Geschäftsführer",
        description="Exact German role, e.g., Geschäftsführer, Inhaber, Prokurist, Objektbetreuer",
    )
    direct_email: Optional[str] = Field(
        default=None, description="Direct personal email if explicitly written on page"
    )
    direct_phone: Optional[str] = Field(
        default=None, description="Direct phone extension if explicitly written"
    )
    linkedin_url: Optional[str] = Field(
        default=None, description="Personal LinkedIn profile URL if found"
    )
    source_quote: str = Field(
        default="",
        description="Exact verbatim substring from text proving this person's name and role",
    )


class CompanyKPIExtraction(BaseModel):
    """
    Strict Pydantic schema enforced on Multi-Provider LLM extraction
    (and deterministic fallback parser).
    """

    is_actual_hausverwaltung: bool = Field(
        default=True,
        description="True if company offers property management (WEG/Miet/Gewerbe), False if pure broker/cleaner",
    )
    legal_entity_name: Optional[str] = Field(
        default=None, description="Official legal name from Impressum"
    )
    legal_form: Optional[str] = Field(
        default=None, description="GmbH, UG, AG, GmbH & Co. KG, e.K., GbR, etc."
    )
    commercial_register_id: Optional[str] = Field(
        default=None, description="e.g., HRB 123456 B"
    )
    founding_year: Optional[int] = Field(
        default=None, description="4-digit founding year if explicitly mentioned (1850-2026)"
    )
    exact_units_managed: Optional[int] = Field(
        default=None,
        description="Explicit number of managed units (Wohneinheiten/Einheiten) if stated, else null",
    )
    units_evidence_quote: Optional[str] = Field(
        default=None, description="Verbatim quote stating the unit count, else null"
    )
    reference_buildings_count: Optional[int] = Field(
        default=None, description="Number of reference properties listed on website if any"
    )
    employee_count_mentioned: Optional[int] = Field(
        default=None,
        description="Explicit employee count or number of team members listed on /team page",
    )
    manages_weg: bool = Field(
        default=False,
        description="True if WEG-Verwaltung / Wohnungseigentumsverwaltung is offered",
    )
    manages_miet: bool = Field(
        default=False,
        description="True if Mietverwaltung / Zinshausverwaltung / Hausverwaltung is offered",
    )
    manages_gewerbe: bool = Field(
        default=False, description="True if Gewerbeverwaltung is offered"
    )
    manages_sev: bool = Field(
        default=False, description="True if Sondereigentumsverwaltung is offered"
    )
    has_online_portal: bool = Field(
        default=False,
        description="True if website offers a digital Kundenportal / Eigentümerportal / Mieter-App",
    )
    software_mentioned: List[str] = Field(
        default_factory=list,
        description="Any ERP/PropTech or metering providers mentioned in text",
    )
    decision_makers: List[DecisionMakerExtracted] = Field(
        default_factory=list,
        description="All Geschäftsführer, Inhaber, and key contacts extracted",
    )
    general_emails: List[str] = Field(
        default_factory=list,
        description="General emails like info@, kontakt@, verwaltung@",
    )
    qualification_reasoning: str = Field(
        default="",
        description="1-2 sentence factual summary of why this company is a strong/weak lead for Metrixa Systems",
    )


class CrawledPageRecord(BaseModel):
    """Stage 3 Crawled Webpage & DOM Tech Detection Record."""

    company_id: int
    page_type: str  # homepage | impressum | team | leistungen | referenzen | portal
    url: str
    http_status: int
    clean_markdown: str
    detected_erp_list: List[str] = Field(default_factory=list)
    detected_metering_list: List[str] = Field(default_factory=list)
    has_portal_link: bool = False
    social_linkedin_urls: List[str] = Field(default_factory=list)
    extracted_emails_raw: List[str] = Field(default_factory=list)

