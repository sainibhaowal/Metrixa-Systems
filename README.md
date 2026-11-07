# Heidi Engine — Autonomous B2B Lead Discovery, Enrichment & Qualification Pipeline

**Case Study Submission:** AI Agent Builder Application @ **Heidi Systems GmbH**
**Target Domain:** Property Management Companies (*Hausverwaltungen*) in Berlin, Germany

---

## 📊 Live Production Results (Berlin *Hausverwaltungen* Dataset)

| Metric                                                                |           Production Result           | Details                                                                                                                                                                              |
| :-------------------------------------------------------------------- | :------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Total Raw Scraped Listings (Stage 1)**                        |            **1,371**            | Scraped across *Gelbe Seiten* (`405`), *11880.com* (`835`), *VDIV Berlin-Brandenburg* (`30`), *OpenStreetMap Overpass API* (`100`), and *Search Discovery* (`1`) |
| **Unique Qualified Berlin *Hausverwaltungen* (Stage 2)**      |            **1,199**            | Deduplicated via Canonical Domain, E.164 Phone, `RapidFuzz` Token Sort Ratio & `Union-Find` clustering (`167` duplicates merged, `6` non-Berlin/noise filtered)              |
| **🟢 Tier A — High-Priority Target Leads (`Score 70–100`)** |              **33**              | Immediate sales targets managing `1,000–53,300+` units with PropTech portals/ERPs and direct decision-maker contacts                                                              |
| **🟡 Tier B — Qualified Mid-Market Leads (`Score 45–69`)**  |             **409**             | Established Berlin residential property managers                                                                                                                                     |
| **⚪ Tier C — Long-Tail / Small Leads (`Score < 45`)**       |             **757**             | Smaller local property managers across all 12 Berlin *Bezirke*                                                                                                                     |
| **Website & *Impressum* Pages Crawled (Stage 3)**             |          **866 Pages**          | Across `242` verified corporate domains (`/`, `/impressum`, `/team`, `/leistungen`, `/referenzen`, `/kundenportal`)                                                    |
| **PropTech ERP / Customer Portals Detected**                    |         **38 Companies**         | *Casavi, Domus, Immoware24, Haufe PowerHaus / axera, etg24*, and digital tenant/owner portals                                                                                      |
| **Named Decision-Makers Extracted (Stage 4)**                   | **118 Contacts** *(101 Firms)* | *Geschäftsführer*, *Inhaber*, *Vorstand*, and *Prokuristen* extracted from § 5 DDG *Impressum* & Team pages                                                             |
| **Verified / DNS `MX`-Valid Personal Emails (Stage 5)**       |         **99 Companies**         | Strictly non-`info@` personal executive emails verified against `216` live DNS `MX` corporate servers                                                                          |

---

## 📦 Generated Deliverables (Ready to Submit)

1. **Multi-Tab Excel Workbook (`.xlsx` for Google Sheets / Attachment):**👉 [`data/exports/heidi_berlin_hausverwaltungen.xlsx`](./data/exports/heidi_berlin_hausverwaltungen.xlsx)
   * **Tab 1 (`Qualified_Berlin_Leads`):** All **1,199** Berlin property management companies ranked by `Heidi Lead Score (0–100)` across 31 KPI & contact columns.
   * **Tab 2 (`All_Decision_Makers_Contacts`):** All **118** extracted *Geschäftsführer* / decision-makers with personal emails, DNS `MX` server verification, and verbatim evidence quotes.
   * **Tab 3 (`Evidence_And_Audit_Trail`):** All **866** crawled pages with HTTP status codes, DOM ERP/metering signals, and verbatim unit quotes.
   * **Tab 4 (`KPI_Methodology_And_Summary`):** Executive KPI rationale, scoring weights, and live dataset statistics.
2. **Master CSV Deliverable:**👉 [`data/exports/heidi_berlin_leads_master.csv`](./data/exports/heidi_berlin_leads_master.csv)
3. **Task 3 Quantitative Evaluation & Stage Ablation Report:**👉 [`data/exports/evaluation_ablation_report.md`](./data/exports/evaluation_ablation_report.md)
4. **Task 3 Executive Presentation / Methodology Document:**
   👉 [`docs/Working Docs/07_TASK3_EXECUTIVE_PRESENTATION.md`](./docs/Working%20Docs/07_TASK3_EXECUTIVE_PRESENTATION.md)

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

## 🖥️ Rich Terminal UI (TUI) & CLI Usage

Run any stage or inspect the live SQLite database directly from your terminal using `.\heidi.bat` (or `.\.venv\Scripts\python.exe -m heidi_engine`):

