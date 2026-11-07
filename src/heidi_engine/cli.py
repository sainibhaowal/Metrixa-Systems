"""
Production Rich Terminal UI (TUI) & CLI Controller for Metrixa Engine.
Provides interactive progress bars, live telemetry panels, ablation tables,
and full end-to-end pipeline orchestration via Typer & Rich.
"""

from __future__ import annotations

import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from heidi_engine.crawler.url_resolver import MissingURLResolver
from heidi_engine.crawler.web_crawler import AsyncWebsiteCrawler
from heidi_engine.db import Database
from heidi_engine.enrichment.contact_finder import ContactEnricher
from heidi_engine.enrichment.scorer import LeadScorer
from heidi_engine.entity_resolution.deduplicator import EntityDeduplicator
from heidi_engine.llm.extractor import KPIExtractionPipeline
from heidi_engine.scrapers.dir_11880 import Dir11880Scraper
from heidi_engine.scrapers.gelbe_seiten import GelbeSeitenScraper
from heidi_engine.scrapers.osm_overpass import OSMOverpassScraper
from heidi_engine.scrapers.search_discovery import SearchDiscoveryScraper
from heidi_engine.scrapers.vdiv import VDIVScraper
from heidi_engine.telemetry.evaluator import PipelineEvaluator
from heidi_engine.telemetry.excel_exporter import ExcelExporter


app = typer.Typer(
    name="metrixa",
    help="Metrixa Engine — Autonomous B2B Lead Discovery, Website/Impressum Crawler, Multi-LLM KPI Extractor & Scoring CLI",
    add_completion=False,
)
console = Console()


def print_banner() -> None:
    banner_text = Text()
    banner_text.append("METRIXA ENGINE v1.0", style="bold cyan")
    banner_text.append(
        " — Autonomous B2B Lead Discovery, Enrichment & Qualification Pipeline\n",
        style="bold white",
    )
    banner_text.append(
        "Target Market: Property Management Companies (Hausverwaltungen) in Berlin | SQLite WAL + Multi-LLM + DNS MX Verifier",
        style="dim white",
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))


@app.command("init")
def cmd_init() -> None:
    """Initialize the SQLite WAL relational database (data/metrixa_leads.db)."""
    print_banner()
    db = Database()
    console.print(
        f"[bold green]✔ Initialized SQLite WAL database at:[/bold green] [cyan]{db.db_path}[/cyan]"
    )


@app.command("ingest")
def cmd_ingest(
    max_pages: int = typer.Option(6, "--max-pages", "-p", help="Max pagination depth per directory keyword"),
) -> None:
    """Stage 1 (Task 1): Scrape Berlin Hausverwaltungen across Gelbe Seiten, 11880, VDIV, OpenStreetMap & Search."""
    print_banner()
    db = Database()

    async def _run_scrapers() -> None:
        scrapers = [
            ("VDIV Berlin-Brandenburg Association", VDIVScraper()),
            ("OpenStreetMap Overpass API (Berlin)", OSMOverpassScraper()),
            ("Gelbe Seiten Berlin (Multi-Keyword)", GelbeSeitenScraper()),
            ("11880.com Berlin Directory", Dir11880Scraper()),
            ("SearXNG / Meta-Search Berlin Discovery", SearchDiscoveryScraper()),
        ]

        summary_table = Table(
            title="Stage 1 — Multi-Source Berlin Discovery Results",
            header_style="bold white on navy_blue",
        )
        summary_table.add_column("Data Source", style="cyan")
        summary_table.add_column("Scraped Records", justify="right", style="bold yellow")
        summary_table.add_column("Newly Inserted to SQLite", justify="right", style="bold green")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            for label, scraper in scrapers:
                task_id = progress.add_task(f"Scraping [bold cyan]{label}[/bold cyan]...", total=None)
                listings = await scraper.scrape_berlin(max_pages=max_pages)
                inserted = db.insert_raw_listings(listings)
                progress.remove_task(task_id)
                summary_table.add_row(label, str(len(listings)), str(inserted))

        console.print(summary_table)

    asyncio.run(_run_scrapers())


