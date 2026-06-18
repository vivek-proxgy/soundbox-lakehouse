"""Batch job: soundbox Postgres → local parquet → GCS Iceberg."""

from __future__ import annotations

from typing import Any

from app.config.settings import Settings, get_settings
from app.ingestion.iceberg_writer import sync_table
from app.ingestion.parquet_writer import write_snapshot
from app.ingestion.postgres_reader import export_all_tables


def run(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    cfg.require_database()

    print(
        f"[lakehouse] Starting ingest mode={cfg.ingest_mode} "
        f"warehouse={cfg.warehouse_uri or '(local only)'}"
    )

    frames = export_all_tables(cfg)
    counts: dict[str, int] = {}
    gcs_results: dict[str, Any] = {}

    for table, df in frames.items():
        counts[table] = len(df)
        local_path = None

        if cfg.write_local_parquet:
            local_path = write_snapshot(table, df, cfg.lakehouse_local_root)

        if cfg.upload_to_gcs and cfg.warehouse_uri and not df.empty:
            gcs_results[table] = sync_table(
                table,
                df,
                local_path,
                cfg,
            )

    if counts.get("merchants", 0) == 0 and cfg.ingest_mode == "full":
        raise RuntimeError(
            "No merchants exported. Check DATABASE_* env vars match soundbox-backend."
        )

    summary = {
        "counts": counts,
        "gcs": gcs_results,
        "mode": cfg.ingest_mode,
        "warehouse": cfg.warehouse_uri,
    }
    print("[lakehouse] Ingest complete:", summary)
    return summary


if __name__ == "__main__":
    run()
