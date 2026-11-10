"""
Multi-Key Blocking + RapidFuzz Token Sort Ratio + Union-Find Disjoint-Set
Entity Resolution & Golden Record Survivorship Engine.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple
from rapidfuzz import fuzz

from metrixa_engine.config import map_berlin_plz_to_district
from metrixa_engine.db import Database
from metrixa_engine.entity_resolution.normalizer import (
    canonicalize_company_name,
    check_listing_eligibility,
    extract_canonical_domain,
    extract_legal_form,
    normalize_address_key,
    normalize_phone_e164,
    normalize_website_url,
)

SOURCE_TRUST_RANK = {
    "vdiv": 100,
    "gelbe_seiten": 80,
    "11880": 70,
    "osm": 60,
    "searxng_discovery": 50,
}


class UnionFind:
    """Path-compressed Disjoint-Set data structure for O(N alpha(N)) entity clustering."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, i: int) -> int:
        if self.parent[i] != i:
            self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i: int, j: int) -> None:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i == root_j:
            return
        if self.rank[root_i] < self.rank[root_j]:
            self.parent[root_i] = root_j
        elif self.rank[root_i] > self.rank[root_j]:
            self.parent[root_j] = root_i
        else:
            self.parent[root_j] = root_i
            self.rank[root_i] += 1


