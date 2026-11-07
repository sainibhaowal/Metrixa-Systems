"""
Metrixa Cockpit Web API Server Entrypoint.
Starts the FastAPI backend on http://127.0.0.1:8000 with interactive docs at /docs.
All pipeline orchestration, leads exploration, and telemetry run 100% via the Web UI.
"""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "heidi_engine.api.server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