```powershell
# 1. View the Rich Terminal UI (TUI) Telemetry Dashboard & Top 25 Tier-A Berlin Leads
.\heidi.bat dashboard --top 25

# 2. Run the Full 6-Stage Pipeline End-to-End
.\heidi.bat run-all

# 3. Run Individual Pipeline Stages
.\heidi.bat init
.\heidi.bat ingest --max-pages 6
.\heidi.bat deduplicate
.\heidi.bat crawl --resolve-urls 10
.\heidi.bat extract --provider auto_fallback   # Supports: deepseek | gemini | nvidia_nim | local_llamacpp | lm_studio | deterministic
.\heidi.bat enrich --search-top 10
.\heidi.bat export
.\heidi.bat evaluate

# 4. Run Unit & Integration Tests
.\.venv\Scripts\pytest.exe -v
```

---

## 📚 Master Engineering Documentation Index (Follow `01` → `07` in Order)

|      Order      | Document File                                                                                                                                                 | What Is Inside                                                                                                                                                                                                                                                                                                                                                                       |
| :--------------: | :------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`01`** | [`docs/01_PRD_AND_REQUIREMENTS_ENGINEERING.md`](./docs/01_PRD_AND_REQUIREMENTS_ENGINEERING.md)                                                               | **Product Requirements Document (PRD):** Heidi Systems business model (*Messdienstleister*), mapping of Task 1, Task 2, Bonus, and Task 3 to functional (`FR-1` to `FR-7`) and non-functional requirements.                                                                                                                                                              |
| **`02`** | [`docs/02_SYSTEM_ARCHITECTURE_AND_TECH_STACK.md`](./docs/02_SYSTEM_ARCHITECTURE_AND_TECH_STACK.md)                                                           | **System Design & Tech Stack:** 6-stage pipeline architecture diagrams, Unified Multi-LLM Router (`llama.cpp`, `LM Studio`, `NVIDIA NIM`, `DeepSeek`, `Gemini`), Unified Search Router (`Local SearXNG` + Native Meta-Search + `Tavily`), library justifications, and repository folder tree.                                                                    |
| **`03`** | [`docs/03_TASK1_INGESTION_SCRAPERS_AND_DEDUPLICATION.md`](./docs/03_TASK1_INGESTION_SCRAPERS_AND_DEDUPLICATION.md)                                           | **Task 1 Blueprint (Market Discovery & Deduplication):** Technical specs for all 5 Berlin scrapers (`Gelbe Seiten`, `11880.com`, `VDIV Berlin-Brandenburg`, `OpenStreetMap Overpass API`, `SearXNG/Tavily`), Berlin PLZ/category filtering, and the `RapidFuzz` + `Union-Find` Entity Resolution algorithm.                                                      |
| **`04`** | [`docs/04_TASK2_KPI_BLUEPRINT_CRAWLER_AND_SCORING_ENGINE.md`](./docs/04_TASK2_KPI_BLUEPRINT_CRAWLER_AND_SCORING_ENGINE.md)                                   | **Task 2 & Bonus Blueprint (KPIs, Crawler, LLM & Lead Scoring):** 5-Pillar Qualifying KPI definitions for submetering, async Website/*Impressum* crawler, DOM PropTech/ERP scanner (`Casavi`, `Domus`, `Wodis`, `Haufe`, `etg24`), Pydantic LLM schema with verbatim evidence checks, personal email/LinkedIn enrichment, and the `0–100` Lead Scoring formula. |
| **`05`** | [`docs/05_DATABASE_SCHEMA_DATA_STRUCTURES_AND_EXPORT_SPEC.md`](./docs/05_DATABASE_SCHEMA_DATA_STRUCTURES_AND_EXPORT_SPEC.md)                                 | **Database Schema & Deliverable Spec:** Complete SQLite WAL ER diagram (`raw_listings`, `companies_golden`, `crawled_pages`, `kpi_extractions`, `decision_makers`, `llm_audit_logs`), crash-recovery state machine, and exact 4-Tab Excel (`.xlsx`) / Google Sheets column layout.                                                                               |
| **`06`** | [`docs/06_TASK3_VALIDATION_EVALUATION_ABLATION_AND_PRESENTATION_BLUEPRINT.md`](./docs/06_TASK3_VALIDATION_EVALUATION_ABLATION_AND_PRESENTATION_BLUEPRINT.md) | **Task 3 Blueprint (Validation, Evaluation, Ablation & Setup):** 4-layer data validation rules, Gold-Set Precision/Recall/F1 metrics, Stage 1–5 Ablation Study table, and native local SearXNG / Multi-LLM configuration.                                                                                                                                                     |
| **`07`** | [`docs/07_TASK3_EXECUTIVE_PRESENTATION.md`](./docs/07_TASK3_EXECUTIVE_PRESENTATION.md)                                                                       | **Task 3 Executive Presentation Deliverable:** Slide-by-slide presentation summarizing our architecture, KPI logic, validation results, and ablation table for Heidi Systems.                                                                                                                                                                                                  |
