# Metrixa Engine: Automated B2B Lead Discovery, Enrichment & Qualification Pipeline

**Case Study Submission:** B2B Data Engineering & LeadOps Architecture @ **Metrixa Systems GmbH**
**Target Domain:** Property Management Companies (*Hausverwaltungen*) in Berlin, Germany

---

## 📊 Live Production Results (Berlin *Hausverwaltungen* Dataset)

| Metric                                                                |           Production Result           | Details                                                                                                                                                                              |
| :-------------------------------------------------------------------- | :------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Total Raw Scraped Listings (Stage 1)**                        |            **1,375**            | Scraped across *Gelbe Seiten* (`405`), *11880.com* (`838`), *VDIV Berlin-Brandenburg* (`30`), *OpenStreetMap Overpass API* (`100`), and *Search Discovery* (`2`) |
| **Unique Qualified Berlin *Hausverwaltungen* (Stage 2)**      |            **1,200**            | Deduplicated via Canonical Domain, E.164 Phone, `RapidFuzz` Token Sort Ratio & `Union-Find` clustering (`175` duplicates merged)                                                   |
| **🟢 Tier A: High-Priority Target Leads (`Score 70 to 100`)**  |              **35**              | Immediate sales targets managing large portfolios with PropTech portals/ERPs and direct decision-maker contacts                                                                      |
| **🟡 Tier B: Qualified Mid-Market Leads (`Score 45 to 69`)**   |             **409**             | Established Berlin residential property managers                                                                                                                                     |
| **⚪ Tier C: Long-Tail / Small Leads (`Score < 45`)**          |             **756**             | Smaller local property managers across all 12 Berlin *Bezirke*                                                                                                                     |
| **Website & *Impressum* Pages Crawled (Stage 3)**             |          **885 Pages**          | Across `243` verified corporate domains (`/`, `/impressum`, `/team`, `/leistungen`, `/referenzen`, `/kundenportal`)                                                                 |
| **PropTech ERP / Customer Portals Detected**                    |         **41 Deployments**      | *Casavi, Domus, Immoware24, Haufe PowerHaus / axera, etg24, Facilioo*, and digital tenant/owner portals                                                                             |
| **Named Decision-Makers Extracted (Stage 4)**                   | **121 Contacts** *(104 Firms)* | *Geschäftsführer*, *Inhaber*, *Vorstand*, and *Prokuristen* extracted from § 5 DDG *Impressum* & Team pages                                                                        |
| **Verified / DNS `MX`-Valid Personal Emails (Stage 5)**       | **118 Contacts** *(102 Firms)* | Strictly non-`info@` personal executive emails verified against live DNS `MX` corporate servers                                                                                     |

---

## 📦 Generated Deliverables (Ready to Submit)

1. **Academic Research Paper & Whitepaper PDF:** 👉 [`docs/Case Study/Case_Study_Heidi_Systems.pdf`](./docs/Case%20Study/Case_Study_Heidi_Systems.pdf)
2. **Multi-Tab Excel Workbook (`.xlsx` for Google Sheets / Attachment):** 👉 [`data/exports/metrixa_berlin_hausverwaltungen.xlsx`](./data/exports/metrixa_berlin_hausverwaltungen.xlsx)
   * **Tab 1 (`Qualified_Berlin_Leads`):** All **1,200** Berlin property management companies ranked by `Metrixa Lead Score (0 to 100)` across 31 KPI & contact columns.
   * **Tab 2 (`All_Decision_Makers_Contacts`):** All **121** extracted *Geschäftsführer* / decision-makers with personal emails, DNS `MX` server verification, and verbatim evidence quotes.
   * **Tab 3 (`Evidence_And_Audit_Trail`):** All **885** crawled pages with HTTP status codes, DOM ERP/metering signals, and verbatim unit quotes.
   * **Tab 4 (`KPI_Methodology_And_Summary`):** Executive KPI rationale, scoring weights, and live dataset statistics.
3. **Master CSV Deliverable:** 👉 [`data/exports/metrixa_berlin_leads_master.csv`](./data/exports/metrixa_berlin_leads_master.csv)
4. **Comprehensive Documentation & Methodology:** 👉 [`docs/Case Study/Case Study.md`](./docs/Case%20Study/Case%20Study.md)

---

## 🚀 One-Click Launch: Full-Stack Web Cockpit & Dashboard

Launch both the **FastAPI Backend (:8000)** and the **Next.js 14 Web Cockpit (:3000)** simultaneously:

```powershell
.\start_cockpit.bat
```