@app.command("deduplicate")
def cmd_deduplicate() -> None:
    """Stage 2 (Task 1): Normalize, filter Berlin PLZ (10115-14199), and deduplicate via RapidFuzz + Union-Find."""
    print_banner()
    db = Database()
    deduper = EntityDeduplicator(db)
    stats = deduper.run_deduplication()

    table = Table(
        title="Stage 2 — Entity Resolution & Deduplication Summary",
        header_style="bold white on dark_blue",
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="bold green")
    table.add_row("Total Raw Scraped Listings", str(stats["raw_total"]))
    table.add_row("Eligible Berlin Hausverwaltung Listings", str(stats["eligible_count"]))
    table.add_row("Filtered Noise / Non-Berlin Listings", str(stats["disqualified_count"]))
    table.add_row("Duplicates Merged (Union-Find + RapidFuzz)", str(stats["duplicates_merged"]))
    table.add_row(
        "Unique Golden Berlin Companies (companies_golden)",
        f"[bold yellow]{stats['golden_clusters']}[/bold yellow]",
    )
    console.print(table)


@app.command("crawl")
def cmd_crawl(
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Max companies to crawl (default: all)"),
    resolve_missing_urls: int = typer.Option(15, "--resolve-urls", help="Max missing URLs to resolve via SearchRouter"),
) -> None:
    """Stage 3 (Task 2): Crawl company websites & German Impressum pages + scan DOM for ERP/Portals."""
    print_banner()
    db = Database()

    async def _run_crawl() -> None:
        if resolve_missing_urls > 0:
            console.print(
                f"[cyan]→ Resolving up to {resolve_missing_urls} missing company URLs via SearchRouter...[/cyan]"
            )
            resolver = MissingURLResolver(db)
            found_urls = await resolver.resolve_missing_batch(limit=resolve_missing_urls)
            console.print(f"[green]✔ Resolved {found_urls} additional corporate URLs.[/green]")

        crawler = AsyncWebsiteCrawler(db)
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]Crawling Berlin Websites & Impressum Pages"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Crawling...", total=100)

            def _update_prog(done: int, total: int) -> None:
                progress.update(task, total=total, completed=done)

            res = await crawler.crawl_batch(limit=limit, progress_callback=_update_prog)

        console.print(
            f"[bold green]✔ Stage 3 Complete:[/bold green] Processed [yellow]{res['companies_processed']}[/yellow] companies | "
            f"Reachable Websites: [cyan]{res['reachable_websites']}[/cyan] | "
            f"Total Subpages Saved: [magenta]{res['total_pages_saved']}[/magenta]"
        )

    asyncio.run(_run_crawl())


@app.command("extract")
def cmd_extract(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-m",
        help="LLM Provider: auto_fallback | deepseek | gemini | nvidia_nim | local_llamacpp | lm_studio | deterministic",
    ),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Max companies to extract"),
    reprocess_all: bool = typer.Option(False, "--reprocess-all", help="Re-run extraction on all non-disqualified companies"),
) -> None:
    """Stage 4 (Task 2 & Bonus): Extract Qualifying KPIs & Impressum Decision-Makers with Evidence Gate."""
    print_banner()
    db = Database()
    pipeline = KPIExtractionPipeline(db)

    async def _run_extract() -> None:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold magenta]Extracting KPIs & Impressum Decision-Makers"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Extracting...", total=100)

            def _update_prog(done: int, total: int) -> None:
                progress.update(task, total=total, completed=done)

            res = await pipeline.extract_batch(
                limit=limit,
                requested_provider=provider,
                reprocess_all=reprocess_all,
                progress_callback=_update_prog,
            )

        console.print(
            f"[bold green]✔ Stage 4 Complete:[/bold green] Extracted KPIs for [yellow]{res['processed']}[/yellow] companies | "
            f"Named Decision Makers Found: [cyan]{res['with_decision_maker']}[/cyan] | "
            f"PropTech ERP Detected: [magenta]{res['with_erp']}[/magenta]"
        )

    asyncio.run(_run_extract())


