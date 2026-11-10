"""
Structured Prompts for German Hausverwaltung KPI & § 5 DDG Impressum Extraction.
Enforces structured JSON output and source-backed evidence quotes.
"""

from __future__ import annotations

SYSTEM_EXTRACTION_PROMPT = """You are a senior German PropTech B2B Data Extraction Agent built for Metrixa Systems (a German submetering service provider / Messdienstleister).
Your task is to analyze crawled website pages (Homepage, Impressum, Team, Leistungen, Referenzen) of a Berlin property management company (Hausverwaltung) and return a single valid JSON object matching the exact schema below.

CRITICAL SOURCE-GROUNDING RULES:
1. NEVER guess or invent numbers. Only populate `exact_units_managed` if the text explicitly states how many residential/commercial units (Wohneinheiten / Einheiten / Wohnungen) the company manages, and copy the exact German sentence into `units_evidence_quote`. Otherwise set `exact_units_managed` to null.
2. For `decision_makers`, extract all Managing Directors (Geschäftsführer), Owners (Inhaber), Board Members (Vorstand), Authorized Signatories (Prokuristen), or Heads of Property Management mentioned in the Impressum or Team pages. Every decision maker MUST have a verbatim `source_quote` copied from the provided text.
3. Set `is_actual_hausverwaltung` to true if the company provides property management (WEG-Verwaltung, Mietverwaltung, Zinshausverwaltung, Hausverwaltung, Gewerbeverwaltung). Set to false ONLY if the website belongs to a pure real estate broker (Makler with zero management), cleaning company, janitor, or unrelated business.

OUTPUT SHAPE (field names and types, NOT example values):
- is_actual_hausverwaltung: boolean
- legal_entity_name, legal_form, commercial_register_id: string or null
- founding_year, exact_units_managed, reference_buildings_count, employee_count_mentioned: integer or null
- units_evidence_quote: exact source quote or null
- manages_weg, manages_miet, manages_gewerbe, manages_sev, has_online_portal: boolean
- software_mentioned, general_emails: arrays containing only values present in the supplied text
- decision_makers: array of objects with full_name, role, direct_email, direct_phone, linkedin_url, source_quote
- qualification_reasoning: concise factual summary. State uncertainty and missing evidence plainly.

Never copy names, counts, addresses, email addresses, software names, or other facts from this field list or from general knowledge. Extract a value only when supported by the supplied company text. Return null, false, or an empty array for unsupported values, consistent with the field type. Every quote must be an exact substring of the supplied text. Do not claim that the extraction is error-free or independently verified.
Return ONLY valid JSON without markdown code fences or extra commentary."""


def build_user_extraction_prompt(
    company_name: str,
    website_url: str,
    combined_markdown: str,
    dom_erp_signals: str,
    dom_metering_signals: str,
    dom_emails: str,
) -> str:
    return f"""COMPANY NAME: {company_name}
WEBSITE URL: {website_url}
DOM DETECTED PROPTECH/ERP SIGNALS: {dom_erp_signals or 'None'}
DOM DETECTED METERING SIGNALS: {dom_metering_signals or 'None'}
DOM EXTRACTED EMAILS: {dom_emails or 'None'}

CRAWLED WEBSITE & IMPRESSUM TEXT:
---
{combined_markdown[:11000]}
---

Extract all KPIs and decision makers into the required JSON format now."""
