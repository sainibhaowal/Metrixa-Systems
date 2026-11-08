# 08 — Next-Gen 3-Panel Mission Control & Historical Telemetry Specification

**Project Name:** Metrixa Cockpit — Pipeline Mission Control Enterprise Redesign
**Scope:** Full-Width 3-Panel Layout (Left History & Runs Drawer, Center Real-Time Telemetry & Stage Visualizer, Right Stage Controls & Manual Tooling) with Comparison Diffs, View Modes (Concise vs. Deep-Dive), and Evidence Traces.
**Location:** `docs/Web Plan/08_MISSION_CONTROL_3PANEL_ENTERPRISE_SPEC.md` and referenced in `docs/Working Docs/`
**Status:** Approved Architectural Specification

---

## 1. Executive Summary & Why the Redesign is Necessary

The current Mission Control page (shown in screenshots) consists of two simple blocks:
1. A standard 6-card grid with "Run Stage" buttons.
2. A single dark terminal box at the bottom.

### 1.1 The Problems in the Current Layout
- **Wasted Screen Space:** The page does not use full screen width; cards are squished and static.
- **Zero Run History / Track Record:** When a run finishes, previous execution metrics, timing, record counts, and errors disappear. A business operator cannot compare "Run #14" with "Run #15".
- **Binary Telemetry View (No Concise vs. Deep-Dive):** Logs are either a raw wall of text or nothing. An executive wants concise high-level progress (e.g., *"Ingested 1,240 records across 5 sources in 42s"*), while a developer or QA engineer wants deep-dive payload inspection (HTTP status, regex matches, LLM prompt tokens, DNS MX response).
- **No Agent/Tool Calling Transparency:** In Stage 4 (LLM KPI extraction) or Stage 3 (Crawler), the user cannot see *which* tool or agent was invoked, what prompt was passed, or how anti-hallucination verification blocked a hallucinated unit quote.

---

## 2. The 3-Panel Enterprise Architecture

To transform Mission Control into an enterprise-grade command center that utilizes 100% of the display width, the layout is partitioned into **Three Interactive Panels**:

```
+-----------------------------------------------------------------------------------------------------------------------------+
|                                              TOP MASTER BAR: STATUS & GLOBAL CONTROLS                                       |
|  Pipeline: IDLE/ACTIVE | Active Run #16 | City: Berlin | Active LLM: OpenAI Platform | Mode: Concise/Deep | Run Full Pipeline|
+-------------------------------------+-------------------------------------------------------+-------------------------------+
| LEFT PANEL (20-25% Width)           | MIDDLE PANEL (50-55% Width)                           | RIGHT PANEL (25% Width)       |
| "Execution History & Run Audit"     | "Live Telemetry, DAG Timeline & Deep-Dive Inspector"  | "Stage Controls & Live Tooling"|
|                                     |                                                       |                               |
| • Runs History List:                | • Top: Interactive Dynamic DAG & Progress Bar         | • 6 Independent Stage Action  |
|   - Run #16 (Today 16:15) - SUCCESS |   [Stage 1] -> [Stage 2] -> [Stage 3] -> ...          |   Cards with Config & Stats:  |
|   - Run #15 (Today 14:02) - SUCCESS | • View Toggle: [Concise Business] / [Deep Inspector]  |   1. Multi-Source Ingest      |
|   - Run #14 (Yesterday)   - DIFF    | • Real-Time Timeline Stream:                          |   2. Deduplication Engine     |
| • Run Metadata:                     |   - Stage 1: Ingested 1,240 rows (Gelbe, 11880, VDIV) |   3. Async Impressum Crawler  |
|   - Duration, records, token spend  |   - Stage 2: Deduplicated -> 1,199 golden (98.2%)     |   4. Multi-LLM KPI Extraction |
| • Historical Comparison Diff Tool:  |   - Stage 3: Crawled 1,199 /impressum (Playwright/H2) |   5. MX Verification & Scoring|
|   - "Compare Run #16 vs Run #15":   |   - Stage 4: LLM Extraction & Anti-Hallucination Gate |   6. Excel Deliverables & Eval|
|     +12 New Companies               |   - Stage 5: DNS MX verified 115 live mail domains    | • Quick Tooling Triggers:     |
|     +3 Changed Geschäftsführer      |   - Stage 6: 4-Tab Excel & Gold Set F1: 94.6%         |   - Test RFC DNS MX query     |
|     +2 ERP Switches (Casavi)        | • Deep-Dive Drawer: Click any log/event to inspect    |   - Test Impressum Regex      |
|                                     |   raw JSON, HTTP payload, LLM prompt & response       |   - Ping Active LLM Provider  |
+-------------------------------------+-------------------------------------------------------+-------------------------------+
```

---

## 3. Detailed Panel Specifications

