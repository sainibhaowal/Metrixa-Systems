from __future__ import annotations

from pathlib import Path

import pytest

from metrixa_engine.config import (
    BERLIN_DISTRICTS,
    Settings,
    is_valid_berlin_plz,
    map_berlin_plz_to_district,
)


def test_path_and_cors_defaults_and_valid_settings(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("EXPORT_DIR", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    defaults = Settings()
    assert defaults.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert defaults.database_path.is_absolute() and defaults.export_dir.is_absolute()

    monkeypatch.setenv("DATABASE_PATH", "relative/db.sqlite")
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("CORS_ORIGINS", " https://app.example/,http://127.0.0.1:3000 ")
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "8765")
    configured = Settings()
    assert (
        configured.database_path
        == (Path(configured.project_root) / "relative/db.sqlite").resolve()
    )
    assert configured.export_dir == (tmp_path / "exports").resolve()
    assert configured.cors_origins == ["https://app.example", "http://127.0.0.1:3000"]
    assert configured.api_host == "0.0.0.0" and configured.api_port == 8765
    configured.ensure_dirs()
    assert configured.database_path.parent.exists() and configured.export_dir.exists()


def test_berlin_postcode_and_district_fallbacks():
    assert not is_valid_berlin_plz(None)
    assert not is_valid_berlin_plz("1234")
    assert not is_valid_berlin_plz("99999")
    assert is_valid_berlin_plz("101-15")
    assert map_berlin_plz_to_district(None) == "Berlin (Allgemein)"
    assert map_berlin_plz_to_district("abc") == "Berlin (Allgemein)"
    assert map_berlin_plz_to_district("99999") == "Umland / Brandenburg"
    assert map_berlin_plz_to_district("abc", "Pankow") == "Pankow"
    assert map_berlin_plz_to_district(None, "Some district") == "Some district"
    assert (
        map_berlin_plz_to_district("99999", "Charlottenburg-Wilmersdorf district")
        == "Charlottenburg-Wilmersdorf"
    )

    expected = {
        "10551": BERLIN_DISTRICTS[0],
        "10961": BERLIN_DISTRICTS[1],
        "10405": BERLIN_DISTRICTS[2],
        "10315": BERLIN_DISTRICTS[10],
        "10585": BERLIN_DISTRICTS[3],
        "10777": BERLIN_DISTRICTS[6],
        "12043": BERLIN_DISTRICTS[7],
        "12157": BERLIN_DISTRICTS[5],
        "12435": BERLIN_DISTRICTS[8],
        "12619": BERLIN_DISTRICTS[9],
        "13403": BERLIN_DISTRICTS[11],
        "13581": BERLIN_DISTRICTS[4],
        "11000": BERLIN_DISTRICTS[0],
    }
    for postcode, district in expected.items():
        assert map_berlin_plz_to_district(postcode) == district
    assert map_berlin_plz_to_district("abc", "Outside") == "Outside"


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "ftp://example.com",
        "https://",
        "https://example.com/path",
        "https://example.com?q=x",
        "https://example.com#frag",
    ],
)
def test_cors_rejects_non_origin_values(monkeypatch, origin):
    monkeypatch.setenv("CORS_ORIGINS", origin)
    with pytest.raises(ValueError):
        Settings()
