from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from metrixa_engine.api import server


class _Response:
    def __init__(self, data=None, status=200, body=""):
        self._data, self.status_code, self.text = data or {}, status, body

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://provider.example/chat/completions")
            response = httpx.Response(self.status_code, request=request, text=self.text)
            raise httpx.HTTPStatusError(
                "provider error", request=request, response=response
            )


class _Client:
    response = _Response(
        {"choices": [{"message": {"content": "PONG"}}], "usage": {"total_tokens": 1}}
    )
    error = None
    calls = []

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs, self.kwargs))
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def client():
    return TestClient(server.app)


def test_runtime_settings_persistence_replaces_and_appends_atomically(
    tmp_path, monkeypatch
):
    env_file = tmp_path / "runtime.env"
    env_file.write_bytes(b"# keep\r\nexport OPENAI_API_KEY=old\r\nTAIL=1")
    monkeypatch.setenv("METRIXA_ENV_PATH", str(env_file))
    server._persist_runtime_settings(
        {"openai_api_key": 'quote" slash\\ line\nnext', "new_flag": True}
    )
    text = env_file.read_text(encoding="utf-8")
    assert text.startswith('# keep\nOPENAI_API_KEY="quote\\" slash\\\\ line\\nnext"\n')
    assert 'NEW_FLAG="true"' in text and "TAIL=1\n" in text


def test_settings_update_normalization_empty_body_and_write_failure(
    client, monkeypatch, tmp_path
):
    env_file = tmp_path / "settings.env"
    monkeypatch.setenv("METRIXA_ENV_PATH", str(env_file))
    old = server.settings.searxng_base_url
    monkeypatch.setattr(server.settings, "searxng_base_url", old)
    response = client.post(
        "/api/settings",
        json={
            "searxng_base_url": " http://localhost:8888/// ",
            "default_search_provider": "google_cse",
        },
    )
    assert response.status_code == 200
    assert server.settings.searxng_base_url == "http://localhost:8888"
    assert 'SEARXNG_BASE_URL="http://localhost:8888"' in env_file.read_text(
        encoding="utf-8"
    )
    assert client.post("/api/settings", json={}).json()["persisted"] is True
    monkeypatch.setattr(
        server,
        "_persist_runtime_settings",
        lambda updates: (_ for _ in ()).throw(OSError("disk full")),
    )
    failed = client.post("/api/settings", json={"openai_model": "model"})
    assert failed.status_code == 500


def test_provider_ping_reasoning_gemini_native_errors_and_auto(client, monkeypatch):
    monkeypatch.setattr(server.httpx, "AsyncClient", _Client)
    _Client.error = None
    _Client.calls.clear()
    assert (
        client.post("/api/providers/ping", json={"provider": "auto_fallback"}).json()[
            "status"
        ]
        == "degraded"
    )

    # O-series and reasoner provider payloads use their compatible token fields.
    _Client.response = _Response(
        {"choices": [{"message": {"reasoning_content": "PONG from reasoning"}}]}
    )
    response = client.post(
        "/api/providers/ping",
        json={
            "provider": "openai",
            "api_key": "secret",
            "model": "o3-mini",
            "base_url": "https://api.example/v1",
        },
    ).json()
    assert response["status"] == "ok" and response["reply"] == "PONG from reasoning"
    assert "max_completion_tokens" in _Client.calls[-1][1]["json"]

    _Client.response = _Response({"choices": [{"text": "PONG from text"}]})
    response = client.post(
        "/api/providers/ping",
        json={
            "provider": "deepseek",
            "api_key": "secret",
            "model": "deepseek-reasoner",
            "base_url": "https://api.example/v1",
        },
    ).json()
    assert (
        response["reply"] == "PONG from text"
        and "max_tokens" in _Client.calls[-1][1]["json"]
    )

    _Client.response = _Response(
        {
            "candidates": [{"content": {"parts": [{"text": "Gemini native PONG"}]}}],
            "usage": {"total_tokens": 5},
        }
    )
    response = client.post(
        "/api/providers/ping",
        json={"provider": "gemini", "api_key": "secret", "model": "gemini-test"},
    ).json()
    assert response["reply"] == "Gemini native PONG" and response["tokens"] == 5

    # Empty standard choices and empty Gemini candidate lists produce a real diagnostic.
    _Client.response = _Response({"choices": []})
    assert (
        client.post(
            "/api/providers/ping",
            json={"provider": "openai", "api_key": "secret", "model": "gpt"},
        ).json()["status"]
        == "error"
    )
    _Client.response = _Response({"candidates": []})
    assert (
        client.post(
            "/api/providers/ping",
            json={"provider": "gemini", "api_key": "secret", "model": "gemini"},
        ).json()["status"]
        == "error"
    )

    _Client.error = httpx.ConnectError("offline")
    error = client.post(
        "/api/providers/ping",
        json={
            "provider": "ollama",
            "model": "llama",
            "base_url": "http://localhost:11434/v1",
        },
    ).json()
    assert error["status"] == "error" and "Connection refused" in error["error"]
    _Client.error = None
    _Client.response = _Response(status=401, body="secret server detail")
    auth = client.post(
        "/api/providers/ping",
        json={"provider": "openai", "api_key": "secret", "model": "gpt"},
    ).json()
    assert "Authentication Failed (401)" in auth["error"]
    _Client.response = _Response(status=404, body="model missing")
    missing = client.post(
        "/api/providers/ping",
        json={"provider": "openai", "api_key": "secret", "model": "gpt"},
    ).json()
    assert "not found" in missing["error"]
    _Client.response = _Response(status=500, body="server exploded")
    generic = client.post(
        "/api/providers/ping",
        json={"provider": "openai", "api_key": "secret", "model": "gpt"},
    ).json()
    assert "HTTP 500" in generic["error"]
    _Client.error = OSError("unexpected")
    assert (
        client.post(
            "/api/providers/ping",
            json={"provider": "openai", "api_key": "secret", "model": "gpt"},
        ).json()["error"]
        == "unexpected"
    )
    _Client.error = None
    _Client.response = _Response({"choices": [{"message": {"content": "PONG"}}]})