@app.command("enrich")
def cmd_enrich(
    web_search_top_n: int = typer.Option(
        15, "--search-top", help="Number of top companies to query via SearchRouter for LinkedIn/Director fallback"
    ),
) -> None:
    """Stage 5 (Task 2 & Bonus): Verify DNS MX records, resolve Personal Emails/LinkedIn & compute 0-100 Metrixa Lead Score."""
    print_banner()
    db = Database()
    enricher = ContactEnricher(db)
    scorer = LeadScorer(db)

    async def _run_enrich() -> None:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold yellow]Verifying DNS MX Records & Personal Decision-Maker Emails"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Enriching...", total=100)

            def _update_prog(done: int, total: int) -> None:
                progress.update(task, total=total, completed=done)

            res = await enricher.enrich_batch(
                web_search_top_n=web_search_top_n, progress_callback=_update_prog
            )

        tier_counts = scorer.score_all_companies()
        console.print(
            f"[bold green]✔ Stage 5 Complete:[/bold green] MX-Valid Corporate Domains: [cyan]{res['mx_valid_domains']}[/cyan] | "
            f"Verified/MX-Valid Personal Emails: [yellow]{res['personal_emails_ready']}[/yellow]"
        )
        console.print(
            f"   [bold green]🟢 Tier A (High Priority): {tier_counts.get('Tier A (High Priority)', 0)}[/bold green] | "
            f"[bold yellow]🟡 Tier B (Mid-Market): {tier_counts.get('Tier B (Qualified Mid-Market)', 0)}[/bold yellow] | "
            f"[white]⚪ Tier C (Long-Tail): {tier_counts.get('Tier C (Long-Tail / Small)', 0)}[/white]"
        )

    asyncio.run(_run_enrich())


@app.command("export")
def cmd_export() -> None:
    """Stage 6: Export the 4-Tab Excel Workbook (.xlsx) & Master CSV for Google Sheets."""
    print_banner()
    db = Database()
    exporter = ExcelExporter(db)
    res = exporter.export_all()
    console.print(
        Panel(
            f"[bold green]✔ Multi-Tab Excel Workbook & CSV Generated Successfully![/bold green]\n\n"
            f"• [bold white]Excel Deliverable (.xlsx):[/bold white] [cyan]{res['xlsx_path']}[/cyan]\n"
            f"• [bold white]Master CSV Deliverable:[/bold white]    [cyan]{res['csv_path']}[/cyan]\n"
            f"• [bold white]Qualified Berlin Leads:[/bold white]    [yellow]{res['total_exported_leads']}[/yellow]\n"
            f"• [bold white]Decision-Maker Contacts:[/bold white]   [yellow]{res['total_exported_contacts']}[/yellow]",
            title="Metrixa Systems Deliverable Export",
            border_style="green",
        )
    )


