# 04 :  Database Schema Evolution, API Contracts & Cockpit UI Integration

**Project Name:** Metrixa Engine (Metrixa Systems B2B PropTech & Submetering Intelligence Platform)
**Document Scope:** Non-Destructive SQLite WAL Migrations, New FastAPI Endpoints, and Next.js Cockpit UI Enhancements
**Document Order:** `04 of 07`

---

## 1. Non-Destructive SQLite Schema Evolution (`src/metrixa_engine/db.py`)

To guarantee **zero data loss** on the existing `data/metrixa_leads.db` (`1,199` Berlin companies), all schema additions use idempotent `CREATE TABLE IF NOT EXISTS` and safe column inspection (`PRAGMA table_info(...)` + `ALTER TABLE ... ADD COLUMN`).

### 1.1 New Tables Added in Phase 2

```sql
-- 1. Capability 2: Official Handelsregister / Commercial Register Verification Table
CREATE TABLE IF NOT EXISTS commercial_register_checks (
    company_id TEXT PRIMARY KEY,
    register_court TEXT,                 -- e.g. 'Amtsgericht Charlottenburg', 'Amtsgericht München'
    register_type TEXT,                  -- 'HRB' | 'HRA' | 'NONE'
    register_number TEXT,                -- e.g. '123456 B'
    canonical_register_key TEXT,         -- e.g. 'DE-Berlin-Charlottenburg-HRB-123456'
    verification_status TEXT NOT NULL,   -- 'VERIFIED_ACTIVE' | 'FORMAT_VALIDATED_LOCAL' | 'UNREGISTERED' | 'MISMATCH'
    legal_form_consistent INTEGER DEFAULT 1,
    verified_directors_json TEXT,        -- JSON array of verified Geschäftsführer
    verification_source TEXT,            -- 'impressum_plus_court_rules' | 'openregister_api'
    checked_at TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies_golden(company_id)
);

-- 2. Capability 4: Bi-Directional CRM Sync Ledger (Protects Sales Rep Dispositions)
CREATE TABLE IF NOT EXISTS crm_sync_ledger (
    company_id TEXT PRIMARY KEY,
    crm_provider TEXT NOT NULL,          -- 'hubspot' | 'pipedrive' | 'salesforce' | 'webhook' | 'local_crm'
    external_crm_id TEXT,                -- ID in remote CRM
    sales_disposition TEXT DEFAULT 'NEW',-- 'NEW' | 'CONTACTED' | 'IN_SEQUENCE' | 'MEETING_BOOKED' | 'DEAL_WON' | 'DISQUALIFIED_BY_SALES'
    assigned_owner TEXT,
    sales_notes TEXT,
    is_sales_locked INTEGER DEFAULT 0,   -- 1 = Pipeline re-runs will NOT overwrite sales_disposition
    last_pushed_at TEXT,
    last_pulled_at TEXT,
    sync_status TEXT DEFAULT 'PENDING',  -- 'SYNCED' | 'PENDING' | 'FAILED' | 'LOCAL_ONLY'
    FOREIGN KEY (company_id) REFERENCES companies_golden(company_id)
);

-- 3. Capability 6: High-Intent Delta Monitoring & Change Trigger Events
CREATE TABLE IF NOT EXISTS company_delta_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL,
    city TEXT DEFAULT 'Berlin',
    event_type TEXT NOT NULL,            -- 'NEW_DECISION_MAKER' | 'ERP_OR_PORTAL_SWITCH' | 'PORTFOLIO_UNITS_GROWTH' | 'METERING_INCUMBENT_CHANGE'
    severity TEXT NOT NULL,              -- 'CRITICAL' | 'HIGH' | 'MEDIUM'
    previous_value TEXT,
    new_value TEXT,
    urgency_score_boost INTEGER DEFAULT 0,
    detected_at TEXT NOT NULL,
    acknowledged INTEGER DEFAULT 0,
    FOREIGN KEY (company_id) REFERENCES companies_golden(company_id)
);

-- 4. Observability & Debugging: Structured Pipeline & Diagnostic Telemetry Log
CREATE TABLE IF NOT EXISTS system_diagnostic_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,                 -- 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
    component TEXT NOT NULL,             -- 'scraper' | 'crawler_spa' | 'handelsregister' | 'email_verifier' | 'crm_sync' | 'delta_monitor' | 'resilience'
    city TEXT DEFAULT 'Berlin',
    company_id TEXT,
    message TEXT NOT NULL,
    details_json TEXT
);
```

### 1.2 Safe Additive Columns on Existing Tables
- `crawled_pages`:
  - `render_engine TEXT DEFAULT 'httpx_static'` (`'httpx_static'` vs `'playwright_chromium'`)
  - `is_spa_hydrated INTEGER DEFAULT 0`
- `decision_makers`:
  - `email_verification_tier TEXT DEFAULT 'MX_VERIFIED'` (`'VALID_DELIVERABLE'` | `'CATCH_ALL_DOMAIN'` | `'MX_AND_SPF_VERIFIED'` | `'MX_VERIFIED'`)
  - `mail_provider TEXT` (e.g., `'Microsoft 365'`, `'Google Workspace'`, `'IONOS'`)
  - `spf_dmarc_status TEXT` (e.g., `'SPF+DMARC_STRICT'`, `'SPF_ONLY'`, `'NONE'`)