Open [http://localhost:3000](http://localhost:3000) in your browser to experience:
* **Executive Cockpit (`/`)**: 5 live KPI metric cards, district market penetration bar charts, and PropTech ERP adoption matrix.
* **Mission Control (`/mission-control`)**: 6-stage DAG runner with real-time Server-Sent Events (SSE) streaming terminal.
* **Leads Database (`/leads`)**: 31-column virtualized data grid with debounced search, district filters, and tier badges.
* **Evidence Drawer (`EvidenceDrawer.tsx`)**: 5-pillar scorecard, verified decision-maker dossier, and verbatim German legal *Impressum* quotes.
* **Tools Catalog (`/tools`)**: Agentic scraping, parsing, and verification tool monitor with live latency health checks.
* **Artifact Vault (`/artifacts`)**: Instant downloads for `.xlsx`, `.csv`, and Markdown reports.
* **Provider & Harness Hub (`/settings`)**:
  * **Sliding Motion Toggle:** Seamless transition between **LLM Extraction Engines** and **Web Search Providers**.
  * **Real Brand Logos:** Official high-definition vector logos for Gemini, OpenAI, DeepSeek, Ollama, LM Studio, llama.cpp, NVIDIA, SearXNG, Tavily, and Brave.
  * **SearXNG Local Default Active:** Zero-cost privacy meta-search engine with live test ping and automatic failover.
  * **Live 10-Token Ping Tests:** Real-time token validation and connection testing.
  * **Animated Collapsible Sidebar:** One-click toggle button on top bar with persistent state.
  * **Pure Matte Dark Frost Theme:** Obsidian charcoal `#09090b` palette with crisp emerald `#10b981` accents.

---

## 🌐 Full Web Architecture & API Gateway

Metrixa Systems is engineered natively as an end-to-end **Web Application & REST API Gateway**. All pipeline orchestration, lead filtering, evidence inspection, provider testing, and exports are conducted 100% through the modern Web UI:

* **Web Application UI:** [http://localhost:3000](http://localhost:3000)
* **Interactive OpenAPI Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Backend Gateway:** [http://127.0.0.1:8000](http://127.0.0.1:8000)

```powershell
# Launch both FastAPI backend and Next.js 14 frontend simultaneously:
.\start_cockpit.bat

# Or launch via metrixa batch script:
.\metrixa.bat

# Run the backend test suite:
.\.venv\Scripts\pytest.exe -v
```

---

## 📚 Master Engineering Documentation Index (Follow `01` → `07` in Order)

|      Order      | Document File                                                                                                                                                 | What Is Inside                                                                                                                                                                                                                                                                                                                                                                       |
| :--------------: | :------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`01`** | [`docs/01_PRD_AND_REQUIREMENTS_ENGINEERING.md`](./docs/01_PRD_AND_REQUIREMENTS_ENGINEERING.md)                                                               | **Product Requirements Document (PRD):** Metrixa Systems business model (*Messdienstleister*), mapping of Task 1, Task 2, Bonus, and Task 3 to functional (`FR-1` to `FR-7`) and non-functional requirements.                                                                                                                                                              |
| **`02`** | [`docs/02_SYSTEM_ARCHITECTURE_AND_TECH_STACK.md`](./docs/02_SYSTEM_ARCHITECTURE_AND_TECH_STACK.md)                                                           | **System Design & Tech Stack:** 6-stage pipeline architecture diagrams, Unified Multi-LLM Router (`llama.cpp`, `LM Studio`, `NVIDIA NIM`, `DeepSeek`, `Gemini`), Unified Search Router (`Local SearXNG` + Native Meta-Search + `Tavily`), library justifications, and repository folder tree.                                                                    |
| **`03`** | [`docs/03_TASK1_INGESTION_SCRAPERS_AND_DEDUPLICATION.md`](./docs/03_TASK1_INGESTION_SCRAPERS_AND_DEDUPLICATION.md)                                           | **Task 1 Blueprint (Market Discovery & Deduplication):** Technical specs for all 5 Berlin scrapers (`Gelbe Seiten`, `11880.com`, `VDIV Berlin-Brandenburg`, `OpenStreetMap Overpass API`, `SearXNG/Tavily`), Berlin PLZ/category filtering, and the `RapidFuzz` + `Union-Find` Entity Resolution algorithm.                                                      |
| **`04`** | [`docs/04_TASK2_KPI_BLUEPRINT_CRAWLER_AND_SCORING_ENGINE.md`](./docs/04_TASK2_KPI_BLUEPRINT_CRAWLER_AND_SCORING_ENGINE.md)                                   | **Task 2 & Bonus Blueprint (KPIs, Crawler, LLM & Lead Scoring):** 5-Pillar Qualifying KPI definitions for submetering, async Website/*Impressum* crawler, DOM PropTech/ERP scanner (`Casavi`, `Domus`, `Wodis`, `Haufe`, `etg24`), Pydantic LLM schema with verbatim evidence checks, personal email/LinkedIn enrichment, and the `0–100` Lead Scoring formula. |
| **`05`** | [`docs/05_DATABASE_SCHEMA_DATA_STRUCTURES_AND_EXPORT_SPEC.md`](./docs/05_DATABASE_SCHEMA_DATA_STRUCTURES_AND_EXPORT_SPEC.md)                                 | **Database Schema & Deliverable Spec:** Complete SQLite WAL ER diagram (`raw_listings`, `companies_golden`, `crawled_pages`, `kpi_extractions`, `decision_makers`, `llm_audit_logs`), crash-recovery state machine, and exact 4-Tab Excel (`.xlsx`) / Google Sheets column layout.                                                                               |
| **`06`** | [`docs/06_TASK3_VALIDATION_EVALUATION_ABLATION_AND_PRESENTATION_BLUEPRINT.md`](./docs/06_TASK3_VALIDATION_EVALUATION_ABLATION_AND_PRESENTATION_BLUEPRINT.md) | **Task 3 Blueprint (Validation, Evaluation, Ablation & Setup):** 4-layer data validation rules, Gold-Set Precision/Recall/F1 metrics, Stage 1–5 Ablation Study table, and native local SearXNG / Multi-LLM configuration.                                                                                                                                                     |
| **`07`** | [`docs/07_TASK3_EXECUTIVE_PRESENTATION.md`](./docs/07_TASK3_EXECUTIVE_PRESENTATION.md)                                                                       | **Task 3 Executive Presentation Deliverable:** Slide-by-slide presentation summarizing our architecture, KPI logic, validation results, and ablation table for Metrixa Systems.                                                                                                                                                                                                  |