### 3.1 Left Panel: "Execution History & Run Comparison Ledger"
- **Purpose:** Answers the question *"What happened last time, how did the system perform, and what changed between runs?"*
- **Features:**
  1. **Historical Runs List:**
     - Displays historical runs stored in SQLite (`pipeline_runs` table).
     - Each entry shows: Run Number (`Run #15`), Timestamp (`Today 15:42`), Status (`SUCCESS` / `FAILED`), Duration (`2m 14s`), and Output Count (`1,199 leads`).
  2. **Run Selection & Replay:**
     - Clicking any past run instantly updates the Middle Panel to replay that run's telemetry, stats, and logs.
  3. **Run-to-Run Comparison Diff Engine (`Diff View`):**
     - Compare `Run A` vs `Run B`:
       - **New Leads Found:** Companies present in Run B but not in Run A.
       - **Decision Maker Changes:** Geschäftsführer appointed or removed.
       - **Tech Stack Updates:** Hausverwaltungen that adopted *Casavi*, *Domus*, or switched from *Techem* to *ista*.
       - **Units Portfolio Growth:** Companies whose reported managed units increased.

### 3.2 Middle Panel: "Interactive Live Timeline & Multi-Mode Telemetry Stream"
- **Purpose:** Real-time visibility into the running engine with two user-switchable modes.
- **Features:**
  1. **Mode Switcher:**
     - **`Concise Business Mode` (For Executives / Sales Leaders):**
       - High-level status cards for each stage.
       - Clean milestones: *"Stage 1 Completed: 1,240 records ingested across 5 sources in 41s"*.
       - Live progress bar with ETA countdown and records processed counter.
     - **`Deep-Dive Engineer Mode` (For Developers / Audits):**
       - Expandable event nodes showing exact tool invocations, agent steps, HTTP request/response codes, latency graphs, LLM token usages, and anti-hallucination quote verifications.
  2. **Visual DAG Progression Timeline:**
     - Six sequential nodes with live pulsating status rings:
       - ⚪ `PENDING` → 🔵 `RUNNING` (with live spinner & item counter) → 🟢 `COMPLETED` / 🔴 `FAILED`.
  3. **Event Detail Drawer (Click-to-Inspect):**
     - Clicking on any event opens an inspector drawer showing:
       - `Tool Call`: `scan_html_for_tech_and_contacts` or `LLMRouter.extract_kpis`
       - `Input Payload`: URL crawled, HTML chunk, or LLM prompt.
       - `Verification Status`: Quote match confirmed in source text vs. blocked hallucination.
       - `Latency & Memory`: Execution time in milliseconds.

### 3.3 Right Panel: "Stage Execution Controls & Direct Tooling Benches"
- **Purpose:** Direct manual control over the pipeline and instant test tools.
- **Features:**
  1. **Individual Stage Execution Cards (Stages 1 through 6):**
     - Each stage card features:
       - Title & Purpose badge.
       - Average execution time (`~45s`).
       - Parameter controls (e.g., Target City filter, Concurrency level, Sample run size `All` vs `First 20`).
       - Distinct "Run Stage" button with immediate live feedback.
  2. **Global Emergency & Management Actions:**
     - "Execute Full Pipeline (End-to-End)" button.
     - "Pause / Stop Pipeline" button.
     - "Export Current Telemetry Log (JSON / TXT)" button.
  3. **Embedded Real-Time Tooling Benches:**
     - Test individual functions right from Mission Control:
       - 🔍 *RFC 5321 MX Query Tester* (test any domain's mail host in 50ms).
       - ⚡ *DOM Impressum Regex Tester* (paste sample German HTML and extract Geschäftsführer).
       - 🤖 *LLM 10-Token Ping* (test active provider latency without running a full batch).

---

## 4. Backend Database & API Requirements

### 4.1 New SQLite Table: `pipeline_runs`
```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,             -- e.g. 'run-20261108-161500'
    run_number INTEGER NOT NULL,         -- 1, 2, 3...
    trigger_type TEXT NOT NULL,          -- 'MANUAL_FULL' | 'MANUAL_STAGE' | 'CRON_SCHEDULED'
    target_city TEXT DEFAULT 'Berlin',
    active_stage TEXT,
    status TEXT NOT NULL,                -- 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
    total_companies_in INTEGER DEFAULT 0,
    total_companies_out INTEGER DEFAULT 0,
    new_companies_found INTEGER DEFAULT 0,
    changed_kpis_count INTEGER DEFAULT 0,
    duration_seconds REAL DEFAULT 0.0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_message TEXT,
    summary_metrics_json TEXT
);
```

### 4.2 New REST Endpoints in `src/heidi_engine/api/server.py`
- `GET /api/pipeline/runs`: List historical runs with duration, counts, and status.
- `GET /api/pipeline/runs/{run_id}`: Get full telemetry events, logs, and stage breakdowns for a specific run.
- `GET /api/pipeline/runs/compare?run_a={id}&run_b={id}`: Compute exact diff of newly discovered companies, changed decision makers, and ERP switches between two runs.
- `POST /api/pipeline/stop`: Safely abort a running stage or pipeline.

---

## 5. UI/UX Design System Specifications

1. **Full-Width Canvas Utilization:**
   - Remove `max-w-7xl` constraint and use `w-full px-4 sm:px-6 lg:px-8 py-6` to make complete use of modern widescreen displays (1920x1080 and ultrawides).
2. **Matte Dark Theme Aesthetic:**
   - Deep background `#0c0c0e`, surface `#111114`, borders `#27272a` (Zinc 800), accents in `#10b981` (Emerald 500) and `#38bdf8` (Sky 400).
3. **Responsive Collapse:**
   - On screens `< 1280px`, Left and Right panels convert into collapsible slide-over drawers so the Middle Telemetry timeline always maintains full readability.
