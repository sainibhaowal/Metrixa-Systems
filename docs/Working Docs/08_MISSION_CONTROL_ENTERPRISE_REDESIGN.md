# 08 — Mission Control 3-Panel Enterprise Redesign & Operational Blueprint

**Document Reference:** `docs/Working Docs/08_MISSION_CONTROL_ENTERPRISE_REDESIGN.md`
**Parent Specification:** `docs/Web Plan/08_MISSION_CONTROL_3PANEL_ENTERPRISE_SPEC.md`
**Project:** Metrixa Engine / Heidi Systems Intelligence Cockpit
**Status:** Approved for Implementation

---

## 1. Context & Operational Philosophy

The user has reviewed the existing Mission Control page and identified critical improvements needed to make it a **true production-grade business tool**:
1. **The current layout is too basic and static**: It wastes display width, leaving empty black space while squeezing telemetry into a plain terminal box.
2. **Operators have no memory of past runs**: A business owner cannot see run history, when runs occurred, how many leads were produced, or compare *Run #14* vs *Run #15* to detect newly discovered property managers or changed managing directors.
3. **Telemetry lacks dual-mode fidelity**: Business leaders need a **Concise Overview Mode** with progress milestones, while engineers and evaluators need a **Deep-Dive Inspector Mode** that exposes tool calling, prompt token counts, HTTP latencies, DOM signatures, and anti-hallucination verification gates.
4. **Tooling is disconnected**: Testing an MX lookup, an Impressum regex, or an LLM ping requires navigating away from Mission Control to the Tools page.

---

## 2. Structural Breakdown of the 3-Panel Cockpit

### Left Panel (24% Width): "Run History, Audits & Comparison Diff Ledger"
- **Historical Runs Accordion:**
  - Lists historical execution runs (`Run #1`, `Run #2`, ..., `Run #16`) loaded from SQLite `pipeline_runs`.
  - Shows run timestamp, trigger type (`Full Pipeline` vs `Stage 3: Crawler`), runtime duration, leads output, and status badge (`SUCCESS` / `FAILED`).
- **Interactive Run Selector:**
  - Clicking any historical run immediately populates the Middle Panel with that run's telemetry and metrics.
- **Run-to-Run Comparison Diff Engine:**
  - Choose two runs (e.g. *Run #15* and *Run #16*) to view:
    - 🟢 Newly added *Hausverwaltungen* (+12)
    - 🔄 Modified *Geschäftsführer* (+3)
    - ⚡ Detected ERP or customer portal adoptions (+2 Casavi portals)
    - 📈 Portfolio unit growth events

### Middle Panel (52% Width): "Live Telemetry DAG, Multi-Mode Timeline & Event Inspector"
- **Top Bar Controls:**
  - View Toggle: **`[Concise Business Mode]`** vs **`[Deep-Dive Inspector Mode]`**
  - City Scope Selector: `Berlin` (default) | `All Cities` | `München` | `Hamburg` | `Frankfurt` | `Köln`
  - Active Run Indicator with live animated pulse and progress percentage.
- **Visual Dynamic DAG Milestones:**
  - Interactive stages (Stage 1 Ingest ➔ Stage 2 Dedup ➔ Stage 3 Crawler ➔ Stage 4 LLM ➔ Stage 5 MX & Scoring ➔ Stage 6 Excel & Eval).
  - Clicking any stage filters the telemetry stream specifically to that stage.
- **Real-Time Event Stream:**
  - In **Concise Mode**: Clean business-level milestone cards with records processed, time elapsed, and summary KPIs.
  - In **Deep-Dive Mode**: Expandable execution nodes showing exact tool calls (`scan_html_for_tech_and_contacts`, `LLMRouter.extract_kpis`), agent steps, HTTP status codes, latency in ms, raw JSON payloads, and anti-hallucination quote verifications.
- **Event Detail Slide-Over Inspector:**
  - Click any log event to inspect full metadata, request payload, response text, and error stack trace without leaving the page.

### Right Panel (24% Width): "Stage Action Controls & Live Execution Benches"
- **Stage Action Cards (Stages 1 through 6):**
  - Card 1: Multi-Source Ingest (`Gelbe Seiten`, `11880`, `VDIV`, `OSM`, `Search`)
  - Card 2: Entity Deduplication (`Union-Find` + `RapidFuzz` PLZ blocking)
  - Card 3: Async Impressum & DOM Crawler (`httpx` HTTP/2 + Playwright SPA fallback)
  - Card 4: Multi-LLM KPI Extraction (Deterministic § 5 DDG + Live API LLM router)
  - Card 5: MX Verification & Lead Scoring (`DNS MX` + 0–100 commercial scoring)
  - Card 6: Excel Deliverables & Eval (`4-Tab Excel`, CSV, Gold-Set Ablation Report)
  - Each card has an independent "Run Stage" trigger and parameter options (batch size, city filter).
- **Embedded Real-Time Tool Benches:**
  - 🔍 Quick MX Lookup tool
  - ⚡ Impressum Regex Tester
  - 🤖 LLM Ping & Provider Status check
- **Global Execution Button:**
  - Large sticky "Execute Full Pipeline (End-to-End)" button with emergency abort option.

---

## 3. Data Integrity & Case Study Safety Assurance

- **Zero Breaking Changes to Existing APIs:** The existing `/api/pipeline/run` and `/api/pipeline/stream` endpoints remain 100% backward-compatible.
- **Safe Database Addition:** A new table `pipeline_runs` is created automatically in SQLite via `CREATE TABLE IF NOT EXISTS` without modifying or locking the existing `companies_golden` or `raw_listings` tables.
- **Full Widescreen Responsive Design:** Uses modern CSS flexbox/grid (`grid-cols-12`) that spans 100% of the viewport width while remaining clean and responsive on smaller laptop screens.
