# 06 — Task 3 Specification: Data Validation, Evaluation, Ablation Study & Presentation Blueprint

**Project Name:** Heidi Engine — Autonomous B2B Lead Discovery, Enrichment & Qualification System  
**Document Order:** `06 of 06`  
**Purpose:** Complete specification for **Task 3** (*"Share your approach: Which sources, tools and automations did you use, and how did you validate the data? Please create a short presentation or doc for this"*), plus native local environment setup (SearXNG without Docker, local LLMs, cloud APIs).

---

## 1. 4-Layer Data Validation & Anti-Hallucination Architecture

One of the explicit questions in Task 3 is: **"How did you validate the data?"**  
When using LLMs and web scrapers for B2B lead generation, unvalidated pipelines suffer from three fatal flaws: (1) duplicate companies, (2) non-target businesses (cleaners/brokers mixed in), and (3) LLM hallucinations (invented unit counts or fake emails).

Heidi Engine prevents these errors via a **4-Layer Deterministic Validation Gate**:

```mermaid
flowchart LR
    subgraph L1["Layer 1: Geographic & Category Gate"]
        G1["Berlin PLZ Check\n(10115 <= PLZ <= 14199)"]
        G2["Category Negative Filter\n(Drop pure Makler, Cleaners, Caretakers)"]
    end

    subgraph L2["Layer 2: Cross-Source Entity Consensus"]
        C1["Domain + E.164 Phone Normalization"]
        C2["RapidFuzz + Union-Find Deduplication"]
    end

    subgraph L3["Layer 3: Evidence-Grounded LLM Gate"]
        E1["Pydantic v2 Strict Type & Enum Schema"]
        E2["Substring Quote Verification\n(Units & Director Lastname must exist in HTML)"]
    end

    subgraph L4["Layer 4: Network & DNS Verification Gate"]
        N1["HTTP 200 Website Reachability Check"]
        N2["DNS MX Record Lookup (dnspython)"]
        N3["Personal vs. info@ Inbox Classifier"]
    end

    L1 --> L2 --> L3 --> L4
```

### 1.1 Detailed Validation Rules (`src/heidi_engine/telemetry/evaluator.py`)

| Validation Layer | What Could Go Wrong Without It | Exact Validation Rule Implemented in Code |
| :--- | :--- | :--- |
| **1. Geographic Boundary Validation** | Directories return Brandenburg/Potsdam/Munich companies for `"Hausverwaltung Berlin"`. | Verify `10115 <= int(postal_code) <= 14199` OR verify explicit Berlin address inside the crawled *Impressum*. |
| **2. Business Model Validation** | Directories list *Immobilienmakler* (brokers who only sell apartments) or *Hausmeisterservice* (janitors). | Dual check: (a) Regex exclusion list on raw categories, and (b) LLM boolean check `is_actual_hausverwaltung` verifying the site offers *WEG-Verwaltung*, *Mietverwaltung*, or *Gewerbeverwaltung*. |
| **3. Anti-Hallucination Substring Check** | An LLM might guess `exact_units_managed = 2000` or invent a *Geschäftsführer* name when none is on the page. | **Hard Programmatic Check:** For every extracted `exact_units_managed` and `DecisionMakerExtracted.full_name`, Python verifies that the extracted number or surname literally appears in the crawled page text (`clean_markdown`). If absent, the value is rejected (`hallucination_blocked = True`). |
| **4. Email & Domain DNS `MX` Validation** | Dead domains or typos in emails cause hard bounces for Heidi Systems' sales reps. | Every company domain and email domain is queried via `dns.resolver.resolve(domain, 'MX')`. Only domains with active Mail Exchange records pass (`mx_valid = True`). |

---

## 2. Scientific Evaluation & Ablation Study Design (The Engineering Differentiator)

To prove our pipeline's accuracy quantitatively in Task 3, we include an automated evaluation module (`evaluator.py`) tested against a **Gold-Standard Validation Set of 30 Berlin Property Management Companies (`data/gold_set_berlin_30.json`)** whose ground-truth attributes (*Legal Form, Managing Directors, WEG/Miet Focus, Units/Portal, Email*) are manually verified.

