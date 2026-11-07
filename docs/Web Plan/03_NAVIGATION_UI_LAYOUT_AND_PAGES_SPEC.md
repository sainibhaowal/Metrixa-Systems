# 03 — Navigation Layout, UI Blueprint & Page Specifications: Metrixa Cockpit

**Project Name:** Metrixa Cockpit — Autonomous LeadOps & Metering Intelligence Suite
**Document Order:** `03 of 06` in `docs/Web Plan/`
**Location:** `C:\Users\Ravin\Projects\Projetcs Alpha\Metrixa Systems\docs\Web Plan\03_NAVIGATION_UI_LAYOUT_AND_PAGES_SPEC.md`

---

## 1. Global Navigation & Layout Architecture

Metrixa Cockpit uses a modern **Fixed Sidebar + Sticky Topbar + Dynamic Viewport Layout**. The interface is optimized for high information density, rapid switching between operational views, and persistent system status.

```text
+----------------------------------------------------------------------------------------------------+
|  [LOGO] HEIDI COCKPIT | B2B Berlin Hausverwaltungen    [Global Live Status: READY]  [DB: 1,199 Leads]  |
+-------------------+--------------------------------------------------------------------------------+
|  SIDEBAR NAV      |  PAGE HEADER: Breadcrumbs & Primary Actions (e.g., [Run Stage] [Export XLSX])   |
|                   +--------------------------------------------------------------------------------+
|  [#] Cockpit      |                                                                                |
|  [>] Mission Ctrl |                                                                                |
|  [=] Lead Grid    |                            DYNAMIC PAGE CONTENT VIEW                           |
|  [*] Tool Catalog |                                                                                |
|  [^] Artifacts    |                                                                                |
|  [@] Settings     |                                                                                |
|                   +--------------------------------------------------------------------------------+
|  v1.0.0 (FastAPI) |  [SLIDING EVIDENCE DRAWER / INSPECTOR: Opens from right on lead click]         |
+-------------------+--------------------------------------------------------------------------------+
```

### 1.1 Sticky Topbar Elements
- **Brand Identity:** Metrixa Systems minimalist submetering badge + "Metrixa Cockpit" wordmark.
- **System Heartbeat:** Live pill indicator (`ONLINE` green pulse, `RUNNING` cyan animation, or `IDLE` slate).
- **Target Counter:** Live metric showing `1,199 Deduplicated Berlin Companies`.
- **Quick Action Bar:** Direct 1-click button: `[Download Excel]` and `[Sync Pipeline]`.

### 1.2 Sidebar Navigation Items
1. **📊 Cockpit (Dashboard):** High-level market intelligence, TAM breakdown, tier shares, and district charts.
2. **⚡ Mission Control:** Interactive DAG visualizer, stage runners, and real-time SSE execution logs.
3. **📋 Lead Explorer:** Virtualized 31-column data table with facet filters and inline evidence triggers.
4. **🛠️ Agentic Tools:** Catalog of scrapers, parsers, and DNS verifiers with live health pings.
5. **📁 Artifacts & Vault:** Timestamped exports (`.xlsx`, `.csv`, `.md`), changelog, and Google Sheets link.
6. **⚙️ Settings & Hub:** Provider API keys, model selector (`DeepSeek`, `Gemini`, `Local`), and concurrency limits.

---

## 2. Page Specifications (View by View)

---

### View 1: Executive Cockpit / Dashboard (`/`)

#### Purpose
Gives sales directors and executives an instant, 10-second overview of market penetration across Berlin and qualified leads ready for sales outreach.

#### Key Components
1. **Summary KPI Cards (Top Row, 5 Columns):**
   - **Total Market TAM:** `1,199` Qualified Berlin *Hausverwaltungen*.
   - **Tier A Priority Leads:** `33` companies (Managing `1,000` to `53,300+` units, score $\ge 70$).
   - **Decision-Maker Reachability:** `118` named *Geschäftsführer* (`101` unique companies).
   - **Personal Email Coverage:** `99` companies with verified non-generic corporate emails (`8.3%`).
   - **PropTech ERP Penetration:** `38` companies using Casavi, Immoware24, Domus, Haufe, or etg24.
2. **Chart Matrix (Middle Row, 2 Columns):**
   - **Left: Lead Score Distribution:** Histogram plotting lead counts across score brackets (`90–100`, `80–89`, `70–79`, `50–69`, `<50`).
   - **Right: Berlin District Penetration (Top 12 Bezirke):** Horizontal bar chart showing Charlottenburg-Wilmersdorf, Mitte, Pankow, Tempelhof-Schöneberg, etc.