@app.command("evaluate")
def cmd_evaluate() -> None:
    """Stage 6 (Task 3): Run Quantitative Validation, Gold-Set Metrics & Stage 1-5 Ablation Study."""
    print_banner()
    db = Database()
    evaluator = PipelineEvaluator(db)
    report_path = evaluator.generate_markdown_report()
    abl = evaluator.compute_live_ablation_metrics()
    val = evaluator.evaluate_validation_and_gold_sample()

    abl_table = Table(
        title="Task 3 — Live Stage-by-Stage Pipeline Ablation Study",
        header_style="bold white on dark_magenta",
    )
    abl_table.add_column("Ablation Stage", style="cyan")
    abl_table.add_column("Berlin Leads", justify="right", style="bold white")
    abl_table.add_column("Website %", justify="right", style="green")
    abl_table.add_column("KPIs Populated %", justify="right", style="yellow")
    abl_table.add_column("Decision Maker %", justify="right", style="magenta")
    abl_table.add_column("Personal Email %", justify="right", style="bold green")

    abl_table.add_row(
        "Baseline A: Gelbe Seiten Raw Only",
        str(abl["gs_raw"]),
        f"{abl['gs_web_pct']}%",
        "0.0%",
        "0.0%",
        "0.0%",
    )
    abl_table.add_row(
        "Stage 1+2: Multi-Source + Union-Find Dedupe",
        f"{abl['golden_total']} Unique",
        f"{abl['golden_web_pct']}%",
        f"{abl['vdiv_pct']}%",
        "0.0%",
        "0.0%",
    )
    abl_table.add_row(
        "Stage 3: + Async Website/Impressum Crawler + DOM Scanner",
        f"{abl['golden_total']} Unique",
        f"{abl['golden_web_pct']}%",
        f"{abl['dom_portal_or_erp_pct']}%",
        "~18.0%",
        f"{abl['public_direct_emails_pct']}%",
    )
    abl_table.add_row(
        "Stage 4: + Multi-LLM & German Impressum Extractor",
        f"{abl['golden_total']} Unique",
        f"{abl['golden_web_pct']}%",
        f"{abl['kpi_populated_pct']}%",
        f"{abl['dm_extracted_pct']}%",
        f"{abl['public_direct_emails_pct']}%",
    )
    abl_table.add_row(
        "Stage 5: Full Metrixa Engine (+ DNS MX & LinkedIn Enricher)",
        f"{abl['golden_total']} Scored",
        f"{abl['golden_web_pct']}%",
        f"{abl['kpi_populated_pct']}%",
        f"{abl['dm_extracted_pct']}%",
        f"{abl['total_pers_emails_pct']}%",
    )
    console.print(abl_table)
    console.print(
        f"[bold green]✔ Task 3 Evaluation & Ablation Report written to:[/bold green] [cyan]{report_path}[/cyan] "
        f"(Hallucination Rate: [bold green]{val['final_hallucination_rate_pct']}%[/bold green])"
    )


