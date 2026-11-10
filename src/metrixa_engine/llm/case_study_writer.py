"""Source-backed case-study narrative generation from retrieved Stage 3 records."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx

from metrixa_engine.config import settings
from metrixa_engine.db import Database
from metrixa_engine.llm.router import llm_router
from metrixa_engine.telemetry.evaluator import PipelineEvaluator


class CaseStudyWriterError(RuntimeError):
    """Base error for generation or evidence validation failures."""


class CaseStudyProviderUnavailable(CaseStudyWriterError):
    """Raised when no configured LLM provider can be resolved."""


class CaseStudyEvidenceUnavailable(CaseStudyWriterError):
    """Raised when there are no current Stage 3 source records to retrieve."""


class CaseStudyNarrativeRejected(CaseStudyWriterError):
    """Raised when generated prose violates citation or numeric-output rules."""


class CaseStudyWriter:
    """Generate a narrative while keeping all measured facts database-derived."""

    output_name = "metrixa_current_case_study.md"

    def __init__(self, db: Database) -> None:
        self.db = db

    def _build_evidence_packet(self) -> Dict[str, Any]:
        telemetry = self.db.get_pipeline_telemetry()
        evaluator = PipelineEvaluator(self.db)
        coverage = evaluator.compute_live_ablation_metrics()
        validation = evaluator.evaluate_validation_metrics()

        with self.db.connect() as conn:
            run = conn.execute(
                """
                SELECT run_id, run_number, status, started_at, finished_at,
                       summary_metrics_json
                FROM pipeline_runs ORDER BY run_number DESC LIMIT 1
                """
            ).fetchone()
            source_rows = conn.execute(
                """
                SELECT p.url, p.page_type, p.detected_erp_csv,
                       p.detected_metering_csv, p.has_portal_link, p.crawled_at,
                       c.website_url
                FROM crawled_pages p
                JOIN companies_golden c ON c.company_id = p.company_id
                WHERE c.pipeline_stage != 'DISQUALIFIED'
                  AND c.is_vdiv_member = 1
                  AND p.http_status = 200
                  AND lower(p.page_type) IN ('portal', 'leistungen')
                  AND (
                    COALESCE(p.detected_erp_csv, '') != ''
                    OR COALESCE(p.detected_metering_csv, '') != ''
                  )
                ORDER BY p.crawled_at DESC, p.page_id DESC
                LIMIT 80
                """
            ).fetchall()

        retrieved = []
        seen_hosts = set()
        for row in source_rows:
            parts = urlsplit(row["url"] or "")
            host = (parts.hostname or "").lower()
            company_host = (urlsplit(row["website_url"] or "").hostname or "").lower()
            if host.startswith("www."):
                host = host[4:]
            if company_host.startswith("www."):
                company_host = company_host[4:]
            if (
                not host
                or not company_host
                or host != company_host
                or host in seen_hosts
            ):
                continue
            signals = []
            if row["has_portal_link"]:
                signals.append("customer portal link detected")
            erp = row["detected_erp_csv"] or ""
            if erp:
                signals.append(f"ERP signature detected: {erp}")
            metering = row["detected_metering_csv"] or ""
            if metering:
                signals.append(f"metering technology signal detected: {metering}")
            seen_hosts.add(host)
            source_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            retrieved.append(
                {
                    "id": f"S{len(retrieved) + 1}",
                    "url": source_url,
                    "host": host,
                    "page_type": row["page_type"],
                    "crawled_at": row["crawled_at"],
                    "signals": signals,
                }
            )
            if len(retrieved) >= 6:
                break

        if not retrieved:
            raise CaseStudyEvidenceUnavailable(
                "No successful Stage 3 pages with portal, ERP, or metering signals are available."
            )

        latest_run = dict(run) if run else None
        run_summary = {}
        if latest_run:
            try:
                run_summary = json.loads(latest_run["summary_metrics_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                run_summary = {}

        return {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "raw_listings": telemetry["raw_total"],
            "active_companies": telemetry["golden_qualified_total"],
            "disqualified_companies": telemetry["disqualified_total"],
            "tiers": telemetry["tiers"],
            "companies_with_website": telemetry["with_website"],
            "stored_crawl_pages": telemetry["crawled_pages_cnt"],
            "companies_with_kpi": coverage["kpi_populated_cnt"],
            "companies_with_decision_maker": telemetry["companies_with_decision_maker"],
            "companies_with_customer_portal": telemetry["with_customer_portal"],
            "companies_with_erp": telemetry["with_erp_stack"],
            "public_email_companies": telemetry["companies_with_public_personal_email"],
            "pattern_email_companies": telemetry[
                "companies_with_pattern_email_candidate"
            ],
            "managed_unit_claims": validation["explicit_units_extracted"],
            "managed_unit_quotes_grounded": validation["units_evidence_grounded"],
            "latest_run": latest_run,
            "latest_run_summary": run_summary,
            "mapped_raw_listings": coverage["mapped_raw_count"],
            "duplicate_listings_merged": coverage["duplicates_removed"],
            "unmapped_raw_listings": coverage["unmapped_raw_count"],
            "retrieved_sources": retrieved,
        }

    @staticmethod
    def _validate_narrative(
        narrative: str,
        source_ids: set[str],
        allowed_numeric_labels: Optional[set[str]] = None,
    ) -> None:
        text = (narrative or "").strip()
        if not text:
            raise CaseStudyNarrativeRejected("The model returned an empty narrative.")
        citation_groups = re.findall(
            r"\[(S\d+(?:\s*,\s*S\d+)*)\]", text, flags=re.IGNORECASE
        )
        citations = {
            tag.upper()
            for group in citation_groups
            for tag in re.findall(r"S\d+", group, flags=re.IGNORECASE)
        }
        if not citations or not citations.issubset(source_ids):
            raise CaseStudyNarrativeRejected(
                "The narrative must cite at least one retrieved source and may not cite unknown sources."
            )
        unsupported_inference_patterns = (
            r"\binfrastructure\b",
            r"\bcompatib(?:ility|le)\b",
            r"\bintegration (?:point|points|mechanism|mechanisms|notes?)\b",
            r"\bdata[- ]exchange\b",
            r"\bperformance\b",
            r"\b(?:company|lead|sales) fit\b",
        )
        if any(
            re.search(pattern, text, flags=re.IGNORECASE)
            for pattern in unsupported_inference_patterns
        ):
            raise CaseStudyNarrativeRejected(
                "The narrative inferred infrastructure, deployment, compatibility, or fit beyond the page signals."
            )
        without_citations = re.sub(
            r"\[S\d+(?:\s*,\s*S\d+)*\]", "", text, flags=re.IGNORECASE
        )
        for label in sorted(allowed_numeric_labels or (), key=len, reverse=True):
            if label.strip():
                without_citations = re.sub(
                    re.escape(label.strip()), "", without_citations, flags=re.IGNORECASE
                )
        numeric_tokens = sorted(set(re.findall(r"\d+", without_citations)))
        if numeric_tokens:
            raise CaseStudyNarrativeRejected(
                "The narrative included numeric tokens "
                f"({', '.join(numeric_tokens)}); the application supplies measured numbers separately."
            )

    @staticmethod
    def _build_document(
        packet: Dict[str, Any], narrative: str, provider: str, model: str
    ) -> str:
        run = packet["latest_run"] or {}
        warnings = packet["latest_run_summary"].get("warnings") or []
        tier_a = packet["tiers"].get("Tier A (High Priority)", 0)
        tier_b = packet["tiers"].get("Tier B (Qualified Mid-Market)", 0)
        tier_c = packet["tiers"].get("Tier C (Long-Tail / Small)", 0)
        lines = [
            "# Metrixa Engine: Current Local Pilot Case Study",
            "",
            f"**Snapshot:** {packet['generated_at']}  ",
            f"**Latest run:** {run.get('run_id', 'No recorded run')} ({run.get('status', 'not available')})  ",
            f"**Narrative model:** {provider} / {model}",
            "",
            "> LLM-assisted narrative based on retrieved Stage 3 website signals. All numbers below are calculated from the local SQLite database. Quote presence and source signals do not establish overall accuracy.",
            "",
            "## Case-study narrative",
            "",
            narrative.strip(),
            "",
            "## Measured local snapshot",
            "",
            "| Measure | Current value |",
            "| --- | ---: |",
            f"| Raw source listings | {packet['raw_listings']:,} |",
            f"| Active canonical companies | {packet['active_companies']:,} |",
            f"| Quarantined/disqualified canonical rows | {packet['disqualified_companies']:,} |",
            f"| Duplicate raw listings merged by source lineage | {packet['duplicate_listings_merged']:,} |",
            f"| Raw rows without a canonical mapping | {packet['unmapped_raw_listings']:,} |",
            f"| Tier A / Tier B / Tier C | {tier_a:,} / {tier_b:,} / {tier_c:,} |",
            f"| Companies with a website | {packet['companies_with_website']:,} |",
            f"| Stored crawl page records | {packet['stored_crawl_pages']:,} |",
            f"| Companies with a KPI record | {packet['companies_with_kpi']:,} |",
            f"| Companies with a named decision maker | {packet['companies_with_decision_maker']:,} |",
            f"| Customer portal / ERP signals | {packet['companies_with_customer_portal']:,} / {packet['companies_with_erp']:,} |",
            f"| Source-listed personal email companies | {packet['public_email_companies']:,} |",
            f"| Inferred pattern-candidate companies | {packet['pattern_email_companies']:,} |",
            f"| Managed-unit claims with quote / quote present in stored successful pages | {packet['managed_unit_claims']:,} / {packet['managed_unit_quotes_grounded']:,} |",
            "",
            "## Retrieved Stage 3 evidence",
            "",
        ]
        for source in packet["retrieved_sources"]:
            signals = "; ".join(source["signals"])
            lines.append(
                f"- [{source['id']}]({source['url']}) ({source['page_type']}, crawled {str(source['crawled_at'])[:10]}): {signals}."
            )
        lines.extend(
            [
                "",
                "## Limitations",
                "",
                "The latest run may have warnings recorded in the pipeline history. A source result of zero means no records were returned in that run; it does not invalidate rows retained from earlier runs. Website availability is partial. Publicly listed email addresses are not mailbox-verified, inferred email patterns are not source-listed contacts, and MX checks are domain-level signals. The system has no independently labeled accuracy, precision, recall, F1, or conversion benchmark.",
                "",
                f"Latest run warnings: {('; '.join(warnings)) if warnings else 'none recorded'}.",
                "",
                "The narrative is a writing aid, not a factual verification layer. Review it and the cited source pages before external submission.",
                "",
            ]
        )
        return "\n".join(lines)

    def _record_audit(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        blocked: bool,
        notes: str,
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO llm_audit_logs (
                    company_id, stage, provider, model_name, prompt_tokens,
                    completion_tokens, latency_ms, schema_valid,
                    hallucination_blocked, notes, created_at
                ) VALUES (NULL, 'CASE_STUDY_WRITER', ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    provider,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    latency_ms,
                    int(blocked),
                    notes,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    async def generate(
        self, requested_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve current Stage 3 signals, generate a constrained narrative, and save Markdown."""
        provider_cfg = await llm_router.resolve_active_provider(requested_provider)
        if not provider_cfg:
            raise CaseStudyProviderUnavailable(
                "No configured LLM provider is reachable for case-study writing."
            )

        packet = self._build_evidence_packet()
        source_ids = {source["id"] for source in packet["retrieved_sources"]}
        system_prompt = (
            "Write one short professional case-study paragraph in exactly two sentences. "
            "Sentence one must summarize only the concrete portal, ERP, and metering labels "
            "detected on the supplied public pages, using the exact vendor labels and relevant "
            "source tags. Sentence two must say these are unverified page observations that a "
            "human must confirm before relying on them. Use only the supplied retrieved signals; "
            "do not add external facts, company names, people, emails, market-size claims, "
            "conversion claims, or accuracy claims. Do not infer infrastructure, deployment, "
            "compatibility, integration points, data exchange, performance, or company fit. "
            "The application adds measured figures separately, so do not write numeric "
            "measurements or counts. Vendor labels may be repeated only exactly as supplied, "
            "including digits that are part of a vendor name. Cite every source-specific claim "
            "with its exact supplied tag and include at least one tag. Do not use lists. Return "
            "only the two sentences."
        )
        narrative_sources = [
            {
                "id": source["id"],
                "page_type": (
                    "service"
                    if source["page_type"].lower() == "leistungen"
                    else source["page_type"]
                ),
                "signals": source["signals"],
            }
            for source in packet["retrieved_sources"]
        ]
        user_prompt = json.dumps(
            {
                "project": "A local lead-intelligence pilot for property managers",
                "narrative_scope": "Interpret only the qualitative website signals listed below. The application adds all counts and score figures separately from SQLite.",
                "citation_rule": "Use exact source tags from this list in the prose: "
                + ", ".join(f"[{source_id}]" for source_id in sorted(source_ids)),
                "retrieved_stage3_sources": narrative_sources,
                "latest_run_warnings": packet["latest_run_summary"].get("warnings", []),
            },
            ensure_ascii=False,
        )
        payload = {
            "model": provider_cfg["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 700,
        }
        if provider_cfg["model"].lower().startswith("nvidia/nemotron-3.5-lightning"):
            # This reasoning model otherwise spends the short prose budget on
            # internal reasoning and may return no final assistant content.
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        headers = {
            "Authorization": f"Bearer {provider_cfg['api_key']}",
            "Content-Type": "application/json",
        }
        endpoint = f"{provider_cfg['base_url'].rstrip('/')}/chat/completions"
        started = time.perf_counter()
        prompt_tokens = 0
        completion_tokens = 0
        provider = provider_cfg["provider"]
        model = provider_cfg["model"]
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._record_audit(
                provider,
                model,
                0,
                0,
                latency_ms,
                True,
                f"Provider request failed: {type(exc).__name__}.",
            )
            raise CaseStudyWriterError(
                "The case-study provider could not be reached."
            ) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code != 200:
            self._record_audit(
                provider,
                model,
                0,
                0,
                latency_ms,
                True,
                f"Provider returned HTTP {response.status_code}.",
            )
            raise CaseStudyWriterError(
                f"The configured case-study provider returned HTTP {response.status_code}."
            )
        try:
            response_data = response.json()
            choices = response_data.get("choices") or []
            choice = choices[0] if choices else {}
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            if not isinstance(message, dict):
                message = {}
            content = message.get("content")
            if not str(content or "").strip() and isinstance(choice, dict):
                content = choice.get("text")
            narrative = str(content or "").strip()
            usage = response_data.get("usage") or {}
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            completion_tokens = int(usage.get("completion_tokens", 0))
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            self._record_audit(
                provider,
                model,
                prompt_tokens,
                completion_tokens,
                latency_ms,
                True,
                "Provider returned an invalid response payload.",
            )
            raise CaseStudyWriterError(
                "The case-study provider returned an invalid response."
            ) from exc
        if not narrative:
            self._record_audit(
                provider,
                model,
                prompt_tokens,
                completion_tokens,
                latency_ms,
                True,
                "Provider returned no final narrative content; reasoning-only output was discarded.",
            )
            raise CaseStudyWriterError(
                "The configured provider returned no final narrative content. Choose a chat model that returns a final response."
            )
        try:
            allowed_numeric_labels = {
                signal.split(":", 1)[1].strip()
                for source in packet["retrieved_sources"]
                for signal in source["signals"]
                if signal.startswith(
                    ("ERP signature detected:", "metering technology signal detected:")
                )
            }
            self._validate_narrative(narrative, source_ids, allowed_numeric_labels)
        except CaseStudyNarrativeRejected as exc:
            self._record_audit(
                provider,
                model,
                prompt_tokens,
                completion_tokens,
                latency_ms,
                True,
                str(exc),
            )
            raise

        document = self._build_document(packet, narrative, provider, model)
        settings.ensure_dirs()
        output_path = settings.export_dir / self.output_name
        output_path.write_text(document, encoding="utf-8")
        self._record_audit(
            provider,
            model,
            prompt_tokens,
            completion_tokens,
            latency_ms,
            False,
            "Narrative generated from retrieved Stage 3 evidence; numeric facts were added from SQLite.",
        )
        return {
            "status": "ready",
            "provider": provider,
            "model": model,
            "source_count": len(packet["retrieved_sources"]),
            "source_ids": sorted(source_ids),
            "latest_run_id": (packet["latest_run"] or {}).get("run_id"),
            "path": str(output_path),
            "markdown": document,
            "download_url": "/api/artifacts/download/current-case-study",
            "preview_url": "/api/artifacts/preview/current-case-study",
        }