3. **Strategic Breakdown Cards (Bottom Row, 3 Columns):**
   - **ERP & Portal Adoption:** Progress bars displaying Casavi (`14`), Domus (`11`), Immoware24 (`8`), Haufe (`5`), Customer Portal (`38`).
   - **Asset Focus Distribution:** Donut chart showing WEG-Verwaltung (`91%`), Mietverwaltung (`84%`), Commercial (`18%`).
   - **Source Provenance:** Breakdown of raw records by directory source (11880, Gelbe Seiten, VDIV, OSM).

---

### View 2: Pipeline Mission Control (`/mission-control`)

#### Purpose
Provides real-time interactive execution of the 6 pipeline stages with zero terminal commands needed. Operators can watch stages execute live with streaming logs.

#### Key Components
1. **Interactive Stage Pipeline (Visual DAG):**
   - 5 sequential interactive cards representing:
     - `Stage 1: Multi-Source Berlin Ingest`
     - `Stage 2: Entity Resolution & Dedupe`
     - `Stage 3: Async Website & Impressum Crawl`
     - `Stage 4: Multi-LLM KPI Extraction`
     - `Stage 5: DNS MX Verification & Scoring`
   - Each card displays status (`Completed`, `Running`, `Idle`), last execution timestamp, and a direct `[Run Stage]` button.
   - Master Control Button: `[🚀 Execute Entire Pipeline End-to-End]` and `[🛑 Abort Run]`.
2. **Live SSE Streaming Terminal (Cockpit Feed):**
   - Clean, dark-mode terminal window streaming live events directly from Python via Server-Sent Events.
   - Displays real-time progress bars: `Crawling Berlin Websites [===========>] 242/242 (100%)`.
   - Color-coded logs: `[INFO]` (Cyan), `[EXTRACTED]` (Green), `[MX_VALID]` (Yellow), `[WARNING]` (Orange).
3. **Run History & Metrics Panel:**
   - Table of recent runs, token consumption, latency per company, and hallucination prevention count (`0 blocked`).

---

### View 3: Master Lead Explorer & Data Grid (`/leads`)

#### Purpose
The primary workhorse for sales reps and researchers. Allows instantaneous searching, filtering, and inspection of all 1,199 companies.

#### Key Components
1. **Filter & Search Toolbar (Top):**
   - **Global Search Input:** Live debounce search across Company Name, *Geschäftsführer*, Street, and Domain.
   - **Tier Filter:** Multi-select pills: `[🟢 Tier A (33)]`, `[🟡 Tier B (409)]`, `[⚪ Tier C (757)]`.
   - **Bezirk Dropdown:** Filter by any of the 12 Berlin districts (e.g., Charlottenburg-Wilmersdorf, Mitte).
   - **Feature Toggles:** `[Has Decision Maker]`, `[Has Personal Email]`, `[Uses PropTech ERP]`, `[VDIV Member]`.
   - **Actions:** `[Export Filtered View to CSV]`, `[Reset Filters]`.
2. **Virtualized TanStack Data Grid:**
   - Columns:
     - `Tier` (Color-coded badge)
     - `Score` (Bold score badge $0–100$)
     - `Company Name` (With legal form badge: `GmbH`, `AG`, `e.K.`)
     - `District & PLZ` (e.g., `Mitte (10117)`)
     - `Units Managed` (Explicit count or size tier badge: `11,500 Units`, `1,000-5,000`)
     - `Services` (Small badges for `WEG`, `Miet`, `Gew`)
     - `ERP / Portal` (Badges for `Casavi`, `Immoware24`, `Portal`)
     - `Decision Maker` (Full name & role: `Geschäftsführer`)
     - `Personal Email` (Click-to-copy button with verification icon)
     - `Actions` (`[Inspect Evidence 👁️]` button)
3. **Sliding Evidence Drawer (Triggered by Row Click):**
   - Slides smoothly from the right side without navigating away from the table.
   - Contains 4 tabs:
     - **Tab 1: Overview & Scorecard:** Radar chart of 5 pillars, phone, address, website link.
     - **Tab 2: Decision-Maker Dossier:** Names, roles, personal email, email verification status (`PUBLIC_DIRECT_VERIFIED` / `PATTERN_MX_VERIFIED`), MX server host, direct phone, LinkedIn profile.
     - **Tab 3: Evidence & Anti-Hallucination Audit:** Verbatim German *Impressum* quote, verbatim unit count quote, exact crawled subpage URLs with HTTP status codes.
     - **Tab 4: Technical Stack:** PropTech signatures, detected customer portal, legacy metering incumbents.