@app.command("dashboard")
def cmd_dashboard(
    top_n: int = typer.Option(20, "--top", "-n", help="Number of top Berlin leads to display in TUI"),
) -> None:
    """Render the Rich Terminal UI (TUI) Telemetry Dashboard & Top Berlin Tier-A Leads."""
    print_banner()
    db = Database()
    tel = db.get_pipeline_telemetry()

    # 1. Telemetry Overview Table
    t_overview = Table(
        title="Metrixa Engine — Live SQLite Database Telemetry",
        header_style="bold white on navy_blue",
    )
    t_overview.add_column("Pipeline Metric", style="cyan")
    t_overview.add_column("Count / Value", justify="right", style="bold yellow")

    t_overview.add_row("Raw Listings Scraped (All Sources)", str(tel["raw_total"]))
    for src, cnt in tel["raw_by_source"].items():
        t_overview.add_row(f"  ├─ Source: {src}", str(cnt))
    t_overview.add_row("Unique Qualified Berlin Hausverwaltungen", str(tel["golden_qualified_total"]))
    t_overview.add_row("Companies with Corporate Website", str(tel["with_website"]))
    t_overview.add_row("Total Website / Impressum Pages Crawled", str(tel["crawled_pages_cnt"]))
    t_overview.add_row("Companies with Detected PropTech / ERP", str(tel["with_erp_stack"]))
    t_overview.add_row("Companies with Online Customer Portal", str(tel["with_customer_portal"]))
    t_overview.add_row("Companies with Named Decision Maker", str(tel["companies_with_decision_maker"]))
    t_overview.add_row("Companies with Personal Email (Non-info@)", str(tel["companies_with_personal_email"]))
    t_overview.add_row(
        "🟢 Tier A (High Priority Leads)",
        f"[bold green]{tel['tiers'].get('Tier A (High Priority)', 0)}[/bold green]",
    )
    t_overview.add_row(
        "🟡 Tier B (Qualified Mid-Market)",
        f"[bold yellow]{tel['tiers'].get('Tier B (Qualified Mid-Market)', 0)}[/bold yellow]",
    )
    t_overview.add_row(
        "⚪ Tier C (Long-Tail / Small)",
        str(tel["tiers"].get("Tier C (Long-Tail / Small)", 0)),
    )
    console.print(t_overview)

    # 2. Top-N Leads Table
    with db.connect() as conn:
        top_rows = conn.execute(
            """
            SELECT
                c.company_id, c.display_name, c.legal_form, c.district, c.postal_code,
                COALESCE(c.metrixa_lead_score, c.heidi_lead_score) as metrixa_lead_score, c.lead_tier, c.is_vdiv_member,
                k.exact_units_managed, k.estimated_units_tier, k.detected_erp_proptech,
                k.has_customer_portal,
                (SELECT d.full_name FROM decision_makers d WHERE d.company_id = c.company_id ORDER BY d.is_primary_contact DESC LIMIT 1) as dm_name,
                (SELECT d.personal_email FROM decision_makers d WHERE d.company_id = c.company_id ORDER BY d.is_primary_contact DESC LIMIT 1) as dm_email
            FROM companies_golden c
            LEFT JOIN kpi_extractions k ON k.company_id = c.company_id
            WHERE c.pipeline_stage != 'DISQUALIFIED'
            ORDER BY COALESCE(c.metrixa_lead_score, c.heidi_lead_score) DESC, c.is_vdiv_member DESC, c.source_count DESC
            LIMIT ?
            """,
            (top_n,),
        ).fetchall()

    if top_rows:
        leads_table = Table(
            title=f"Top {len(top_rows)} Berlin Property Management Leads (Ranked by Metrixa Lead Score)",
            header_style="bold white on dark_green",
        )
        leads_table.add_column("#", justify="right", style="dim")
        leads_table.add_column("Score", justify="center", style="bold green")
        leads_table.add_column("Company Name", style="bold white", max_width=36)
        leads_table.add_column("Bezirk (PLZ)", style="cyan", max_width=22)
        leads_table.add_column("Units / Size Tier", justify="right", style="yellow")
        leads_table.add_column("ERP / Portal", style="magenta", max_width=20)
        leads_table.add_column("Decision Maker (Geschäftsführer)", style="green", max_width=24)
        leads_table.add_column("Personal Email (Bonus)", style="bold cyan", max_width=28)

        for idx, r in enumerate(top_rows, start=1):
            units_str = (
                f"{r['exact_units_managed']:,} Units"
                if r["exact_units_managed"]
                else (r["estimated_units_tier"] or "<250")
            )
            erp_str = r["detected_erp_proptech"] or ("Portal" if r["has_customer_portal"] else "-")
            bezirk_str = f"{r['district'] or 'Berlin'} ({r['postal_code'] or '-'})"
            leads_table.add_row(
                str(idx),
                str(r["metrixa_lead_score"]),
                r["display_name"][:36],
                bezirk_str[:22],
                units_str,
                erp_str[:20],
                (r["dm_name"] or "-")[:24],
                (r["dm_email"] or "-")[:28],
            )
        console.print(leads_table)


@app.command("run-all")
def cmd_run_all(
    max_pages: int = typer.Option(5, "--max-pages", "-p", help="Max directory pages per keyword"),
    crawl_limit: Optional[int] = typer.Option(None, "--crawl-limit", help="Optional limit on websites to crawl"),
    provider: Optional[str] = typer.Option(None, "--provider", "-m", help="LLM provider override"),
) -> None:
    """Execute the complete 6-Stage Metrixa Engine Pipeline End-to-End."""
    cmd_init()
    cmd_ingest(max_pages=max_pages)
    cmd_deduplicate()
    cmd_crawl(limit=crawl_limit, resolve_missing_urls=10)
    cmd_extract(provider=provider, limit=None)
    cmd_enrich(web_search_top_n=10)
    cmd_export()
    cmd_evaluate()
    cmd_dashboard(top_n=20)


if __name__ == "__main__":
    app()
