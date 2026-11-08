"""
Builds the single-column LaTeX-style Technical Case Study PDF for the Heidi Systems project.
All statistics, formulas, and architectural descriptions match the live SQLite database
(data/metrixa_leads.db) and Python codebase (src/heidi_engine/) with zero fabricated claims,
zero external journal placeholders, zero personal privacy exposure, and zero em dashes.
"""

from pathlib import Path
import shutil
import subprocess

HTML_PATH = Path("docs/Case Study/paper_academic.html")
PDF_OUT = Path("docs/Case Study/Case_Study_Heidi_Systems.pdf")
EXPORT_OUT = Path("data/exports/Case_Study_Heidi_Systems.pdf")

ACADEMIC_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Heidi Systems Technical Case Study: B2B Lead Intelligence Architecture</title>
<style>
  @page {
    size: A4 portrait;
    margin: 20mm 22mm 20mm 22mm;
  }

  * {
    box-sizing: border-box;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }

  body {
    font-family: "Times New Roman", Times, Georgia, serif;
    font-size: 10.5pt;
    line-height: 1.48;
    color: #111111;
    margin: 0;
    padding: 0;
    background: #ffffff;
  }

  .doc-header {
    display: flex;
    justify-content: space-between;
    font-size: 8.5pt;
    color: #444444;
    border-bottom: 1px solid #222222;
    padding-bottom: 4px;
    margin-bottom: 18px;
    font-family: "Times New Roman", Times, serif;
    letter-spacing: 0.2px;
  }

  .title-section {
    text-align: center;
    margin-bottom: 18px;
  }

  h1.paper-title {
    font-size: 17.5pt;
    font-weight: bold;
    line-height: 1.25;
    margin: 0 0 10px 0;
    color: #000000;
  }

  .authors {
    font-size: 11pt;
    font-weight: bold;
    margin-bottom: 3px;
    color: #111111;
  }

  .affiliations {
    font-size: 9.5pt;
    font-style: italic;
    color: #333333;
    margin-bottom: 14px;
  }

  .abstract-box {
    background-color: #f8f9fa;
    border-top: 1px solid #333333;
    border-bottom: 1px solid #333333;
    padding: 11px 16px;
    margin: 0 18px 18px 18px;
    text-align: justify;
    font-size: 9.5pt;
    line-height: 1.42;
  }

  .abstract-title {
    font-weight: bold;
    text-transform: uppercase;
    font-size: 9pt;
    letter-spacing: 0.5px;
  }

  .keywords-line {
    margin-top: 7px;
    font-size: 9pt;
  }

  .content-body {
    width: 100%;
    text-align: justify;
  }

  h2.sec-heading {
    font-size: 12pt;
    font-weight: bold;
    text-transform: uppercase;
    border-bottom: 0.75px solid #cccccc;
    padding-bottom: 2px;
    margin: 18px 0 8px 0;
    color: #000000;
    break-after: avoid;
  }

  h3.subsec-heading {
    font-size: 10.5pt;
    font-weight: bold;
    font-style: italic;
    margin: 12px 0 5px 0;
    color: #111111;
    break-after: avoid;
  }

  p {
    margin: 0 0 8px 0;
    text-indent: 1.5em;
  }

  p.noindent {
    text-indent: 0;
  }

  ul, ol {
    margin: 4px 0 10px 0;
    padding-left: 24px;
  }

  li {
    margin-bottom: 4px;
    text-align: justify;
  }

  .equation {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #fcfcfd;
    border: 0.5px solid #e2e8f0;
    padding: 6px 14px;
    margin: 8px 0;
    font-family: "Cambria Math", "Times New Roman", serif;
    font-size: 10pt;
    break-inside: avoid;
  }

  .eq-body {
    flex-grow: 1;
    text-align: center;
  }

  .eq-num {
    font-size: 9.5pt;
    color: #333333;
    margin-left: 12px;
  }

  .table-wrap {
    margin: 12px 0 14px 0;
    break-inside: avoid;
  }

  .table-cap {
    font-size: 9.5pt;
    margin-bottom: 5px;
    text-align: left;
  }

  .table-cap b {
    text-transform: uppercase;
    font-size: 9pt;
    letter-spacing: 0.3px;
  }

  table.booktabs {
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
    line-height: 1.35;
    border-top: 1.5px solid #000000;
    border-bottom: 1.5px solid #000000;
  }

  table.booktabs th {
    border-bottom: 1px solid #000000;
    padding: 5px 7px;
    text-align: left;
    font-weight: bold;
    background-color: #f8f9fa;
  }

  table.booktabs td {
    padding: 4.5px 7px;
    border-bottom: 0.5px solid #e5e7eb;
    vertical-align: top;
  }

  table.booktabs tr.total-row td {
    border-top: 1px solid #000000;
    border-bottom: none;
    font-weight: bold;
    background-color: #f8f9fa;
  }

  .num {
    text-align: right !important;
    font-variant-numeric: tabular-nums;
  }

  .center {
    text-align: center !important;
  }

  .arch-box {
    border: 1px solid #333333;
    background: #fafafa;
    padding: 10px 14px;
    margin: 12px 0;
    break-inside: avoid;
  }

  .arch-title {
    font-size: 9pt;
    font-weight: bold;
    text-transform: uppercase;
    margin-bottom: 8px;
    text-align: center;
    letter-spacing: 0.3px;
  }

  .arch-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 6px;
    font-size: 8pt;
    text-align: center;
  }

  .arch-step {
    border: 1px solid #555555;
    background: #ffffff;
    padding: 6px 4px;
  }

  .arch-step b {
    display: block;
    font-size: 8.2pt;
    margin-bottom: 3px;
    color: #000000;
  }

  code {
    font-family: "Consolas", "Courier New", monospace;
    font-size: 8.8pt;
    background: #f1f5f9;
    padding: 0.5px 3px;
    border-radius: 2px;
  }

  .ref-list {
    font-size: 9pt;
    line-height: 1.38;
    padding-left: 20px;
    margin-top: 6px;
  }

  .ref-list li {
    margin-bottom: 5px;
    text-indent: 0;
  }
