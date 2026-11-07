# 05 — Database Schema, Pipeline State Machine & Excel/Google Sheets Deliverable Spec

**Project Name:** Metrixa Engine — Autonomous B2B Lead Discovery, Enrichment & Qualification System
**Document Order:** `05 of 06`
**Purpose:** Complete relational database design (`SQLite WAL`), pipeline state transitions, and the exact column-by-column structure of the final multi-tab Excel (`.xlsx`) / Google Sheets deliverable.

---

## 1. Entity-Relationship (ER) Diagram (`data/metrixa_leads.db`)

All data across every stage of Metrixa Engine is persisted in a single, portable SQLite database (`data/metrixa_leads.db`) configured with `PRAGMA journal_mode=WAL;` and `PRAGMA foreign_keys=ON;`.

```mermaid
erDiagram
    RAW_LISTINGS ||--o{ COMPANY_SOURCES_MAP : "merged_into"
    COMPANIES_GOLDEN ||--o{ COMPANY_SOURCES_MAP : "has_provenance"
    COMPANIES_GOLDEN ||--o{ CRAWLED_PAGES : "has_webpages"
    COMPANIES_GOLDEN ||--o| KPI_EXTRACTIONS : "has_kpis"
    COMPANIES_GOLDEN ||--o{ DECISION_MAKERS : "has_contacts"
    COMPANIES_GOLDEN ||--o{ LLM_AUDIT_LOGS : "logged_by"

    RAW_LISTINGS {
        int id PK
        string source_name "gelbe_seiten | 11880 | vdiv | osm | searxng"
        string external_id
        string raw_company_name
        string raw_street
        string raw_postal_code
        string raw_city
        string raw_phone
        string raw_email
        string raw_website
        string source_url
        string raw_json_payload
        datetime scraped_at
    }

    COMPANIES_GOLDEN {
        int company_id PK
        string canonical_name
        string display_name
        string legal_form "GmbH | AG | UG | GmbH & Co. KG | e.K. | GbR"
        string commercial_register_id "e.g. HRB 123456 B"
        string street_address
        string postal_code "10115-14199"
        string city "Berlin"
        string district "Mitte, Pankow, Charlottenburg, etc."
        string phone_e164 "+4930..."
        string website_url
        string canonical_domain "unique index when not null"
        string general_email "info@..."
        boolean is_vdiv_member
        int source_count
        string sources_csv "gelbe_seiten,11880,vdiv"
        string pipeline_stage "DEDUPED | CRAWLED | EXTRACTED | ENRICHED | SCORED | DISQUALIFIED"
        int heidi_lead_score "0-100"
        string lead_tier "Tier A | Tier B | Tier C | Disqualified"
        datetime updated_at
    }

    CRAWLED_PAGES {
        int page_id PK
        int company_id FK
        string page_type "homepage | impressum | team | leistungen | referenzen | portal"
        string url
        int http_status
        string clean_markdown
        string detected_erp_csv "Casavi,Domus,Wodis,etc."
        string detected_metering_csv "Techem,Ista,etc."
        boolean has_portal_link
        datetime crawled_at
    }

    KPI_EXTRACTIONS {
        int kpi_id PK
        int company_id FK
        boolean is_actual_hausverwaltung
        int founding_year
        int exact_units_managed
        string units_evidence_quote
        string estimated_units_tier "<250 | 250-1,000 | 1,000-5,000 | 5,000+"
        int employee_count_est
        int reference_buildings_count
        boolean manages_weg
        boolean manages_miet
        boolean manages_gewerbe
        boolean manages_sev
        boolean has_customer_portal
        string detected_erp_proptech
        string incumbent_metering_signal
        int digital_maturity_score "1-5"
        string qualification_reasoning
        string llm_provider_used
        string llm_model_used
        float extraction_confidence
        datetime extracted_at
    }

    DECISION_MAKERS {
        int contact_id PK
        int company_id FK
        string full_name
        string first_name
        string last_name
        string role "Geschäftsführer | Inhaber | Prokurist | Teamleitung"
        string personal_email
        string email_status "PUBLIC_DIRECT_VERIFIED | PATTERN_MX_VERIFIED | GENERIC_ONLY | NONE"
        boolean mx_valid
        string direct_phone
        string linkedin_url
        string source_url
        string evidence_quote
        boolean is_primary_contact
    }

    LLM_AUDIT_LOGS {
        int log_id PK
        int company_id FK
        string stage "kpi_extraction | contact_enrichment"
        string provider "deepseek | local_llamacpp | lm_studio | nvidia_nim | gemini"
        string model_name
        int prompt_tokens
        int completion_tokens
        int latency_ms
        boolean schema_valid
        boolean hallucination_blocked
        datetime created_at
    }
```