class EntityDeduplicator:
    """Deduplicates raw scraped Berlin listings into Golden Company records."""

    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def is_match(rec_a: Dict[str, Any], rec_b: Dict[str, Any]) -> bool:
        """
        Deterministic + Fuzzy matching rule between two normalized records:
        1. Exact Canonical Domain match + Name TokenSortRatio >= 55 (or identical domain root)
        2. Exact E.164 Phone match + Name TokenSortRatio >= 65
        3. Exact Normalized Street+PLZ match + Name TokenSortRatio >= 78
        4. Same Berlin PLZ + Name TokenSortRatio >= 90
        5. Identical Canonical Name (length >= 8) across Berlin
        """
        name_a = rec_a["canonical_name"]
        name_b = rec_b["canonical_name"]
        if not name_a or not name_b:
            return False

        sim = fuzz.token_sort_ratio(name_a, name_b)

        dom_a = rec_a["canonical_domain"]
        dom_b = rec_b["canonical_domain"]
        if dom_a and dom_b and dom_a == dom_b and sim >= 55:
            return True

        ph_a = rec_a["phone_e164"]
        ph_b = rec_b["phone_e164"]
        if ph_a and ph_b and ph_a == ph_b and sim >= 65:
            return True

        addr_a = rec_a["address_key"]
        addr_b = rec_b["address_key"]
        if addr_a and addr_b and addr_a == addr_b and sim >= 78:
            return True

        plz_a = rec_a["clean_plz"]
        plz_b = rec_b["clean_plz"]
        if plz_a and plz_b and plz_a == plz_b and sim >= 90:
            return True

        if name_a == name_b and len(name_a) >= 8:
            return True

        return False

    def run_deduplication(self) -> Dict[str, int]:
        """
        Read all raw_listings, normalize attributes, apply eligibility filter,
        cluster via Multi-Key Blocking + Union-Find, and upsert into companies_golden.
        """
        all_raw_rows = self.db.get_all_raw_listings()
        raw_rows: List[Dict[str, Any]] = []
        source_review_excluded = 0
        for row in all_raw_rows:
            try:
                payload = json.loads(row.get("raw_json_payload") or "{}")
            except (TypeError, json.JSONDecodeError):
                payload = {}
            if (
                isinstance(payload, dict)
                and payload.get("legacy_curated_vdiv_registry_requires_review") is True
            ):
                source_review_excluded += 1
                continue
            raw_rows.append(row)

        if not raw_rows:
            return {
                "raw_total": len(all_raw_rows),
                "eligible_count": 0,
                "disqualified_count": 0,
                "golden_clusters": 0,
                "duplicates_merged": 0,
                "source_review_excluded": source_review_excluded,
            }

        eligible_records: List[Dict[str, Any]] = []
        disqualified_records: List[Tuple[Dict[str, Any], str]] = []

        for row in raw_rows:
            raw_name = row["raw_company_name"]
            raw_plz = row["raw_postal_code"]
            raw_city = row["raw_city"]
            is_ok, reason = check_listing_eligibility(raw_name, raw_plz, raw_city)

            clean_plz = None
            if raw_plz:
                digits = "".join(ch for ch in str(raw_plz) if ch.isdigit())
                if len(digits) == 5:
                    clean_plz = digits

            can_domain = extract_canonical_domain(row["raw_website"], row["raw_email"])
            norm_rec = {
                **row,
                "canonical_name": canonicalize_company_name(raw_name),
                "legal_form": extract_legal_form(raw_name),
                "clean_plz": clean_plz,
                "phone_e164": normalize_phone_e164(row["raw_phone"]),
                "canonical_domain": can_domain,
                "website_url": normalize_website_url(row["raw_website"], can_domain),
                "address_key": normalize_address_key(row["raw_street"], clean_plz),
                "trust_score": SOURCE_TRUST_RANK.get(row["source_name"], 40),
            }

            if is_ok:
                eligible_records.append(norm_rec)
            else:
                disqualified_records.append((norm_rec, reason or "Disqualified"))

        n = len(eligible_records)
        uf = UnionFind(n)

        # Build Multi-Key Blocks to avoid O(N^2) full scan
        blocks: Dict[str, List[int]] = defaultdict(list)
        for idx, rec in enumerate(eligible_records):
            if rec["canonical_domain"]:
                blocks[f"dom:{rec['canonical_domain']}"].append(idx)
            if rec["phone_e164"]:
                blocks[f"ph:{rec['phone_e164']}"].append(idx)
            if rec["clean_plz"]:
                blocks[f"plz:{rec['clean_plz']}"].append(idx)
            if len(rec["canonical_name"]) >= 4:
                blocks[f"pfx:{rec['canonical_name'][:4]}"].append(idx)

        # Compare pairs within blocks
        compared_pairs: Set[Tuple[int, int]] = set()
        for indices in blocks.values():
            if len(indices) < 2 or len(indices) > 400:
                continue
            for i_pos in range(len(indices)):
                idx_a = indices[i_pos]
                for j_pos in range(i_pos + 1, len(indices)):
                    idx_b = indices[j_pos]
                    pair = (min(idx_a, idx_b), max(idx_a, idx_b))
                    if pair in compared_pairs:
                        continue
                    compared_pairs.add(pair)
                    if self.is_match(eligible_records[idx_a], eligible_records[idx_b]):
                        uf.union(idx_a, idx_b)

        # Group into connected components
        clusters: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for idx, rec in enumerate(eligible_records):
            root = uf.find(idx)
            clusters[root].append(rec)

        now_iso = datetime.now(timezone.utc).isoformat()
        current_company_ids: Set[int] = set()

        with self.db.connect() as conn:
            # Rebuild the current source-to-company lineage on every full
            # deduplication. Old mappings survive merges and splits otherwise,
            # causing one raw listing to appear under multiple companies.
            conn.execute(
                """
                DELETE FROM company_sources_map
                WHERE raw_listing_id IN (
                    SELECT id FROM raw_listings
                    WHERE COALESCE(raw_json_payload, '') NOT LIKE
                        '%legacy_curated_vdiv_registry_requires_review%'
                )
                """
            )

            for cluster_members in clusters.values():
                # Sort members by trust_score descending, then completeness
                cluster_members.sort(
                    key=lambda r: (
                        r["trust_score"],
                        1 if r["website_url"] else 0,
                        1 if r["phone_e164"] else 0,
                        1 if r["raw_street"] else 0,
                    ),
                    reverse=True,
                )

                best = cluster_members[0]
                display_name = best["raw_company_name"]
                canonical_name = best["canonical_name"] or display_name.lower()

                legal_form = next(
                    (m["legal_form"] for m in cluster_members if m["legal_form"]), None
                )
                street = next(
                    (m["raw_street"] for m in cluster_members if m["raw_street"]), None
                )
                plz = next(
                    (m["clean_plz"] for m in cluster_members if m["clean_plz"]), None
                )
                district_raw = next(
                    (m["raw_district"] for m in cluster_members if m["raw_district"]),
                    None,
                )
                district = map_berlin_plz_to_district(plz, district_raw)
                phone = next(
                    (m["phone_e164"] for m in cluster_members if m["phone_e164"]), None
                )
                domain = next(
                    (
                        m["canonical_domain"]
                        for m in cluster_members
                        if m["canonical_domain"]
                    ),
                    None,
                )
                website = next(
                    (m["website_url"] for m in cluster_members if m["website_url"]),
                    None,
                )
                email = next(
                    (m["raw_email"] for m in cluster_members if m["raw_email"]), None
                )
                is_vdiv = any(bool(m["is_vdiv_member"]) for m in cluster_members)

                sources_set = sorted({m["source_name"] for m in cluster_members})
                sources_csv = ", ".join(sources_set)
                source_count = len(sources_set)

                # Check if Golden Company already exists (by canonical_domain or canonical_name+plz)
                existing_row = None
                if domain:
                    existing_row = conn.execute(
                        "SELECT company_id, pipeline_stage FROM companies_golden WHERE canonical_domain = ? LIMIT 1",
                        (domain,),
                    ).fetchone()
                if not existing_row:
                    existing_row = conn.execute(
                        "SELECT company_id, pipeline_stage FROM companies_golden WHERE canonical_name = ? AND COALESCE(postal_code, '') = COALESCE(?, '') LIMIT 1",
                        (canonical_name, plz),
                    ).fetchone()

                if existing_row:
                    comp_id = existing_row["company_id"]
                    has_crawled = conn.execute(
                        "SELECT 1 FROM crawled_pages WHERE company_id = ? AND http_status = 200 LIMIT 1",
                        (comp_id,),
                    ).fetchone()
                    if existing_row["pipeline_stage"] == "DISQUALIFIED":
                        new_stage = "CRAWLED" if has_crawled else "DEDUPED"
                    elif website and not has_crawled:
                        new_stage = "DEDUPED"
                    else:
                        new_stage = existing_row["pipeline_stage"]
                    conn.execute(
                        """
                        UPDATE companies_golden
                        SET display_name = COALESCE(?, display_name),
                            legal_form = COALESCE(?, legal_form),
                            street_address = COALESCE(?, street_address),
                            postal_code = COALESCE(?, postal_code),
                            district = COALESCE(?, district),
                            phone_e164 = COALESCE(?, phone_e164),
                            website_url = COALESCE(?, website_url),
                            canonical_domain = COALESCE(?, canonical_domain),
                            general_email = COALESCE(?, general_email),
                            is_vdiv_member = CASE WHEN ? = 1 THEN 1 ELSE is_vdiv_member END,
                            source_count = ?,
                            sources_csv = ?,
                            pipeline_stage = ?,
                            disqualification_reason = NULL,
                            updated_at = ?
                        WHERE company_id = ?
                        """,
                        (
                            display_name,
                            legal_form,
                            street,
                            plz,
                            district,
                            phone,
                            website,
                            domain,
                            email,
                            1 if is_vdiv else 0,
                            source_count,
                            sources_csv,
                            new_stage,
                            now_iso,
                            comp_id,
                        ),
                    )
                else:
                    cur = conn.execute(
                        """
                        INSERT INTO companies_golden (
                            canonical_name, display_name, legal_form, street_address,
                            postal_code, city, district, phone_e164, website_url,
                            canonical_domain, general_email, is_vdiv_member,
                            source_count, sources_csv, pipeline_stage, updated_at
                        ) VALUES (?, ?, ?, ?, ?, 'Berlin', ?, ?, ?, ?, ?, ?, ?, ?, 'DEDUPED', ?)
                        """,
                        (
                            canonical_name,
                            display_name,
                            legal_form,
                            street,
                            plz,
                            district,
                            phone,
                            website,
                            domain,
                            email,
                            1 if is_vdiv else 0,
                            source_count,
                            sources_csv,
                            now_iso,
                        ),
                    )
                    comp_id = cur.lastrowid

                conn.execute(
                    """
                    DELETE FROM company_sources_map
                    WHERE company_id = ? AND raw_listing_id IN (
                        SELECT id FROM raw_listings
                        WHERE raw_json_payload LIKE '%legacy_curated_vdiv_registry_requires_review%'
                    )
                    """,
                    (comp_id,),
                )
                for m in cluster_members:
                    conn.execute(
                        "INSERT OR IGNORE INTO company_sources_map (company_id, raw_listing_id) VALUES (?, ?)",
                        (comp_id, m["id"]),
                    )
                current_company_ids.add(int(comp_id))

            # Keep historical golden rows for traceability, but take rows with
            # no eligible source lineage out of the active sales population.
            stale_update = conn.execute(
                """
                UPDATE companies_golden
                SET pipeline_stage = 'DISQUALIFIED',
                    disqualification_reason = 'no_current_eligible_source_cluster',
                    updated_at = ?
                WHERE pipeline_stage != 'DISQUALIFIED'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM company_sources_map AS source_map
                      JOIN raw_listings AS source
                        ON source.id = source_map.raw_listing_id
                      WHERE source_map.company_id = companies_golden.company_id
                        AND COALESCE(source.raw_json_payload, '') NOT LIKE
                            '%legacy_curated_vdiv_registry_requires_review%'
                  )
                """,
                (now_iso,),
            )
            stale_golden_excluded = max(0, stale_update.rowcount)

        golden_clusters = len(current_company_ids)
        duplicates_merged = max(0, len(eligible_records) - golden_clusters)
        return {
            "raw_total": len(all_raw_rows),
            "eligible_count": len(eligible_records),
            "disqualified_count": len(disqualified_records),
            "golden_clusters": golden_clusters,
            "duplicates_merged": duplicates_merged,
            "source_review_excluded": source_review_excluded,
            "stale_golden_excluded": stale_golden_excluded,
        }
