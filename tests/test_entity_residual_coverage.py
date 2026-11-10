from __future__ import annotations

from metrixa_engine.db import Database
from metrixa_engine.entity_resolution.deduplicator import EntityDeduplicator, UnionFind
from metrixa_engine.entity_resolution.normalizer import normalize_phone_e164
from metrixa_engine.models import RawListing


def _record(name="Alpha Management", **values):
    base = {
        "canonical_name": name,
        "canonical_domain": None,
        "phone_e164": None,
        "address_key": None,
        "clean_plz": None,
    }
    base.update(values)
    return base


def test_union_find_rank_directions_and_match_signals():
    uf = UnionFind(6)
    uf.union(0, 1)  # equal ranks
    uf.union(0, 2)  # rank(root 0) > rank(root 2)
    uf.union(3, 0)  # rank(root 3) < rank(root 0)
    uf.union(1, 2)  # already in the same component
    assert len({uf.find(i) for i in (0, 1, 2, 3)}) == 1

    assert EntityDeduplicator.is_match(_record(""), _record("")) is False
    assert EntityDeduplicator.is_match(
        _record(canonical_domain="alpha.de"), _record(canonical_domain="alpha.de")
    )
    assert EntityDeduplicator.is_match(
        _record(phone_e164="+49305550123"), _record(phone_e164="+49305550123")
    )
    assert EntityDeduplicator.is_match(
        _record(address_key="10115_main1"), _record(address_key="10115_main1")
    )
    assert EntityDeduplicator.is_match(
        _record(clean_plz="10115"), _record(clean_plz="10115")
    )
    assert EntityDeduplicator.is_match(
        _record("same management name"), _record("same management name")
    )
    assert not EntityDeduplicator.is_match(
        _record("Alpha Management", clean_plz="10115"),
        _record("Other Firm", clean_plz="10969"),
    )


def test_dedup_malformed_payload_disqualified_cluster_and_existing_survivors(tmp_path):
    db = Database(tmp_path / "dedup-residual.db")
    db.insert_raw_listings(
        [
            RawListing(
                source_name="osm",
                raw_company_name="Alpha Hausverwaltung GmbH",
                raw_postal_code="10115",
                raw_city="Berlin",
                raw_website="https://alpha.de",
            ),
            RawListing(
                source_name="gelbe_seiten",
                raw_company_name="Alpha Hausverwaltung GmbH",
                raw_postal_code="10115",
                raw_city="Berlin",
                raw_website="https://alpha.de",
            ),
            RawListing(
                source_name="11880",
                raw_company_name="Beta Hausverwaltung GmbH",
                raw_postal_code="10719",
                raw_city="Berlin",
                raw_website="https://beta.de",
            ),
            RawListing(
                source_name="unknown",
                raw_company_name="Gamma Hausverwaltung GmbH",
                raw_postal_code="10969",
                raw_city="Berlin",
            ),
            RawListing(
                source_name="osm",
                raw_company_name="Munich Cleaning GmbH",
                raw_postal_code="80331",
                raw_city="Munich",
            ),
        ]
    )
    with db.connect() as conn:
        conn.execute(
            "UPDATE raw_listings SET raw_json_payload='{malformed' WHERE raw_company_name='Gamma Hausverwaltung GmbH'"
        )
        alpha_id = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,canonical_domain,pipeline_stage,sources_csv,updated_at) VALUES ('alpha','Old Alpha','alpha.de','EXTRACTED','old','now')"
        ).lastrowid
        beta_id = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,canonical_domain,pipeline_stage,sources_csv,updated_at) VALUES ('beta','Old Beta','beta.de','SCORED','old','now')"
        ).lastrowid
        conn.execute(
            "INSERT INTO crawled_pages (company_id,page_type,url,http_status,crawled_at) VALUES (?, 'homepage','https://beta.de',200,'now')",
            (beta_id,),
        )

    result = EntityDeduplicator(db).run_deduplication()
    assert result["raw_total"] == 5 and result["eligible_count"] == 4
    assert result["disqualified_count"] == 1 and result["golden_clusters"] == 3
    with db.connect() as conn:
        alpha = conn.execute(
            "SELECT display_name,pipeline_stage,source_count FROM companies_golden WHERE company_id=?",
            (alpha_id,),
        ).fetchone()
        beta = conn.execute(
            "SELECT pipeline_stage FROM companies_golden WHERE company_id=?", (beta_id,)
        ).fetchone()
        alpha_sources = conn.execute(
            "SELECT COUNT(*) FROM company_sources_map WHERE company_id=?", (alpha_id,)
        ).fetchone()[0]
    assert alpha["pipeline_stage"] == "DEDUPED" and alpha["source_count"] == 2
    assert beta["pipeline_stage"] == "SCORED"
    assert alpha_sources == 2


def test_phone_manual_fallback_variants(monkeypatch):
    import metrixa_engine.entity_resolution.normalizer as module

    def invalid_parse(*args, **kwargs):
        raise ValueError("invalid numbering plan")

    monkeypatch.setattr(module.phonenumbers, "parse", invalid_parse)
    assert normalize_phone_e164("0049 30 123456") == "+4930123456"
    assert normalize_phone_e164("030 1234567") == "+49301234567"
    assert normalize_phone_e164("1234567") == "+491234567"
    assert normalize_phone_e164("12345") is None