---

## 2. Pipeline State Machine & Crash Recovery

Every record in `companies_golden` has a `pipeline_stage` column that acts as a finite state machine (FSM). If your internet drops or an API key hits a rate limit mid-run, re-running any CLI command picks up **only** the records waiting for that stage:

```mermaid
stateDiagram-v2
    [*] --> RAW_SCRAPED: Stage 1 (Scrapers write to raw_listings)
    RAW_SCRAPED --> DEDUPED: Stage 2 (Normalizer + RapidFuzz + Union-Find)
    RAW_SCRAPED --> DISQUALIFIED: Non-Berlin PLZ or Pure Makler/Cleaner
    DEDUPED --> CRAWLED: Stage 3 (Async Website + Impressum + Tech Scanner)
    CRAWLED --> EXTRACTED: Stage 4 (Multi-LLM KPI & Impressum Extraction)
    EXTRACTED --> DISQUALIFIED: LLM confirms not a Hausverwaltung
    EXTRACTED --> ENRICHED: Stage 5 (SearXNG/Tavily LinkedIn + DNS MX Email Verifier)
    ENRICHED --> SCORED: Stage 5b (Deterministic 0-100 Metrixa Lead Scorer)
    SCORED --> [*]: Stage 6 (Export to Multi-Tab .xlsx & Evaluation Report)
```

---

## 3. Exact Specification of the Final Excel (`.xlsx`) & Google Sheets Deliverable

Since we have no web frontend, the **Excel / Google Sheet workbook (`data/exports/metrixa_berlin_hausverwaltungen.xlsx`)** is the centerpiece visual deliverable that Metrixa Systems will inspect.

Our `ExcelExporter` (`src/heidi_engine/telemetry/excel_exporter.py`) automatically builds a **4-Tab Workbook** with corporate styling (dark navy headers `#1B365D`, frozen top row, auto-fitted column widths, color-coded `Tier A/B/C` badges, and clickable URLs):

### 3.1 Tab 1: `Qualified_Berlin_Leads` (Primary Master Table)
Sorted by `Metrixa Lead Score (0–100)` descending so the very best leads appear at the top.

