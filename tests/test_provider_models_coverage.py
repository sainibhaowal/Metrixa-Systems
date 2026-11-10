from __future__ import annotations

from fastapi.testclient import TestClient

from metrixa_engine.api import server


class _Response:
    def __init__(self, payload=None, status=200):
        self.payload, self.status_code = payload or {}, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class _Client:
    responses = []
    calls = []
    error = None

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs, self.kwargs))
        if self.error:
            raise self.error
        return self.responses.pop(0)


def test_discover_provider_model_endpoints_and_offline_paths(monkeypatch):
    client = TestClient(server.app)
    monkeypatch.setattr(server.httpx, "AsyncClient", _Client)
    _Client.calls.clear()
    assert (
        client.post("/api/providers/models", json={"provider": "unknown"}).json()[
            "source"
        ]
        == "system"
    )
    for provider in ("openai", "deepseek", "gemini", "nvidia_nim"):
        result = client.post(
            "/api/providers/models", json={"provider": provider}
        ).json()
        assert result["status"] == "awaiting_key" and result["models"] == []

    _Client.responses = [
        _Response(
            {
                "models": [
                    {
                        "model": "qwen:small",
                        "size": 1073741824,
                        "details": {
                            "parameter_size": "7B",
                            "quantization_level": "Q4",
                            "family": "qwen",
                        },
                    },
                    {},
                    {"name": "llama:latest", "size": 0, "details": {"family": "llama"}},
                ]
            }
        )
    ]
    result = client.post(
        "/api/providers/models",
        json={"provider": "ollama", "base_url": "http://localhost:11434/v1/"},
    ).json()
    assert result["status"] == "ok" and result["source"] == "live_api"
    assert (
        result["models"][0]["id"] == "qwen:small"
        and result["models"][0]["recommended"] is True
    )
    assert (
        "7B" in result["models"][0]["name"]
        and "1.0 GB" in result["models"][0]["capabilities"]
    )
    assert result["models"][1]["capabilities"] == "Family: llama"
    assert _Client.calls[-1][0] == "http://localhost:11434/api/tags"

    # An empty Ollama response falls through to its OpenAI-compatible /models endpoint.
    _Client.responses = [
        _Response({"models": []}),
        _Response({"data": [{"id": "llama3", "max_model_len": 8192}]}),
    ]
    result = client.post(
        "/api/providers/models",
        json={"provider": "ollama", "base_url": "http://local:11434"},
    ).json()
    assert result["models"][0]["context_window"] == "8,192 tokens"
    assert _Client.calls[-2][0] == "http://local:11434/api/tags"

    _Client.responses = [
        _Response(
            {
                "models": [
                    {
                        "name": "models/gemini-flash",
                        "displayName": "Flash",
                        "supportedGenerationMethods": ["generateContent"],
                        "inputTokenLimit": 128000,
                        "outputTokenLimit": 8192,
                    },
                    {
                        "name": "models/gemini-embed",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                    {"name": "", "supportedGenerationMethods": ["generateContent"]},
                    {
                        "name": "models/gemini-small",
                        "supportedGenerationMethods": ["generateContent"],
                        "inputTokenLimit": 0,
                        "outputTokenLimit": 0,
                    },
                ]
            }
        )
    ]
    result = client.post(
        "/api/providers/models", json={"provider": "gemini", "api_key": "test-key"}
    ).json()
    assert len(result["models"]) == 2
    assert (
        result["models"][0]["id"] == "gemini-flash"
        and result["models"][0]["context_window"] == "128,000 tokens"
    )
    assert result["models"][0]["capabilities"] == "Max Output: 8,192 tokens"
    assert result["models"][1]["capabilities"] == "Google Generative Language API"
    assert "key=test-key" in _Client.calls[-1][0]


def test_openai_compatible_model_filter_context_and_empty(monkeypatch):
    client = TestClient(server.app)
    monkeypatch.setattr(server.httpx, "AsyncClient", _Client)
    _Client.error = None
    _Client.responses = [
        _Response(
            {
                "data": [
                    {"id": "gpt-z", "context_window": 128000, "owned_by": "openai"},
                    {"id": "text-embedding-3-small"},
                    {"id": "whisper-1"},
                    {"id": "tts-1"},
                    {"id": "davinci-002"},
                    {"id": "babbage-002"},
                    {"id": "omni-moderation-latest"},
                    {"id": "audio-preview"},
                    {"id": "realtime-preview"},
                    {"id": "gpt-a", "context_window": "Live API model"},
                    {},
                    "bad",
                ]
            }
        )
    ]
    result = client.post(
        "/api/providers/models",
        json={
            "provider": "openai",
            "api_key": "test-key",
            "base_url": "https://api.example/v1",
        },
    ).json()
    assert [m["id"] for m in result["models"]] == ["gpt-a", "gpt-z"]
    assert result["models"][0]["context_window"] == ""
    assert result["models"][1]["context_window"] == "128,000 tokens"
    assert _Client.calls[-1][1]["headers"]["Authorization"] == "Bearer test-key"

    _Client.responses = [
        _Response(
            {
                "data": [
                    {"id": "model", "context_window": "context x"},
                    {"id": "second", "max_model_len": "64k"},
                    {"id": "placeholder", "context_window": "api model live"},
                ]
            }
        )
    ]
    result = client.post(
        "/api/providers/models",
        json={
            "provider": "deepseek",
            "api_key": "secret",
            "base_url": "https://deepseek.example/v1",
        },
    ).json()
    assert [m["context_window"] for m in result["models"]] == ["context x", "", "64k"]

    _Client.responses = [_Response({"data": []})]
    assert (
        client.post(
            "/api/providers/models", json={"provider": "nvidia_nim", "api_key": "key"}
        ).json()["status"]
        == "empty"
    )
    _Client.error = OSError("provider offline")
    offline = client.post(
        "/api/providers/models", json={"provider": "openai", "api_key": "key"}
    ).json()
    assert offline["status"] == "offline" and "provider offline" in offline["message"]
    _Client.error = None
