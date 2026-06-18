"""PySpark ingestion: Postgres JDBC → Iceberg on GCS (billions of rows)."""

from __future__ import annotations

from typing import Any

from app.config.settings import Settings, get_settings
from app.ingestion.queries import EXPORT_TABLES
from app.ingestion.watermark_store import write_watermark
from app.spark.decrypt import maybe_decrypt_columns
from app.spark.iceberg_sink import append_to_iceberg, write_local_parquet_snapshot
from app.spark.jdbc_reader import latest_watermark, read_table
from app.spark.session import create_spark_session, stop_spark


def run(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    cfg.require_database()
    cfg.require_gcs()

    print(
        f"[spark-ingest] mode={cfg.ingest_mode} warehouse={cfg.warehouse_uri} "
        f"partitions={cfg.spark_jdbc_num_partitions}"
    )

    spark = create_spark_session(cfg)
    counts: dict[str, int] = {}
    tables_written: list[str] = []

    try:
        for spec in EXPORT_TABLES:
            df = read_table(spark, spec, cfg)

            if cfg.spark_decrypt_pii:
                df = maybe_decrypt_columns(df, spec)

            row_count = append_to_iceberg(df, spec.name, cfg)
            counts[spec.name] = row_count

            if row_count > 0:
                tables_written.append(spec.name)
                if spec.watermark_column and cfg.ingest_mode == "incremental":
                    latest = latest_watermark(df, spec.watermark_column)
                    if latest is not None:
                        write_watermark(spec.name, latest, cfg)

                write_local_parquet_snapshot(df, spec.name, cfg)

        if counts.get("merchants", 0) == 0 and cfg.ingest_mode == "full":
            raise RuntimeError("No merchants exported — check DATABASE_* and JDBC connectivity")

    finally:
        stop_spark(spark)

    summary = {
        "engine": "spark",
        "counts": counts,
        "tables": tables_written,
        "warehouse": cfg.warehouse_uri,
        "mode": cfg.ingest_mode,
    }
    print("[spark-ingest] complete:", summary)
    return summary


if __name__ == "__main__":
    run()
