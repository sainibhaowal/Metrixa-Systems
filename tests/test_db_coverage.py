from __future__ import annotations

from metrixa_engine.db import Database
from metrixa_engine.models import RawListing


def test_database_keeps_wal_mode_without_reissuing_mode_change(tmp_path):
    db = Database(tmp_path / "wal-mode.db")
    with db.connect() as first:
        assert first.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    with db.connect() as second:
        assert second.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_raw_listing_empty_duplicate_and_enrichment_update(tmp_path):
    db = Database(tmp_path / "raw-insert.db")
    assert db.insert_raw_listings([]) == 0
    base = RawListing(
        source_name="directory", raw_company_name="Alpha GmbH", raw_postal_code="10115"
    )
    assert db.insert_raw_listings([base]) == 1
    # Exact duplicates with no new contact fields are skipped.
    assert db.insert_raw_listings([base]) == 0
    # A fresh observation updates known fields without inflating the insert count.
    enriched = RawListing(
        source_name="directory",
        raw_company_name="Alpha GmbH",
        raw_postal_code="10115",
        raw_email="contact@alpha.de",
        raw_website="https://alpha.de",
    )
    assert db.insert_raw_listings([enriched]) == 0
    # A later source observation refreshes non-empty values and the last-seen timestamp.
    later = RawListing(
        source_name="directory",
        raw_company_name="Alpha GmbH",
        raw_postal_code="10115",
        raw_email="other@alpha.de",
        raw_website="https://other.de",
    )
    result = db.upsert_raw_listings([later])
    assert result == {"inserted": 0, "refreshed": 1}
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT raw_email, raw_website, scraped_at FROM raw_listings"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["raw_email"] == "other@alpha.de"
    assert rows[0]["raw_website"] == "https://other.de"
    assert rows[0]["scraped_at"] != base.scraped_at.isoformat()


def test_init_schema_clears_uncalibrated_legacy_confidence(tmp_path):
    db = Database(tmp_path / "confidence-migration.db")
    with db.connect() as conn:
        company_id = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,sources_csv,updated_at) VALUES ('alpha','Alpha GmbH','directory','now')"
        ).lastrowid
        conn.execute(
            "INSERT INTO kpi_extractions (company_id,extraction_confidence,extracted_at) VALUES (?,0.92,'old')",
            (company_id,),
        )

    db.init_schema()

    with db.connect() as conn:
        confidence = conn.execute(
            "SELECT extraction_confidence FROM kpi_extractions WHERE company_id=?",
            (company_id,),
        ).fetchone()[0]
    assert confidence is None


def test_vdiv_migration_tolerates_malformed_payload_and_updates_claims(tmp_path):
    db = Database(tmp_path / "migration.db")
    db.insert_raw_listings(
        [
            RawListing(
                source_name="vdiv",
                raw_company_name="Bad payload GmbH",
                raw_payload={"verified_vdiv_member": True},
            ),
            RawListing(
                source_name="vdiv",
                raw_company_name="Normal payload GmbH",
                raw_payload={"verified_vdiv_member": True},
                is_vdiv_member=True,
            ),
        ]
    )
    with db.connect() as conn:
        conn.execute(
            "UPDATE raw_listings SET raw_json_payload='{verified_vdiv_member: ' WHERE raw_company_name='Bad payload GmbH'"
        )
        # One company is mapped only to the legacy VDIV claim; one also has a non-VDIV source.
        raw_ids = {
            r["raw_company_name"]: r["id"]
            for r in conn.execute("SELECT id, raw_company_name FROM raw_listings")
        }
        legacy_company = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,is_vdiv_member,sources_csv,updated_at) VALUES ('legacy','Legacy GmbH',1,'vdiv','old')"
        ).lastrowid
        mixed_company = conn.execute(
            "INSERT INTO companies_golden (canonical_name,display_name,is_vdiv_member,sources_csv,updated_at) VALUES ('mixed','Mixed GmbH',1,'vdiv,directory','old')"
        ).lastrowid
        conn.execute(
            "INSERT INTO company_sources_map VALUES (?,?)",
            (legacy_company, raw_ids["Normal payload GmbH"]),
        )
        conn.execute(
            "INSERT INTO company_sources_map VALUES (?,?)",
            (mixed_company, raw_ids["Normal payload GmbH"]),
        )
        # An additional real source prevents the mixed company from being quarantined.
        cur = conn.execute(
            "INSERT INTO raw_listings (source_name,raw_company_name,scraped_at) VALUES ('directory','Mixed source GmbH','now')"
        )
        conn.execute(
            "INSERT INTO company_sources_map VALUES (?,?)",
            (mixed_company, cur.lastrowid),
        )
    db.init_schema()
    events = db.get_run_events("no-events")
    assert events == []
    with db.connect() as conn:
        malformed = conn.execute(
            "SELECT raw_json_payload FROM raw_listings WHERE raw_company_name='Bad payload GmbH'"
        ).fetchone()[0]
        legacy = conn.execute(
            "SELECT is_vdiv_member,raw_json_payload FROM raw_listings WHERE raw_company_name='Normal payload GmbH'"
        ).fetchone()
        states = {
            r["canonical_name"]: r["is_vdiv_member"]
            for r in conn.execute(
                "SELECT canonical_name,is_vdiv_member FROM companies_golden"
            )
        }
    assert malformed == "{verified_vdiv_member: "
    assert legacy["is_vdiv_member"] == 0
    assert states["legacy"] == 0 and states["mixed"] == 0


def test_run_event_json_payload_and_corrupt_payload(tmp_path):
    db = Database(tmp_path / "events.db")
    db.record_run_event(
        "run", 1, "INGEST", "one", "STEP", "INFO", 5, "valid", {"rows": 2}
    )
    db.record_run_event("run", 2, "CRAWL", "two", "STEP", "WARN", 0, "none")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO pipeline_run_events (run_id,seq,timestamp,stage,step_name,event_type,level,duration_ms,message,payload_json) VALUES ('run',3,'now','CRAWL','three','STEP','ERROR',0,'broken','{bad')"
        )
    events = db.get_run_events("run")
    assert events[0]["payload"] == {"rows": 2}
    assert events[1]["payload"] is None
    assert events[2]["payload"] is None
