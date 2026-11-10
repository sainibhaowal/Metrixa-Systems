"""
Metrixa Cockpit Web API Server Entrypoint.
Starts the FastAPI backend on http://127.0.0.1:8000 with interactive docs at /docs.
All pipeline orchestration, leads exploration, and telemetry run 100% via the Web UI.
"""

from __future__ import annotations

import uvicorn
from metrixa_engine.config import settings


def main() -> None:
    uvicorn.run(
        "metrixa_engine.api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
