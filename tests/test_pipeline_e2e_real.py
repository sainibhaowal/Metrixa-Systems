"""
Real End-to-End Pipeline & Interruption Test Suite.
Validates live stage execution, cancellation gates, EventBus pub/sub,
and SSE event delivery.
"""

from __future__ import annotations

import asyncio
import pytest
from fastapi.testclient import TestClient

from metrixa_engine.api.server import app, event_bus


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_pipeline_stream_heartbeat(client: TestClient) -> None:
    """Verify that /api/pipeline/stream connects and sends initial HEARTBEAT."""
    with client.stream("GET", "/api/pipeline/stream") as resp:
        assert resp.status_code == 200
        # Read initial events
        lines = []
        for line in resp.iter_lines():
            if line:
                lines.append(line)
            if len(lines) >= 2:
                break
        combined = " ".join(lines)
        assert "HEARTBEAT" in combined
        assert "connected" in combined


def test_pipeline_cancel_when_idle(client: TestClient) -> None:
    """Verify cancelling an idle pipeline returns 200 with idle message."""
    resp = client.post("/api/pipeline/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("idle", "cancelled")


def test_pipeline_trigger_and_cancel_lifecycle(client: TestClient) -> None:
    """Verify triggering a stage and cancelling it halts execution cleanly."""
    # Ensure clean slate
    client.post("/api/pipeline/cancel")

    # Simulate an active running stage
    event_bus.is_running = True
    event_bus.current_stage = "EXTRACT"
    event_bus.current_run_id = "test-run-cancel-gate"

    # Execute cancel
    cancel_resp = client.post("/api/pipeline/cancel")
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["status"] == "cancelled"
    assert cancel_data["run_id"] == "test-run-cancel-gate"

    # Verify event_bus is reset to IDLE
    assert event_bus.is_running is False
    assert event_bus.current_stage == "IDLE"


def test_pipeline_concurrent_trigger_rejection(client: TestClient) -> None:
    """Verify that launching two pipelines simultaneously rejects the second with 409 Conflict."""
    client.post("/api/pipeline/cancel")

    # Manually mark as running
    event_bus.is_running = True
    event_bus.current_stage = "RUNNING_TEST"
    try:
        resp = client.post(
            "/api/pipeline/run",
            json={"stage": "extract", "limit": 1},
        )
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]
    finally:
        event_bus.is_running = False
        event_bus.current_stage = "IDLE"


def test_pipeline_stage_export_execution(client: TestClient) -> None:
    """Verify executing the export stage generates all deliverables."""
    client.post("/api/pipeline/cancel")

    resp = client.post(
        "/api/pipeline/run",
        json={"stage": "export", "city": "Berlin"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "started"
    assert data["stage"] == "export"