| Col # | Column Header in Sheet | Source / Calculation | Example Value |
| :---: | :--- | :--- | :--- |
| **A** | `Lead ID` | Formatted Golden ID | `HEIDI-BER-0001` |
| **B** | `Lead Tier` | Color-coded badge (`Tier A`, `Tier B`, `Tier C`) | `Tier A (High Priority)` |
| **C** | `Metrixa Lead Score (0-100)` | Deterministic formula (`scorer.py`) | `88` |
| **D** | `Company Name` | Official display/legal name | `BVBI Berliner Vereinigung für Immobilienmanagement GmbH` |
| **E** | `Legal Form` | Extracted legal entity type | `GmbH` |
| **F** | `District (Bezirk)` | Mapped from Berlin PLZ | `Charlottenburg-Wilmersdorf` |
| **G** | `Postal Code (PLZ)` | 5-digit Berlin PLZ | `10719` |
| **H** | `Street Address` | Street + House Number | `Uhlandstr. 165` |
| **I** | `Website URL` | Clickable hyperlink | `https://www.bvbi.de` |
| **J** | `Reported Units (Wohneinheiten)` | Explicit units stated on website | `4500` |
| **K** | `Estimated Portfolio Size Tier` | Size bracket (`<250`, `250-1,000`, `1,000-5,000`, `5,000+`) | `1,000-5,000` |
| **L** | `Est. Team Size (Employees)` | Extracted from `/team` or company profile | `18` |
| **M** | `Manages WEG (Condos)` | `Yes` / `No` | `Yes` |
| **N** | `Manages Mietverwaltung (Rentals)` | `Yes` / `No` | `Yes` |
| **O** | `Manages Commercial (Gewerbe)` | `Yes` / `No` | `Yes` |
| **P** | `Has Online Customer Portal` | `Yes` / `No` | `Yes` |
| **Q** | `Detected ERP / PropTech Stack` | DOM + text signatures | `Casavi, Domus 4000` |
| **R** | `Incumbent Metering Signal` | Mentioned metering provider if any | `Techem` |
| **S** | `Digital Maturity Score (1-5)` | `1` to `5` | `5` |
| **T** | `VDIV Certified Member` | `Yes` / `No` | `Yes` |
| **U** | `Commercial Register (HRB)` | Extracted from *Impressum* | `HRB 98412 B` |
| **V** | `Founding Year` | Extracted from website | `1998` |
| **W** | `Primary Decision Maker Name` | *Geschäftsführer* / *Inhaber* | `Max Mustermann` |
| **X** | `Decision Maker Role` | Role title | `Geschäftsführer` |
| **Y** | `Personal / Direct Email (Bonus)` | Strictly non-`info@` personal email | `m.mustermann@bvbi.de` |
| **Z** | `Email Verification Status` | `PUBLIC_DIRECT_VERIFIED` \| `PATTERN_MX_VERIFIED` \| `GENERIC_ONLY` | `PUBLIC_DIRECT_VERIFIED` |
| **AA** | `Decision Maker / Company LinkedIn` | Clickable LinkedIn URL | `https://de.linkedin.com/in/...` |
| **AB** | `General Company Email` | Fallback `info@` / `kontakt@` inbox | `info@bvbi.de` |
| **AC** | `Company Phone` | E.164 / Formatted Berlin phone | `+49 30 8842100` |
| **AD** | `AI Qualification Summary` | 1-sentence reason why this lead fits Heidi | `Large VDIV-certified WEG & Miet manager (4,500 units) using Casavi portal.` |
| **AE** | `Data Sources Matched` | Provenance across scrapers | `vdiv, gelbe_seiten, 11880` |

### 3.2 Tab 2: `All_Decision_Makers_Contacts` (Bonus Task Deep-Dive)
Many medium-to-large *Hausverwaltungen* have **2 or 3 *Geschäftsführer*** plus a *Leiter WEG-Verwaltung* or *Prokurist*. While Tab 1 shows the primary contact per company, Tab 2 lists **every single extracted decision-maker row-by-row** with:
* `Company ID`, `Company Name`, `Lead Tier`, `Full Name`, `Role`, `Personal Email`, `Email Verification Status`, `DNS MX Server`, `Direct Phone`, `LinkedIn URL`, `Source Page URL`, and `Verbatim Evidence Quote`.

### 3.3 Tab 3: `Evidence_And_Audit_Trail` (Anti-Hallucination Proof)
Shows the exact URLs crawled (`impressum_url`, `team_url`, `services_url`), HTTP status codes, raw DOM tech signals detected, and the verbatim `units_evidence_quote` and `contact_evidence_quote` for full transparency.

### 3.4 Tab 4: `KPI_Methodology_And_Summary` (Executive Dashboard inside the Sheet)
Automatically populated summary table right inside Excel/Google Sheets explaining:
1. Why each KPI was chosen for Metrixa Systems and how the `0–100` Lead Score is weighted.
2. Live dataset statistics (Total Raw Scraped → Total Deduplicated Berlin Companies → Tier A / B / C counts → % with Verified Website → % with Named Decision Maker → % with Personal Email / LinkedIn).