---

### View 4: Agentic Tools & Scraper Catalog (`/tools`)

#### Purpose
Demonstrates the engineering breadth of Metrixa Engine by presenting each scraper, parser, and verifier as an independent, testable tool.

#### Key Components
1. **Tool Grid (6 Category Cards):**
   - **Directory Scrapers:**
     - *Gelbe Seiten Berlin Scraper* (Multi-keyword + 23 district shards + base64 decoder).
     - *11880.com Directory Scraper* (HTML + JSON-LD + Cloudflare XOR email-protection decrypter).
     - *VDIV Berlin Association Scraper* (Certified institutional member list).
     - *OpenStreetMap Overpass Scraper* (Geospatial bounding box Berlin).
   - **Search & Long-Tail Agents:**
     - *Local SearXNG Meta-Search* (Native Python / Zero-Docker multi-engine search).
     - *Tavily AI Search Harness* (Deep LinkedIn and missing website resolver).
   - **Parsing & Extraction Engines:**
     - *German § 5 DDG Impressum Engine* (High-precision regex parser for German commercial registers).
     - *Multi-Provider LLM Router* (Pydantic schema enforcer with verbatim evidence gates).
   - **Verification Services:**
     - *DNS MX Mail Exchange Verifier* (RFC-compliant DNS mail server validator).
     - *Corporate Email Pattern Inferrer* (German B2B pattern generator).
2. **Interactive `[Test Tool]` Modal:**
   - Operators can click `[Test Tool]` on any card to run an instantaneous health check and view raw JSON output.

---

### View 5: Artifacts & Export Vault (`/artifacts`)

#### Purpose
Provides one-click access to all generated deliverables for Metrixa Systems' hiring team and internal sales reps.

#### Key Components
1. **Deliverable Cards:**
   - **Master Excel File (`.xlsx`):** Direct download of `metrixa_berlin_hausverwaltungen.xlsx` (`271 KB`, 4 styled tabs).
   - **Master CSV File (`.csv`):** Direct download of `metrixa_berlin_leads_master.csv` (`355 KB`, 31 columns).
   - **Evaluation & Ablation Report (`.md`):** Direct download of `evaluation_ablation_report.md`.
   - **Executive Presentation Deck (`.md`):** Direct download of `07_TASK3_EXECUTIVE_PRESENTATION.md`.
2. **Live Google Sheets Integration Card:**
   - Instructions and 1-click URL to open the synced Google Sheet with sharing set to *"Anyone with the link"*.
3. **Inline Markdown Report Viewer:**
   - Embedded, styled preview of the live Evaluation and Ablation study table directly inside the browser.

---

### View 6: Settings & Provider Configuration Hub (`/settings`)

#### Purpose
Allows the operator to switch LLM backends (Local vs. Cloud) and configure search harnesses without modifying code or restarting the server.

#### Key Components
1. **LLM Provider Hub:**
   - Provider radio selector:
     - `auto_fallback` (Intelligent fallback across configured APIs)
     - `deepseek` (DeepSeek-V3 / R1)
     - `gemini` (Google Gemini 2.5 Flash)
     - `nvidia_nim` (Llama-3.3-70B on NVIDIA NIM)
     - `local_llamacpp` (Local llama.cpp server on `http://127.0.0.1:8080/v1`)
     - `lm_studio` (Local LM Studio on `http://127.0.0.1:1234/v1`)
     - `deterministic` (Pure German legal regex/DOM parsing; $0 cost)
   - Dynamic API Key and Base URL inputs with `[Test Connection]` button (pings model and displays round-trip latency).
2. **Search Harness Settings:**
   - Toggle: `Enable Native Meta-Search (No Docker)`
   - Local SearXNG Base URL override
   - Tavily API Key & Request Budget input
3. **Crawler & Database Controls:**
   - Concurrency slider (`5` to `30` concurrent workers)
   - HTTP Timeout slider (`5s` to `30s`)
   - `[Database Vacuum & Re-Index]` maintenance button
   - `[Save Configuration]` button that automatically updates `.env` and runtime settings.
