"""Unified entrypoint — Intelligence API server or ingestion job.

Set RUN_MODE explicitly:
  RUN_MODE=server  → FastAPI (auth/CORS/rate-limit in app/server.py)
  RUN_MODE=ingest  → one-shot Postgres → parquet ingestion job

Missing or invalid RUN_MODE fails at startup — no guessing from PORT or CLI args.
"""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn

from app.config.settings import Settings, get_settings
from app.core.enums.run_mode import RunMode
from app.core.logging import setup_logging
from app.core.messages.startup_messages import StartupMessage
from app.core.startup_validation import validate_server_startup

logger = logging.getLogger(__name__)


def _on_sigterm(_signum: int, _frame: object) -> None:
    logger.info("Received SIGTERM — shutting down")
    sys.exit(0)


def _run_server(settings: Settings) -> None:
    validate_server_startup(settings)
    setup_logging(settings.log_level)
    signal.signal(signal.SIGTERM, _on_sigterm)

    logger.info(
        "Starting Intelligence API on %s:%s",
        settings.server_host,
        settings.server_port,
    )
    uvicorn.run(
        "app.server:create_app",
        factory=True,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )


def _run_ingestion(settings: Settings) -> None:
    setup_logging(settings.log_level)
    logger.info("Starting ingestion job (engine=%s)", settings.ingest_engine)

    from ingestion.run import run as run_ingestion

    summary = run_ingestion(settings)
    logger.info("Ingestion job finished: %s", summary)


def run_for_mode(settings: Settings) -> None:
    """Start the process for the configured run mode — reject anything else."""
    match settings.run_mode:
        case RunMode.SERVER:
            _run_server(settings)
        case RunMode.INGEST:
            _run_ingestion(settings)
        case unknown:
            raise RuntimeError(
                StartupMessage.UNSUPPORTED_RUN_MODE.format(
                    mode=unknown,
                    allowed=", ".join(RunMode.values()),
                )
            )


def main() -> None:
    try:
        run_for_mode(get_settings())
    except Exception:
        logging.basicConfig(level=logging.ERROR)
        logger.exception("Failed to start soundbox-lakehouse")
        sys.exit(1)


if __name__ == "__main__":
    main()