---

## 2. New & Enhanced FastAPI REST Endpoints (`src/metrixa_engine/api/server.py`)

| Method & Endpoint | Purpose | Request / Query Params | Response Highlights |
| :--- | :--- | :--- | :--- |
| `GET /api/cities` | Multi-city territory summary across Berlin, Munich, Hamburg, Frankfurt, Cologne | None | List of 5 cities with `valid_plz_ranges`, `districts`, `amtsgericht`, `total_leads`, `tier_a_count`, `verified_units` |
| `GET /api/leads` | Enhanced Lead Explorer query | `?city=Berlin&district=...&tier=...&crm_status=...` | Paginated leads enriched with `handelsregister_status`, `crm_disposition`, `render_engine`, and `delta_alerts_count` |
| `POST /api/scaleup/handelsregister/verify` | Trigger or inspect *Handelsregister* cross-check for a company or batch | `{ "company_id"?: str, "city"?: str }` | Returns normalized `Amtsgericht`, `HRB/HRA` status, legal form consistency, and verified directors |
| `POST /api/scaleup/email/verify-deep` | Run 3-tier Email Verification (`MX` + `SPF/DMARC` + `SMTP/Catch-All`) | `{ "email": str, "domain"?: str }` | Live MX host, mail provider, SPF/DMARC policy, catch-all classification, and deliverability status |
| `GET /api/crm/status` | View CRM sync ledger & sales disposition counts | `?city=Berlin` | Total synced, pending, sales-locked leads, and active CRM connector status |
| `POST /api/crm/sync` | Trigger outbound/inbound CRM sync or update sales disposition | `{ "provider": "hubspot" \| "pipedrive" \| "salesforce" \| "local", "company_ids"?: [...], "sales_disposition"?: str }` | Sync summary (`pushed_count`, `locked_preserved_count`, `ledger_updated`) |
| `POST /api/crm/webhook` | Receive inbound webhook from HubSpot / Pipedrive / Salesforce | `{ "company_id": str, "sales_disposition": str, "sales_notes"?: str }` | Updates `crm_sync_ledger` and sets `is_sales_locked = 1` |
| `GET /api/deltas` | List high-intent sales trigger delta events & run snapshot diff check | `?city=Berlin&severity=CRITICAL` | List of `NEW_DECISION_MAKER`, `ERP_OR_PORTAL_SWITCH`, `PORTFOLIO_UNITS_GROWTH`, and `METERING_INCUMBENT_CHANGE` alerts |
| `POST /api/deltas/scan` | Execute a live delta scan across companies | `{ "city"?: str }` | Newly detected change triggers and updated urgency scores |
| `GET /api/resilience/status` | View Proxy Pool, Rate-Limiter & Circuit Breaker telemetry | None | Active proxy count, per-domain circuit breaker states (`CLOSED`/`OPEN`/`HALF_OPEN`), retry stats |
| `GET /api/diagnostics/logs` | Full structured debug & trace log inspector | `?level=INFO&component=...&trace_id=...` | Live structured logs from `system_diagnostic_logs` and rotating log files |

---

## 3. Next.js Cockpit UI Integration (`web/src/app/`)

1. **Executive Overview (`/`) & Lead Explorer (`/leads`)**:
   - **City Territory Selector Pill Bar**: Switch seamlessly between **All Cities**, **Berlin** (`10115-14199`), **München** (`80331-81929`), **Hamburg** (`20095-22769`), **Frankfurt am Main** (`60306-65936`), and **Köln** (`50667-51149`), dynamically updating the District filter dropdown to the selected city's official *Bezirke / Stadtbezirke*.
   - **Evidence Dossier Drawer Enhancements**:
     - Shows **Handelsregister Badge** (e.g., `Amtsgericht Charlottenburg • HRB Verified`).
     - Shows **3-Tier Email Security & Deliverability Badge** (`MX + SPF/DMARC Verified` / `Microsoft 365`).
     - Shows **CRM Sales Disposition Selector** (`NEW`, `CONTACTED`, `IN_SEQUENCE`, `MEETING_BOOKED`, `DEAL_WON`, `DISQUALIFIED`) with a 1-click save that locks the lead from being overwritten.
     - Shows **Delta Trigger Alerts** if the company recently changed its *Geschäftsführer*, ERP portal, or unit count.
2. **Mission Control (`/mission-control`)**:
   - Adds a **Target City Selector** (`Berlin (Default Case Study)`, `München`, `Hamburg`, `Frankfurt am Main`, `Köln`) and a **Scale-Up Capabilities Status Bar** showing live telemetry for Headless SPA Renderer, Handelsregister Verifier, 3-Tier Email Verifier, CRM Sync Ledger, Proxy/Circuit Breaker, and Delta Monitor.
3. **Tools & Scrapers Catalog (`/tools`)**:
   - Adds interactive live test benches for the 6 new production capabilities so reviewers can test them in real time with custom inputs.
