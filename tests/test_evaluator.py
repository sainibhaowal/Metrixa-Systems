"""Validation reports must not invent accuracy results for empty or unlabeled data."""

from __future__ import annotations

from pathlib import Path

from metrixa_engine.config import settings
from metrixa_engine.db import Database
from metrixa_engine.telemetry.evaluator import PipelineEvaluator


def test_empty_database_reports_accuracy_metrics_as_not_measured(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "empty.db")
    evaluator = PipelineEvaluator(db)

    metrics = evaluator.evaluate_validation_metrics()
    report = evaluator.generate_markdown_report(tmp_path / "coverage.md").read_text(
        encoding="utf-8"
    )

    assert metrics["eligible_leads_with_berlin_plz_pct"] is None
    assert metrics["units_evidence_grounded_pct"] is None
    assert metrics["personal_email_non_generic_rate_pct"] is None
    assert metrics["public_email_source_grounded_pct"] is None
    assert metrics["pattern_email_candidates_total"] == 0
    assert metrics["final_hallucination_rate_pct"] is None
    assert "Not measured" in report
    assert "not a labeled Gold-Set benchmark" in report
    assert "F1:" not in report


def test_default_report_refreshes_artifact_library_alias(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "export_dir", tmp_path)
    monkeypatch.setattr(settings, "database_path", tmp_path / "local.db")
    evaluator = PipelineEvaluator(Database(tmp_path / "local.db"))

    canonical_report = evaluator.generate_markdown_report()
    artifact_report = tmp_path / "metrixa_evaluation_ablation_report.md"

    assert artifact_report.read_text(encoding="utf-8") == canonical_report.read_text(
        encoding="utf-8"
    )


def test_units_evidence_normalizes_whitespace_and_case(tmp_path: Path) -> None:
    db = Database(tmp_path / "grounded.db")
    with db.connect() as conn:
        company_id = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,updated_at) VALUES ('alpha','Alpha GmbH','test','EXTRACTED','now')"
        ).lastrowid
        conn.execute(
            "INSERT INTO kpi_extractions (company_id,exact_units_managed,units_evidence_quote,extracted_at) VALUES (?,3200,'  3,200   Units  ','now')",
            (company_id,),
        )
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,clean_markdown,crawled_at) VALUES (?,'impressum','https://alpha.invalid',200,'Portfolio: 3,200 units managed','now')",
            (company_id,),
        )
    result = PipelineEvaluator(db).evaluate_validation_metrics()
    assert result["units_evidence_grounded_pct"] == 100.0


def test_report_separates_source_listed_emails_from_pattern_candidates(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "email-evidence.db")
    with db.connect() as conn:
        company_id = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,updated_at,website_url) VALUES ('alpha','Alpha GmbH','test','SCORED','now','https://alpha.example')"
        ).lastrowid
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,clean_markdown,crawled_at) VALUES (?, 'impressum','https://alpha.example/impressum',200,'Named contact listed on the site. Contact owner@example.de','now')",
            (company_id,),
        )
        conn.execute(
            "INSERT INTO decision_makers (company_id,full_name,personal_email,email_status,evidence_quote) VALUES (?, 'Owner Example','owner@example.de','PUBLIC_LISTED','Named contact listed on the site.')",
            (company_id,),
        )
        conn.execute(
            "INSERT INTO decision_makers (company_id,full_name,personal_email,email_status) VALUES (?, 'Owner Example','owner.pattern@example.de','PATTERN_CANDIDATE_MX')",
            (company_id,),
        )

    metrics = PipelineEvaluator(db).evaluate_validation_metrics()
    assert metrics["public_listed_emails_total"] == 1
    assert metrics["public_emails_grounded"] == 1
    assert metrics["public_email_source_grounded_pct"] == 100.0
    assert metrics["pattern_email_candidates_total"] == 1
    assert metrics["contact_quotes_total"] == 1
    assert metrics["contact_quotes_grounded"] == 1
    assert metrics["contact_quote_source_grounded_pct"] == 100.0
    report = (
        PipelineEvaluator(db)
        .generate_markdown_report(tmp_path / "email-evidence.md")
        .read_text(encoding="utf-8")
    )
    assert "| Eligible canonical companies with a website | 1 / 1 (100.0%) |" in report


def test_merge_count_uses_lineage_and_excludes_disqualified_crawl_rows(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "lineage-report.db")
    with db.connect() as conn:
        active_id = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,updated_at) VALUES ('alpha','Alpha GmbH','test','SCORED','now')"
        ).lastrowid
        disqualified_id = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,pipeline_stage,disqualification_reason,updated_at) VALUES ('old','Old GmbH','test','DISQUALIFIED','stale','now')"
        ).lastrowid
        raw_ids = []
        for index in range(4):
            raw_ids.append(
                conn.execute(
                    "INSERT INTO raw_listings (source_name,raw_company_name,scraped_at) VALUES ('test',?, 'now')",
                    (f"Listing {index}",),
                ).lastrowid
            )
        for raw_id in raw_ids[:3]:
            conn.execute(
                "INSERT INTO company_sources_map (company_id,raw_listing_id) VALUES (?,?)",
                (active_id, raw_id),
            )
        conn.execute(
            "INSERT INTO company_sources_map (company_id,raw_listing_id) VALUES (?,?)",
            (disqualified_id, raw_ids[3]),
        )
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,crawled_at) VALUES (?, 'home','https://old.example',200,'now')",
            (disqualified_id,),
        )
        conn.execute(
            "INSERT INTO decision_makers (company_id,full_name,personal_email,email_status) VALUES (?, 'Owner Example','owner@example.de','PUBLIC_LISTED')",
            (active_id,),
        )

    metrics = PipelineEvaluator(db).compute_live_ablation_metrics()
    assert metrics["duplicates_removed"] == 2
    assert metrics["mapped_raw_count"] == 4
    assert metrics["unmapped_raw_count"] == 0
    assert metrics["crawled_companies"] == 0
    assert metrics["public_direct_emails_cnt"] == 1


def test_report_handles_malformed_pipeline_event_json(tmp_path: Path) -> None:
    db = Database(tmp_path / "malformed-run-log.db")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO pipeline_runs (run_id,run_number,trigger_type,status,started_at,finished_at,summary_metrics_json) VALUES ('run-1',1,'MANUAL_FULL','COMPLETED','now','later','{')"
        )
        conn.execute(
            "INSERT INTO pipeline_run_events (run_id,seq,timestamp,stage,step_name,event_type,level,message,payload_json) VALUES ('run-1',1,'now','INGEST','bad-source','SCRAPER_EXEC','WARN','bad stored payload','{')"
        )

    report_path = PipelineEvaluator(db).generate_markdown_report(
        tmp_path / "malformed-log-report.md"
    )
    report = report_path.read_text(encoding="utf-8")

    assert "Run #1 (`run-1`)" in report
    assert "Source: 0" in report
    assert "The latest run has no recorded warnings." in report


def test_report_does_not_claim_running_run_has_finished(tmp_path: Path) -> None:
    db = Database(tmp_path / "running.db")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO pipeline_runs (run_id,run_number,trigger_type,status,started_at) VALUES ('run-1',1,'MANUAL_FULL','RUNNING','now')"
        )
    report = (
        PipelineEvaluator(db)
        .generate_markdown_report(tmp_path / "running.md")
        .read_text(encoding="utf-8")
    )
    assert "is `RUNNING`" in report
    assert "warnings may be incomplete" in report
    assert "finished `RUNNING`" not in report
