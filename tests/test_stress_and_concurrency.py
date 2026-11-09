"""
High-Concurrency Stress & Load Test Suite.
Validates multi-client SSE pub/sub throughput, database connection pool resilience,
and thread-safety under heavy parallel traffic.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient

from metrixa_engine.api.server import app, event_bus


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_stress_concurrent_leads_queries(client: TestClient) -> None:
    """Stress test: 40 concurrent lead grid queries with mixed filters."""
    endpoints = [
        "/api/leads?limit=15&page=1",
        "/api/leads?limit=15&page=2",
        "/api/leads?tier=Tier+A&limit=10",
        "/api/leads?district=Mitte&limit=10",
        "/api/leads?district=Charlottenburg-Wilmersdorf&limit=10",
        "/api/leads?has_email=true&limit=10",
        "/api/leads?has_dm=true&limit=10",
        "/api/leads?has_erp=true&limit=10",
    ]

    def _make_request(url: str) -> int:
        resp = client.get(url)
        return resp.status_code

    urls = endpoints * 5  # 40 requests
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(_make_request, urls))

    assert len(statuses) == 40
    assert all(code == 200 for code in statuses)


def test_stress_concurrent_metrics_endpoints(client: TestClient) -> None:
    """Stress test: 30 concurrent telemetry metric fetches."""
    def _fetch_metrics(_: int) -> int:
        resp = client.get("/api/metrics")
        return resp.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_fetch_metrics, range(30)))

    assert len(results) == 30
    assert all(code == 200 for code in results)


@pytest.mark.asyncio
async def test_stress_event_bus_multi_subscriber_broadcasting() -> None:
    """Stress test: 20 simultaneous SSE subscriber queues receiving high-frequency events."""
    subscribers = [event_bus.subscribe() for _ in range(20)]
    try:
        # Emit 15 broadcast events
        for idx in range(15):
            await event_bus.emit("LOG", {"level": "INFO", "message": f"Stress test log {idx}"})

        # Verify all 20 queues received all 15 events
        for q in subscribers:
            assert q.qsize() == 15
            first_msg = q.get_nowait()
            assert first_msg["type"] == "LOG"
            assert "Stress test log 0" in first_msg["message"]
    finally:
        for q in subscribers:
            event_bus.unsubscribe(q)