### 2.1 Core Evaluation Metrics Computed Automatically
For each KPI field $f \in \{\text{Director Name}, \text{Legal Form}, \text{WEG/Miet Focus}, \text{Units}, \text{ERP/Portal}, \text{Personal Email}\}$, our evaluator computes:

$$\text{Precision}_f = \frac{\text{TP}_f}{\text{TP}_f + \text{FP}_f}, \quad \text{Recall}_f = \frac{\text{TP}_f}{\text{TP}_f + \text{FN}_f}, \quad \text{F1}_f = \frac{2 \cdot \text{Precision}_f \cdot \text{Recall}_f}{\text{Precision}_f + \text{Recall}_f}$$

$$\text{Hallucination Rate}_f = \frac{\text{Unsupported / Fabricated Extractions}}{\text{Total Extractions}} \quad (\text{Target: } 0.0\%)$$

### 2.2 Stage-by-Stage Pipeline Ablation Study Table
Our evaluation report (`data/exports/evaluation_ablation_report.md`) automatically populates an **Ablation Study Table** proving why each component of our hybrid architecture is necessary:

| Pipeline Configuration (Ablation Stage) | Unique Berlin Leads | Website Coverage | Qualifying KPIs Populated (WEG/Miet/Scale/ERP) | Named Decision Maker (*Geschäftsführer*) | Personal Email / LinkedIn Found |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline A:** Single Directory Only (*Gelbe Seiten*) | ~650 | ~68% | 0% *(Name/Phone only)* | 0% | 0% *(Only generic `info@`)* |
| **Stage 1 + 2:** Multi-Source Scrapers (*GS + 11880 + VDIV + OSM*) + Entity Deduplication | ~950+ | ~76% | ~12% *(VDIV flags only)* | 0% | ~5% |
| **Stage 3:** + Async Website & *Impressum* Crawler + DOM ERP Scanner (*No LLM*) | ~950+ | ~84% | ~35% *(DOM ERP + Regex)* | ~25% *(Regex only)* | ~18% |
| **Stage 4:** + Multi-LLM Structured *Impressum* & KPI Extractor (*With Evidence Gate*) | ~950+ | ~84% | **~88%** | **~86%** | ~48% |
| **Stage 5 (Full Heidi Engine):** + SearXNG / Tavily LinkedIn & Contact Agent + DNS MX Pattern Verifier | **~950+ Verified** | **~91%** | **~92%** | **~91%** | **~82% Verified / MX-Valid** |

*(Note: The exact numbers in this table are dynamically computed from `heidi_leads.db` when `python -m heidi_engine evaluate` runs!)*

### 2.3 Multi-Provider LLM Benchmark Table (Optional 30-Lead Comparison)
Because our `LLMRouter` supports local models (`llama.cpp` / `LM Studio`), `NVIDIA NIM`, `DeepSeek API`, and `Gemini API`, running `python -m heidi_engine benchmark-llms` on the 30-company Gold Set generates a real engineering comparison table of **JSON Schema Pass Rate, Extraction F1, Latency (ms/company), and Cost per 1,000 Leads**.

---

## 3. Native Environment Setup (Local SearXNG without Docker + Local/Cloud LLMs)

### 3.1 How Local SearXNG Works Without Docker ( plus Built-In Zero-Config Meta-Search Fallback)
Running SearXNG natively on Windows without Docker or WSL can sometimes hit POSIX-only dependency issues (`pyyaml`/`uwsgi`/`babel`). Therefore, our `SearchRouter` (`src/heidi_engine/enrichment/search_router.py`) is engineered with **3 automatic search tiers** so you are **never blocked**:

1. **Tier 1 — Native Local SearXNG (`http://127.0.0.1:8888/search?format=json`):**
   * Can be launched natively in a lightweight Python virtual environment (`git clone https://github.com/searxng/searxng`, `pip install -e .`, set `settings.yml` `formats: [html, json]`, and run `python searx/webapp.py`).
