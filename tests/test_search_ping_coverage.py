from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from metrixa_engine.api import server


class _Response:
    def __init__(self, status=200, payload=None, text="remote error"):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _Client:
    response = _Response()
    error = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.response

    async def post(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def client(monkeypatch):
    _Client.response, _Client.error = _Response(), None
    monkeypatch.setattr(server.httpx, "AsyncClient", _Client)
    return TestClient(server.app)


def _ping(client, provider, **kwargs):
    return client.post(
        "/api/search/ping",
        json={"provider": provider, "query": "Berlin property managers", **kwargs},
    )


def test_search_ping_validates_query_and_provider(client):
    assert (
        client.post(
            "/api/search/ping", json={"provider": "searxng", "query": "  "}
        ).status_code
        == 422
    )
    assert _ping(client, "unsupported").status_code == 400


def test_native_search_ok_and_degraded(client, monkeypatch):
    import metrixa_engine.enrichment.search_router as router_module

    async def results(*args, **kwargs):
        return [
            SimpleNamespace(engine="zeta"),
            SimpleNamespace(engine="alpha"),
            SimpleNamespace(engine="alpha"),
        ]

    monkeypatch.setattr(router_module.search_router, "search", results)
    result = _ping(client, "native_metasearch").json()
    assert result["status"] == "ok" and result["engines"] == ["alpha", "zeta"]

    async def empty(*args, **kwargs):
        return []

    monkeypatch.setattr(router_module.search_router, "search", empty)
    assert _ping(client, "internal").json()["status"] == "degraded"


@pytest.mark.parametrize(
    "status,payload,expected",
    [
        (200, {"results": [{"engine": "brave"}, {}, {"engine": "bing"}]}, "ok"),
        (503, {}, "error"),
    ],
)
def test_searxng_success_and_http_error(client, status, payload, expected):
    _Client.response = _Response(status, payload)
    result = _ping(client, "searxng", base_url="http://localhost:8888/").json()
    assert result["status"] == expected
    if expected == "ok":
        assert result["engines"] == ["bing", "brave"]


def test_searxng_connection_error(client):
    _Client.error = OSError("offline")
    assert _ping(client, "searxng").json()["status"] == "error"


def test_tavily_key_success_http_error_and_exception(client):
    assert _ping(client, "tavily").json()["status"] == "error"
    _Client.response = _Response(200, {"results": [{"url": "https://source.invalid"}]})
    assert _ping(client, "tavily", api_key="test-key").json()["status"] == "ok"
    _Client.response = _Response(401, text="denied")
    assert (
        "Tavily Error (401)"
        in _ping(client, "tavily", api_key="test-key").json()["error"]
    )
    _Client.error = OSError("offline")
    assert _ping(client, "tavily", api_key="test-key").json()["error"] == "offline"


def test_brave_key_success_http_error_and_exception(client):
    assert _ping(client, "brave").json()["status"] == "error"
    _Client.response = _Response(
        200, {"web": {"results": [{"url": "https://source.invalid"}]}}
    )
    assert _ping(client, "brave", api_key="test-key").json()["results_count"] == 1
    _Client.response = _Response(429)
    assert (
        "Brave Error (429)"
        in _ping(client, "brave", api_key="test-key").json()["error"]
    )
    _Client.error = OSError("offline")
    assert _ping(client, "brave", api_key="test-key").json()["error"] == "offline"


def test_google_cse_missing_configuration_success_http_error_and_exception(client):
    assert _ping(client, "google_cse").json()["status"] == "error"
    assert (
        "Engine ID" in _ping(client, "google_cse", api_key="test-key").json()["error"]
    )
    _Client.response = _Response(200, {"items": [{"link": "https://source.invalid"}]})
    result = _ping(
        client, "google_cse", api_key="test-key", google_cse_id="engine-id"
    ).json()
    assert result["status"] == "ok" and result["results_count"] == 1
    _Client.response = _Response(503)
    assert (
        _ping(
            client, "google_cse", api_key="test-key", google_cse_id="engine-id"
        ).json()["status"]
        == "error"
    )
    _Client.error = OSError("offline")
    assert (
        "Could not reach"
        in _ping(
            client, "google_cse", api_key="test-key", google_cse_id="engine-id"
        ).json()["error"]
    )
