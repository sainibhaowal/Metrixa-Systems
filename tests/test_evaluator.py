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
