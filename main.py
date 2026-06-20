"""Unified start entrypoint for soundbox-lakehouse (Web server or Ingestion job)."""

from __future__ import annotations

import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    
    # 1. Determine run mode (server vs ingestion)
    run_mode = os.environ.get("RUN_MODE", "").lower()
    is_server = (
        "PORT" in os.environ 
        or run_mode == "server" 
        or (len(sys.argv) > 1 and sys.argv[1] == "server")
    )

    if is_server:
        port = int(os.environ.get("PORT", "8080"))
        print(f"[main] Starting FastAPI Web Server on port {port}...")
        uvicorn.run("app.server:app", host="0.0.0.0", port=port)
    else:
        print(f"[main] Starting Ingestion Job using engine '{settings.ingest_engine}'...")
        from ingestion.run import run as run_ingestion
        summary = run_ingestion(settings)
        print("[main] Ingestion job finished. Summary:", summary)


if __name__ == "__main__":
    main()