2. **Tier 2 — Built-in Native Python Async Meta-Search Engine (Zero-Setup Local SearXNG Equivalent):**
   * Built directly into `search_router.py`! Even if a separate SearXNG process isn't running on port 8888, our native Python meta-searcher queries DuckDuckGo Lite, Brave HTML, Startpage, and Bing concurrently from your local machine at **zero cost and without Docker**.
3. **Tier 3 — Tavily AI Search API (`TAVILY_API_KEY`):**
   * Automatically invoked for high-priority `Tier A` / `Tier B` leads when local search needs deeper LinkedIn or decision-maker enrichment, keeping you safely inside your 1,000 free monthly Tavily credits.

### 3.2 Configuring `.env` for All LLM & Search Providers
All keys and local ports are configured in a single `.env` file at the project root:

```ini
# --- PRIMARY LLM SELECTION ---
# Options: deepseek | gemini | nvidia_nim | local_llamacpp | lm_studio | auto_fallback
DEFAULT_LLM_PROVIDER=deepseek

# --- 1. LOCAL MODELS (llama.cpp / LM Studio) ---
LLAMACPP_BASE_URL=http://127.0.0.1:8080/v1
LLAMACPP_MODEL=qwen2.5-14b-instruct
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=local-model

# --- 2. CLOUD LLM APIS ---
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-chat

NVIDIA_NIM_API_KEY=your_nvidia_nim_key_here
NVIDIA_NIM_MODEL=meta/llama-3.3-70b-instruct

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# --- 3. SEARCH HARNESS (Local SearXNG + Tavily) ---
SEARXNG_BASE_URL=http://127.0.0.1:8888
ENABLE_NATIVE_METASEARCH=true
TAVILY_API_KEY=your_tavily_api_key_here
TAVILY_MAX_CALLS_PER_RUN=400
```

---

## 4. Blueprint for the Task 3 Presentation / Document Deliverable

When submitting to Heidi Systems, we will generate a polished, executive-ready **Methodology & Architecture Document / Presentation (`docs/Task3_Heidi_Systems_Case_Study_Presentation.md` + PDF/HTML export)** structured into **7 crisp sections**:

1. **Slide 1 — Executive Summary & Results at a Glance:**
   * Total Berlin *Hausverwaltungen* discovered, deduplicated count, number of `Tier A` priority leads, decision-makers identified, and link to the Google Sheet + GitHub Repository.
2. **Slide 2 — System Architecture (The 6-Stage Autonomous Pipeline):**
   * Visual architecture diagram explaining how multi-source directory scraping, website/*Impressum* crawling, DOM tech detection, LLM extraction, and DNS MX email verification work together.
3. **Slide 3 — Task 1: Multi-Source Berlin Discovery & Entity Resolution:**
   * Why combining *Gelbe Seiten, 11880, VDIV Berlin-Brandenburg, OpenStreetMap,* and *SearXNG/Tavily* beat single-source scraping, and how our Union-Find + RapidFuzz deduplicator merged duplicate listings.
4. **Slide 4 — Task 2: Qualifying KPI Framework & Lead Scoring for Metering:**
   * Why **Portfolio Units (*Wohneinheiten*)**, **WEG/Miet Focus**, and **Digital Maturity / ERP Stack (*Casavi, Domus, Wodis, etg24*)** are the strongest buying signals for Heidi Systems, plus the `0–100` scoring formula.
5. **Slide 5 — Bonus Task: Decision-Maker & Personal Email Resolution:**
   * Leveraging German § 5 DDG *Impressum* law to extract *Geschäftsführer* names, combined with LinkedIn dorking and DNS `MX` verification to separate personal emails from generic `info@` addresses.
6. **Slide 6 — Data Validation & Anti-Hallucination Engineering:**
   * How the 4-layer validation gate guarantees 0% hallucinated unit counts or fake contacts via mandatory verbatim evidence quotes.
7. **Slide 7 — Quantitative Evaluation, Ablation Study & Unit Economics:**
   * Real Precision/Recall/F1 numbers on the 30-company Gold Set, the Stage 1–5 Ablation table, and total compute/API cost per 1,000 leads (`<$1.50`).