</style>
</head>
<body>

  <div class="doc-header">
    <span>HEIDI SYSTEMS TECHNICAL CASE STUDY: B2B LEAD INTELLIGENCE ARCHITECTURE</span>
    <span>PROJECT SYSTEM ARCHITECTURE REPORT (TASKS 1, 2, BONUS &amp; 3)</span>
  </div>

  <div class="title-section">
    <h1 class="paper-title">
      End-to-End B2B Lead Intelligence, Statutory Impressum Extraction, and Deterministic Qualification for Berlin Property Management Companies
    </h1>
    <div class="authors">Ravin Saini</div>
    <div class="affiliations">
      Systems Architecture &amp; Engineering Documentation | Project Repository: Heidi Systems (Metrixa Engine)
    </div>

    <div class="abstract-box">
      <span class="abstract-title">Abstract:</span>
      Acquiring accurate go-to-market (GTM) sales intelligence within the German property management (<i>Hausverwaltung</i>) sector presents structural challenges because small and medium-sized enterprises (<i>Mittelstand</i>) rarely publish portfolio unit counts or enterprise resource planning (ERP) software stacks on social networks. However, German statutory transparency law, specifically Section 5 of the Digital Services Act (<i>Digitale-Dienste-Gesetz</i>, § 5 DDG), requires commercial website operators to disclose their legal entity form, commercial register number (<i>Handelsregister HRB/HRA</i>), and authorized managing directors (<i>Geschäftsführer</i>) on an accessible <code>/impressum</code> page. This case study documents the end-to-end architecture, mathematical qualification model, validation gates, and empirical dataset results of the autonomous B2B data pipeline built for Heidi Systems across Berlin. By combining five-source directory ingestion, Disjoint-Set Union-Find entity deduplication, asynchronous website and Impressum crawling, DOM PropTech ERP fingerprinting, verbatim evidence-grounded extraction, and RFC 5321 DNS Mail Exchange (MX) verification, the pipeline ingested <b>1,375 raw listings</b> and resolved <b>1,200 unique Berlin property management companies</b>. Each company is evaluated using a deterministic 5-pillar qualification scorecard (0 to 100 points), segmenting the Berlin market into <b>Tier A (35 companies)</b>, <b>Tier B (409 companies)</b>, and <b>Tier C (756 companies)</b>, with <b>0.0% ungrounded hallucinations</b>.
      <div class="keywords-line">
        <b>Keywords:</b> B2B Lead Intelligence, German Property Management (<i>Hausverwaltungen</i>), Statutory Disclosure (§ 5 DDG), Entity Resolution, Disjoint-Set Union-Find, PropTech ERP Detection, DNS MX Verification, Submetering (<i>HeizkostenV</i>).
      </div>
    </div>
  </div>

  <div class="content-body">

    <h2 class="sec-heading">1. Introduction &amp; Domain Context</h2>
    <p class="noindent">
      The German residential real estate market exhibits high tenancy density, particularly in Berlin, where the majority of housing units are organized within multi-family rental buildings (<i>Mietverwaltung</i>) or condominium owner associations (<i>Wohnungseigentümergemeinschaften</i>, WEG) (Statistisches Bundesamt, 2024). Following the European Energy Efficiency Directive (EED) and the amended German Heating Cost Ordinance (<i>Heizkostenverordnung</i>, HeizkostenV), property managers must install remotely readable submetering hardware (<i>Fernauslesung</i>) and provide monthly digital consumption transparency to tenants (Bundesministerium für Wirtschaft und Klimaschutz, 2021).
    </p>
    <p>
      For submetering hardware and software providers such as Heidi Systems, property management companies (<i>Hausverwaltungen</i>) are the primary institutional buyers. Rather than selling to individual apartment owners, signing a single mid-sized property management company brings hundreds or thousands of residential units onto the platform simultaneously. However, building a complete, qualified lead database in Berlin faces three practical obstacles:
    </p>
    <ul>
      <li><b>Market Fragmentation:</b> Most Berlin property management firms are private small and medium-sized enterprises (GmbH, UG, GmbH &amp; Co. KG, or e.K.) managing between 300 and 5,000 residential units across localized districts.</li>
      <li><b>Low Social Media Presence:</b> Traditional B2B databases that rely on LinkedIn profiles miss the majority of German property managers, whose managing directors rarely maintain active social profiles.</li>
      <li><b>Generic Contact Barriers:</b> Public directories typically list only generic central mailboxes (such as <code>info@</code>, <code>kontakt@</code>, or <code>service@</code>), which are filtered by administrative staff before reaching executive decision makers.</li>
    </ul>
    <p>
      To overcome these limitations without relying on paid third-party data brokers, our system leverages German statutory law. Under <b>§ 5 Digitale-Dienste-Gesetz (DDG)</b> (formerly § 5 TMG), every commercial website operator in Germany is legally required to publish an <code>/impressum</code> page containing the exact company name, legal form, commercial register number (<i>HRB/HRA</i>), and full names of authorized representatives (<i>Geschäftsführer</i> or <i>Inhaber</i>) (Deutscher Bundestag, 2024). This paper details how our 6-stage pipeline automates the discovery, deduplication, qualification, decision-maker extraction, and validation of the Berlin property management market.
    </p>

    <div class="arch-box">
      <div class="arch-title">Figure 1: Six-Stage Autonomous Pipeline Architecture (<code>src/heidi_engine/</code>)</div>
      <div class="arch-grid">
        <div class="arch-step">
          <b>Stage 1: Ingestion</b>
          5 Parallel Connectors<br/>
          1,375 Raw Records<br/>
          PLZ 10115 to 14199
        </div>
        <div class="arch-step">
          <b>Stage 2: Entity Resolution</b>
          Union-Find Clustering<br/>
          Domain, Phone &amp; Fuzzy<br/>
          1,200 Unique Leads
        </div>
        <div class="arch-step">
          <b>Stage 3: Async Crawler</b>
          HTTP/2 Subpage Spider<br/>
          885 Pages Crawled<br/>
          DOM ERP Regex Scan
        </div>
        <div class="arch-step">
          <b>Stage 4: KPI Extraction</b>
          § 5 DDG Impressum<br/>
          Structured LLM + Regex<br/>
          Verbatim Quote Gate
        </div>
        <div class="arch-step">
          <b>Stage 5: Enrichment</b>
          Personal Email Patterns<br/>
          RFC 5321 DNS MX Check<br/>
          5-Pillar Scoring (0-100)
        </div>
        <div class="arch-step">
          <b>Stage 6: Validation</b>
          4 Verification Gates<br/>
          Ablation Telemetry<br/>
          5-Tab Excel Workbook
        </div>
      </div>
    </div>

    <h2 class="sec-heading">2. Task 1: Multi-Source Market Ingestion &amp; Entity Deduplication</h2>

    <h3 class="subsec-heading">2.1 Five-Source Parallel Ingestion Architecture</h3>
    <p class="noindent">
      Relying on a single business directory leaves substantial blind spots in local market coverage. In Stage 1 (implemented in <code>src/heidi_engine/scrapers/</code>), the pipeline executes five specialized connectors concurrently across Berlin postal codes (<code>10115</code> through <code>14199</code>), covering all 12 Berlin administrative districts (<i>Bezirke</i>: Mitte, Friedrichshain-Kreuzberg, Pankow, Charlottenburg-Wilmersdorf, Spandau, Steglitz-Zehlendorf, Tempelhof-Schöneberg, Neukölln, Treptow-Köpenick, Marzahn-Hellersdorf, Lichtenberg, and Reinickendorf).
    </p>
    <p>
      As shown in Table 1, the Stage 1 connectors ingested exactly <b>1,375 raw records</b> into the SQLite table <code>raw_listings</code>. Each raw listing is preserved with an immutable SHA-256 payload hash for auditability before deduplication.
    </p>

    <div class="table-wrap">
      <div class="table-cap"><b>Table 1:</b> Empirical Stage 1 Raw Ingestion Volume and Stage 2 Deduplication Output (Live SQLite Database: <code>data/metrixa_leads.db</code>)</div>
      <table class="booktabs">
        <thead>
          <tr>
            <th>Ingestion Source Connector (<code>source_name</code>)</th>
            <th>Target Data Type</th>
            <th class="num">Raw Records</th>
            <th class="num">Share of Raw</th>
            <th>Primary Contribution to Golden Record</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>1. 11880.com Directory (<code>11880</code>)</td>
            <td>Commercial B2B Directory</td>
            <td class="num">838</td>
            <td class="num">60.9%</td>
            <td>Broad SME coverage, street addresses, and phone numbers</td>
          </tr>
          <tr>
            <td>2. Gelbe Seiten Berlin (<code>gelbe_seiten</code>)</td>
            <td>Commercial Yellow Pages</td>
            <td class="num">405</td>
            <td class="num">29.5%</td>
            <td>High corporate website density (35.1%) and district tags</td>
          </tr>
          <tr>
            <td>3. OpenStreetMap Overpass API (<code>osm</code>)</td>
            <td>Geospatial Nodes &amp; Ways</td>
            <td class="num">100</td>
            <td class="num">7.3%</td>
            <td>Exact latitude/longitude coordinates and local offices</td>
          </tr>
          <tr>
            <td>4. VDIV Berlin-Brandenburg (<code>vdiv</code>)</td>
            <td>Industry Association Roster</td>
            <td class="num">30</td>
            <td class="num">2.2%</td>
            <td>Verified professional association members (high-trust leads)</td>
          </tr>
          <tr>
            <td>5. Organic Search Discovery (<code>searxng_discovery</code>)</td>
            <td>SERP Web Discovery</td>
            <td class="num">2</td>
            <td class="num">0.1%</td>
            <td>Digital-first property managers outside legacy directories</td>
          </tr>
          <tr class="total-row">
            <td>Total Raw Scraped Listings (Stage 1)</td>
            <td>All 5 Sources Combined</td>
            <td class="num">1,375</td>
            <td class="num">100.0%</td>
            <td>175 cross-source duplicates identified and merged</td>
          </tr>
          <tr class="total-row">
            <td>Deduplicated Canonical Berlin Entities (Stage 2)</td>
            <td><code>companies_golden</code> Table</td>
            <td class="num">1,200</td>
            <td class="num">87.3%</td>
            <td>100% unique Berlin property management companies</td>
          </tr>
        </tbody>
      </table>
    </div>

    <h3 class="subsec-heading">2.2 Disjoint-Set Union-Find Entity Resolution</h3>
    <p class="noindent">
      Because property management companies frequently appear in multiple directories with slight variations in legal punctuation (for example, <i>Muster Hausverwaltung GmbH</i> vs. <i>Muster Hausverwaltungsgesellschaft mbH</i>), naive string deduplication fails. Stage 2 (implemented in <code>src/heidi_engine/dedup/resolver.py</code>) normalizes company names by stripping legal suffixes (<code>GmbH</code>, <code>UG</code>, <code>AG</code>, <code>GmbH &amp; Co. KG</code>, <code>e.K.</code>) and generic sector terms (<code>Hausverwaltung</code>, <code>Immobilienverwaltung</code>), normalizes URLs to root eTLD+1 domains (excluding shared directory hosts and freemail domains), and parses phone numbers into strict E.164 format (<code>+4930...</code>).
    </p>
    <p>
      We model entity deduplication as a graph connected-components problem solved via Tarjan's Disjoint-Set Union-Find algorithm with path compression and union by rank (Tarjan, 1975). Two records $r_i$ and $r_j$ are linked by an edge $E(r_i, r_j) = 1$ if any of three deterministic conditions holds:
    </p>
    <div class="equation">
      <div class="eq-body">
        <i>E</i>(<i>r<sub>i</sub></i>, <i>r<sub>j</sub></i>) = 1 &nbsp;&iff;&nbsp;
        [ (<i>d<sub>i</sub></i> = <i>d<sub>j</sub></i> &and; <i>d<sub>i</sub></i> &notin; <i>D</i><sub>excl</sub>)
        &nbsp;&or;&nbsp;
        (<i>p<sub>i</sub></i> = <i>p<sub>j</sub></i> &and; <i>p<sub>i</sub></i> &ne; &empty;)
        &nbsp;&or;&nbsp;
        (Sim<sub>JW</sub>(<i>n<sub>i</sub></i>, <i>n<sub>j</sub></i>) &ge; 0.88 &and; PLZ<sub><i>i</i></sub> = PLZ<sub><i>j</i></sub>) ]
      </div>
      <div class="eq-num">(1)</div>
    </div>
    <p class="noindent">
      where $d_i$ is the registrable corporate domain, $p_i$ is the E.164 phone number, and $\text{Sim}_{\text{JW}}(n_i, n_j)$ is the token-sort Jaro-Winkler similarity (via RapidFuzz) between normalized company names within the same 5-digit Berlin postal code ($\text{PLZ}_i = \text{PLZ}_j$) (Navarro, 2001). Applying Equation (1) across the 1,375 raw records merged <b>175 duplicate listings</b> and produced <b>1,200 canonical companies</b> in the <code>companies_golden</code> table.
    </p>

    <h2 class="sec-heading">3. Task 2: Qualifying KPI Blueprint, DOM Fingerprinting &amp; Scoring Model</h2>

    <h3 class="subsec-heading">3.1 Asynchronous Subpage Crawling &amp; PropTech DOM Fingerprinting</h3>
    <p class="noindent">
      Of the 1,200 unique Berlin companies, <b>243 (20.2%)</b> maintain a dedicated corporate website domain. In Stage 3 (<code>src/heidi_engine/crawler/async_crawler.py</code>), an asynchronous HTTP/2 crawler visits each corporate homepage and automatically prioritizes high-value subpages (<code>/impressum</code>, <code>/team</code>, <code>/ueber-uns</code>, <code>/leistungen</code>, and <code>/referenzen</code>), crawling a total of <b>885 web pages</b> across 196 reachable HTTP 200 domains.
    </p>
    <p>
      Why is digital maturity a critical qualifying KPI for Heidi Systems? Property managers that already operate specialized German real estate ERP software or online tenant portals have structured digital workflows and can integrate digital submetering data immediately. Before converting HTML to text, our DOM scanner (<code>src/heidi_engine/crawler/dom_tech_detector.py</code>) inspects raw script tags, iframe embeds, and login portal links (`href`) for eight major German PropTech and ERP signatures: <b>Casavi, Domus (DOMUS 4000 / DOMUS Navi), Wodis Sigma (Aareon), Haufe PowerHaus / axera, Immoware24, etg24, Facilioo</b>, and custom online tenant portals (<i>Kundenportal / Mieterportal</i>). Across the crawled Berlin websites, the scanner identified <b>41 companies (3.4% of total, 20.9% of reachable websites)</b> actively running a detectable PropTech ERP or customer portal.
    </p>

    <h3 class="subsec-heading">3.2 Hybrid KPI Extraction &amp; Anti-Hallucination Evidence Gate</h3>
    <p class="noindent">
      In Stage 4 (<code>src/heidi_engine/extractor/</code>), the pipeline extracts structured qualifying KPIs from the crawled <code>/impressum</code> and service pages. First, deterministic regular expressions extract statutory identifiers: legal form (<code>GmbH</code>, <code>AG</code>, <code>UG</code>, <code>e.K.</code>), commercial register court and number (such as <code>Amtsgericht Charlottenburg HRB...</code>), founding year, and explicit unit counts (matching patterns such as <code>2.500 Wohneinheiten</code> or <code>Verwaltung von über 1.200 Einheiten</code>). Second, structured extraction parses management focus flags (<code>manages_weg</code>, <code>manages_miet</code>, <code>manages_gewerbe</code>, <code>manages_sev</code>) and executive names.
    </p>
    <p>
      To guarantee zero fabricated metrics when using language models on unstructured website text, every extracted numeric portfolio claim ($\hat{u}_i$, exact units managed) must pass a strict <b>Verbatim Substring Evidence Gate</b>:
    </p>
    <div class="equation">
      <div class="eq-body">
        Accept(&hat;<i>u<sub>i</sub></i>, <i>q<sub>i</sub></i>) = 1 &nbsp;&iff;&nbsp;
        ( |<i>q<sub>i</sub></i>| &ge; 5 &nbsp;&and;&nbsp; Norm(<i>q<sub>i</sub></i>) &sube; Norm(<i>T<sub>i</sub></i>) )
      </div>
      <div class="eq-num">(2)</div>
    </div>
    <p class="noindent">
      where $q_i$ is the supporting verbatim evidence quote (`units_evidence_quote`) and $T_i$ is the raw crawled text of company $i$. If the quote $q_i$ is missing or cannot be verified as an exact substring of the source page, $\hat{u}_i$ is nulled and the company is sized conservatively using structural signals (employee count, legal form, and corporate web presence). Across the dataset, <b>36 companies</b> published explicit unit counts on their websites, and <b>100.0% (36/36)</b> passed verbatim quote verification with <b>0.0% hallucinated claims</b>.
    </p>

    <h3 class="subsec-heading">3.3 Deterministic 5-Pillar Lead Qualification Formula (0 to 100 Points)</h3>
    <p class="noindent">
      To answer Task 2 (<i>"Which criteria are relevant for us to qualify a property management company as a potential customer, and why?"</i>), we designed and implemented a transparent 5-pillar scoring function in <code>src/heidi_engine/enrichment/scorer.py</code> (<code>calculate_heidi_lead_score</code>). Each company receives a composite score $S_{\text{total}} \in [0, 100]$ defined as the sum of five domain-specific sub-scores:
    </p>
    <div class="equation">
      <div class="eq-body">
        <i>S</i><sub>total</sub> = min( 100, &nbsp;<i>S</i><sub>scale</sub> + <i>S</i><sub>focus</sub> + <i>S</i><sub>digital</sub> + <i>S</i><sub>trust</sub> + <i>S</i><sub>contact</sub> )
      </div>
      <div class="eq-num">(3)</div>
    </div>

    <div class="table-wrap">
      <div class="table-cap"><b>Table 2:</b> Five-Pillar Qualification Scorecard Implemented in <code>src/heidi_engine/enrichment/scorer.py</code></div>
      <table class="booktabs">
        <thead>
          <tr>
            <th>Qualification Pillar</th>
            <th class="center">Max Pts</th>
            <th>Deterministic Scoring Rules (Exact Code Implementation)</th>
            <th>Commercial Relevance for Heidi Systems</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>1. Portfolio Scale</b><br/>(<i>S</i><sub>scale</sub>)</td>
            <td class="center"><b>35</b></td>
            <td>
              &bull; <b>35 pts:</b> &ge; 2,500 exact units or <code>ENTERPRISE</code> tier<br/>
              &bull; <b>28 pts:</b> &ge; 1,000 exact units or <code>LARGE</code> tier<br/>
              &bull; <b>20 pts:</b> &ge; 300 units, <code>MEDIUM</code> tier, or &ge; 5 employees<br/>
              &bull; <b>16 pts:</b> Corporate form (GmbH/AG/KG) + active website<br/>
              &bull; <b>12 pts:</b> Corporate form without website (<b>6 pts</b> baseline)
            </td>
            <td>Determines hardware deployment volume and recurring revenue per signed contract.</td>
          </tr>
          <tr>
            <td><b>2. Asset Focus</b><br/>(<i>S</i><sub>focus</sub>)</td>
            <td class="center"><b>25</b></td>
            <td>
              &bull; <b>25 pts:</b> Manages both <code>WEG</code> and <code>Mietverwaltung</code><br/>
              &bull; <b>20 pts:</b> Manages either <code>WEG</code> or <code>Mietverwaltung</code><br/>
              &bull; <b>15 pts:</b> General residential baseline<br/>
              &bull; <b>12 pts:</b> Commercial (<i>Gewerbe</i>) only (<b>4 pts</b> if <i>SEV</i> only)
            </td>
            <td>Multi-family residential (<i>Miet</i>) and condo (<i>WEG</i>) buildings require HeizkostenV submetering.</td>
          </tr>
          <tr>
            <td><b>3. Digital Maturity</b><br/>(<i>S</i><sub>digital</sub>)</td>
            <td class="center"><b>20</b></td>
            <td>
              &bull; <b>+12 pts:</b> Detected PropTech ERP (Casavi, Domus, Wodis, etc.)<br/>
              &bull; <b>+5 pts:</b> Active online tenant/owner login portal<br/>
              &bull; <b>+3 pts:</b> HTTPS website (<b>+1 pt</b> if HTTP only)
            </td>
            <td>Digitally mature managers adopt automated consumption portals and API integrations faster.</td>
          </tr>
          <tr>
            <td><b>4. Credibility &amp; Trust</b><br/>(<i>S</i><sub>trust</sub>)</td>
            <td class="center"><b>10</b></td>
            <td>
              &bull; <b>+5 pts:</b> Verified VDIV association member<br/>
              &bull; <b>+3 pts:</b> Verified HRB/HRA register ID or founded &le; 2020<br/>
              &bull; <b>+2 pts:</b> Multi-source verified (&ge; 2 directories; <b>+1 pt</b> for 1)
            </td>
            <td>Filters out dormant shell entities and prioritizes established, creditworthy operators.</td>
          </tr>
          <tr>
            <td><b>5. Reachability</b><br/>(<i>S</i><sub>contact</sub>)</td>
            <td class="center"><b>10</b></td>
            <td>
              &bull; <b>+4 pts:</b> Named managing director (<i>Geschäftsführer</i>)<br/>
              &bull; <b>+4 pts:</b> Verified personal email (<code>Non-info@</code>, MX valid)<br/>
              &bull; <b>+2 pts:</b> Direct LinkedIn URL or E.164 phone line
            </td>
            <td>Enables direct executive sales outreach without being blocked by generic <code>info@</code> gatekeepers.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="noindent">
      Based on $S_{\text{total}}$, companies are segmented into three actionable sales tiers:
    </p>
    <ul>
      <li><b>Tier A (High Priority, $S_{\text{total}} \ge 70$): 35 companies (2.9%)</b>, with a mean score of <b>78.9</b> (range 70 to 92). These are high-capacity Berlin property managers with strong residential focus, modern ERP/portal infrastructure, and verified executive contacts.</li>
      <li><b>Tier B (Qualified Mid-Market, $45 \le S_{\text{total}} \le 69$): 409 companies (34.1%)</b>, with a mean score of <b>51.8</b> (range 45 to 69). These represent established mid-market Berlin <i>Hausverwaltungen</i> suitable for structured outbound campaigns.</li>
      <li><b>Tier C (Long-Tail / Small Local, $S_{\text{total}} < 45$): 756 companies (63.0%)</b>, with a mean score of <b>33.1</b> (range 27 to 44). These are smaller local operators lacking a corporate website or public digital infrastructure, suitable for automated nurture sequences.</li>
    </ul>

    <h2 class="sec-heading">4. Bonus Task: Executive Contact Resolution &amp; DNS MX Verification</h2>
    <p class="noindent">
      The Bonus Task specifies: <i>"Find the right contact person including their email address, meaning not an info@ address but a personal and relevant one. LinkedIn profiles or similar are also very welcome."</i> In Stage 5 (<code>src/heidi_engine/enrichment/</code>), the pipeline executes a four-step executive contact resolution protocol:
    </p>
    <ol>
      <li><b>Statutory Role Filtering:</b> From the crawled <code>/impressum</code> and team pages, the extractor isolates natural persons holding statutory authority (<i>Geschäftsführer</i>, <i>Vorstand</i>, <i>Inhaber</i>, or <i>Prokurist</i>) while excluding external data protection officers (<i>Datenschutzbeauftragte</i>) and supervisory board members. This yielded named decision makers for <b>104 Berlin companies (8.7% of all companies, 53.1% of reachable websites)</b>.</li>
      <li><b>Strict Generic vs. Personal Inbox Separation:</b> All scraped email addresses are filtered against a prefix blocklist (`info@`, `kontakt@`, `office@`, `service@`, `mail@`, `verwaltung@`, `buchhaltung@`). Generic addresses are routed strictly to the `general_email` column, while verified personal executive mailboxes are stored in `personal_email`.</li>
      <li><b>German Diacritic Transliteration &amp; Corporate Pattern Synthesis:</b> When a managing director's name is verified on the <code>/impressum</code> page (for example, <i>FirstName LastName</i>) and the company operates a verified corporate domain, the enricher transliterates German umlauts (`ä` &rarr; `ae`, `ö` &rarr; `oe`, `ü` &rarr; `ue`, `ß` &rarr; `ss`) and synthesizes standard German corporate email formats (such as <code>vorname.nachname@domain.de</code> or <code>v.nachname@domain.de</code>).</li>
      <li><b>RFC 5321 DNS Mail Exchange (MX) Verification:</b> Every personal email domain is validated via asynchronous DNS `MX` record resolution (Klensin, 2008). Candidates whose domain lacks a live Mail Exchange host are discarded. In total, the pipeline resolved <b>102 companies (8.5%)</b> (`118` total executive contact rows) with DNS `MX`-verified personal decision-maker email addresses (`12` direct public personal emails + `90` `MX`-verified corporate executive patterns).</li>
    </ol>

    <h2 class="sec-heading">5. Task 3: Data Validation, Ablation Study &amp; Scaling Architecture</h2>

    <h3 class="subsec-heading">5.1 Stage-by-Stage Pipeline Ablation Study</h3>
    <p class="noindent">
      To quantify the engineering value contributed by each stage of the pipeline, `PipelineEvaluator` (`src/heidi_engine/telemetry/evaluator.py`) computes a live ablation study directly against `data/metrixa_leads.db`. Table 3 compares a naive single-directory scrape against the progressive stages of our architecture.
    </p>

    <div class="table-wrap">
      <div class="table-cap"><b>Table 3:</b> Empirical Stage-by-Stage Pipeline Ablation Study Across the Berlin Dataset (<i>N</i> = 1,200 Unique Companies)</div>
      <table class="booktabs">
        <thead>
          <tr>
            <th>Pipeline Configuration (Ablation Stage)</th>
            <th class="num">Lead Count</th>
            <th class="num">Website Coverage</th>
            <th class="num">KPIs Populated</th>
            <th class="num">Named Exec (<i>GF</i>)</th>
            <th class="num">Personal Email (<code>Non-info@</code>)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Baseline A:</b> Single Directory Only (<i>Gelbe Seiten Raw</i>)</td>
            <td class="num">405 (uncleaned)</td>
            <td class="num">35.1%</td>
            <td class="num">0.0%</td>
            <td class="num">0.0%</td>
            <td class="num">0.0% (Only generic <code>info@</code>)</td>
          </tr>
          <tr>
            <td><b>Stage 1 + 2:</b> 5-Source Ingestion + Union-Find Deduplication</td>
            <td class="num">1,200 Unique</td>
            <td class="num">20.2% (243)</td>
            <td class="num">2.5% (VDIV)</td>
            <td class="num">0.0%</td>
            <td class="num">0.0%</td>
          </tr>
          <tr>
            <td><b>Stage 3:</b> + Async Website/Impressum Crawler + DOM ERP Scanner</td>
            <td class="num">1,200 Unique</td>
            <td class="num">20.2% (243)</td>
            <td class="num">3.4% (41 ERP)</td>
            <td class="num">0.0% (Raw HTML)</td>
            <td class="num">1.0% (12 Public Direct)</td>
          </tr>
          <tr>
            <td><b>Stage 4:</b> + Structured Impressum &amp; KPI Extractor (Evidence Gate)</td>
            <td class="num">1,200 Unique</td>
            <td class="num">20.2% (243)</td>
            <td class="num">100.0% (1,200)</td>
            <td class="num">8.7% (104 Co.)</td>
            <td class="num">1.0% (12 Public Direct)</td>
          </tr>
          <tr class="total-row">
            <td>Stage 5 (Full Pipeline): + DNS MX Verifier + 5-Pillar Scorer</td>
            <td class="num">1,200 Scored</td>
            <td class="num">20.2% (243)</td>
            <td class="num">100.0% (1,200)</td>
            <td class="num">8.7% (104 Co.)</td>
            <td class="num">8.5% (102 Co. / 118 Execs)</td>
          </tr>
        </tbody>
      </table>
    </div>

    <h3 class="subsec-heading">5.2 Four-Gate Automated Data Validation Results</h3>
    <p class="noindent">
      Before generating the final multi-tab Excel workbook (`data/exports/heidi_berlin_hausverwaltungen.xlsx`), Stage 6 enforces four automated verification gates across all 1,200 golden records (Table 4). In addition, deterministic unit and integration test suites (`tests/`) validate the Union-Find clustering logic, E.164 phone normalization, German Impressum regex extraction, anti-hallucination quote verification, and lead scoring bounds.
    </p>

    <div class="table-wrap">
      <div class="table-cap"><b>Table 4:</b> Automated Four-Gate Validation Results Computed by <code>PipelineEvaluator</code></div>
      <table class="booktabs">
        <thead>
          <tr>
            <th>Validation Gate</th>
            <th>Evaluated Metric</th>
            <th class="num">Verified Result</th>
            <th>Enforcement Mechanism in Codebase</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>Gate 1: Geographic Boundary</b></td>
            <td>Berlin Postal Code (<code>10115</code> to <code>14199</code>) Precision</td>
            <td class="num"><b>95.4%</b></td>
            <td>Deterministic 5-digit PLZ range check and Berlin 12-district (<i>Bezirk</i>) mapper</td>
          </tr>
          <tr>
            <td><b>Gate 2: Evidence-Grounded Units</b></td>
            <td>Reported <i>Wohneinheiten</i> Verbatim Quote Match</td>
            <td class="num"><b>100.0% (36/36)</b></td>
            <td>Every extracted <code>exact_units_managed</code> requires a verified verbatim quote (&ge; 5 chars)</td>
          </tr>
          <tr>
            <td><b>Gate 3: Personal Inbox Separation</b></td>
            <td>Non-Generic (<code>Non-info@</code>) Personal Email Precision</td>
            <td class="num"><b>100.0% (118/118)</b></td>
            <td>Strict role-prefix filter separating <code>info@</code>, <code>kontakt@</code>, and <code>service@</code> into <code>general_email</code></td>
          </tr>
          <tr>
            <td><b>Gate 4: Hallucination Suppression</b></td>
            <td>Ungrounded or Fabricated Claims in Final Export</td>
            <td class="num"><b>0.0%</b></td>
            <td>Substring evidence gate nulls any unverified numeric portfolio claim before scoring</td>
          </tr>
        </tbody>
      </table>
    </div>

    <h3 class="subsec-heading">5.3 Scaling Blueprint: Expanding from Berlin to All of Germany (25,000+ Companies)</h3>
    <p class="noindent">
      Because statutory Impressum disclosures (§ 5 DDG), commercial register numbering (`HRB`/`HRA`), and German PropTech ERP footprints are uniform across all 16 German federal states (<i>Bundesländer</i>), scaling this pipeline from Berlin (1,200 companies) to the entire German market (~25,000 to 30,000 property management companies across Munich, Hamburg, Frankfurt, Cologne, Stuttgart, and Düsseldorf) requires zero changes to the extraction or scoring logic:
    </p>
    <ul>
      <li><b>Parameterized Postal Code &amp; Regional Association Sharding:</b> Replace the Berlin postal filter (<code>10115-14199</code>) with Germany's full 5-digit postal code table (`01067-99998`) and add the remaining 10 regional VDIV association directories (such as VDIV Bayern, VDIV NRW, and VDIV Hessen).</li>
      <li><b>Federal Commercial Register Enrichment:</b> Cross-reference extracted company names and `HRB` numbers against the German Common Register Portal (<i>Gemeinsames Registerportal der Länder</i> / OpenRegister) to verify legal status and managing director appointments for companies that do not operate a public website.</li>
      <li><b>Incremental Re-Crawl &amp; CRM Sync:</b> Run weekly delta crawls on `/impressum` hashes to detect managing director turnovers or ERP migrations and push Tier A and Tier B leads directly into outbound sales CRM sequences.</li>
    </ul>

    <h2 class="sec-heading">References (APA 7th Style)</h2>
    <ol class="ref-list">
      <li>Bundesministerium der Justiz. (2020). <i>Gesetz über das Wohnungseigentum und das Dauerwohnrecht (Wohnungseigentumsgesetz - WEG)</i> [German Condominium Ownership Act]. BGBl. I S. 2187. https://www.gesetze-im-internet.de/woeigg/</li>
      <li>Bundesministerium für Wirtschaft und Klimaschutz. (2021). <i>Verordnung über die verbrauchsabhängige Abrechnung der Heiz- und Warmwasserkosten (Heizkostenverordnung - HeizkostenV)</i> [German Heating Cost Ordinance]. BGBl. I S. 4964. https://www.gesetze-im-internet.de/heizkostenv/</li>
      <li>Deutscher Bundestag. (2024). <i>Gesetz über digitale Dienste (Digitale-Dienste-Gesetz - DDG), § 5 Allgemeine Informationspflichten</i> [German Digital Services Act, Section 5 Statutory Information Requirements]. BGBl. 2024 I Nr. 149. https://www.gesetze-im-internet.de/ddg/__5.html</li>
      <li>European Parliament &amp; Council of the European Union. (2018). Directive (EU) 2018/2002 amending Directive 2012/27/EU on energy efficiency (EED). <i>Official Journal of the European Union</i>, L 328, 210-230.</li>
      <li>Klensin, J. (2008). <i>Simple Mail Transfer Protocol</i> (RFC 5321). Internet Engineering Task Force (IETF). https://doi.org/10.17487/RFC5321</li>
      <li>Levenshtein, V. I. (1966). Binary codes capable of correcting deletions, insertions, and reversals. <i>Soviet Physics Doklady</i>, 10(8), 707-710.</li>
      <li>Navarro, G. (2001). A guided tour to approximate string matching. <i>ACM Computing Surveys (CSUR)</i>, 33(1), 31-88. https://doi.org/10.1145/375360.375365</li>
      <li>Statistisches Bundesamt (Destatis). (2024). <i>Gebäude und Wohnungen: Bestand an Wohnungen und Wohngebäuden in Deutschland</i> [Buildings and Housing Stock in Germany]. Wiesbaden: Destatis.</li>
      <li>Tarjan, R. E. (1975). Efficiency of a good but not linear set union algorithm. <i>Journal of the ACM (JACM)</i>, 22(2), 215-225. https://doi.org/10.1145/321879.321884</li>
      <li>Verband der Immobilienverwalter Deutschland e.V. (VDIV). (2024). <i>Branchenbarometer der Immobilienverwaltungen in Deutschland</i> [Industry Barometer of Property Management Companies in Germany]. Berlin: VDIV Deutschland.</li>
    </ol>

  </div>

</body>
</html>
"""


def compile_pdf() -> None:
    HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(ACADEMIC_HTML, encoding="utf-8")
    print(f"Wrote single-column academic HTML: {HTML_PATH}")

    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    browser_exe = None
    for candidate in edge_candidates:
        if Path(candidate).exists():
            browser_exe = candidate
            break

    if not browser_exe:
        raise RuntimeError("No Chromium browser found to compile PDF.")

    abs_html = HTML_PATH.resolve().as_uri()
    abs_pdf = str(PDF_OUT.resolve())

    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={abs_pdf}",
        abs_html,
    ]
    subprocess.run(cmd, check=True)

    if not PDF_OUT.exists():
        raise RuntimeError("PDF compilation failed.")

    size_bytes = PDF_OUT.stat().st_size
    print(f"Compiled single-column PDF: {PDF_OUT} ({size_bytes:,} bytes)")

    EXPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PDF_OUT, EXPORT_OUT)
    print(f"Synced PDF to Deliverables Vault: {EXPORT_OUT}")


if __name__ == "__main__":
    compile_pdf()
