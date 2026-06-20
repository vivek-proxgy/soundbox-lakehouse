"""DuckDB service for querying Iceberg/Parquet datasets with automatic deduplication."""

from __future__ import annotations

from pathlib import Path
import duckdb

from app.config.settings import Settings, get_settings


class DuckDBService:
    """Service to connect and run queries using DuckDB against Parquet files."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Create a DuckDB connection and register deduplicated views for tables."""
        conn = duckdb.connect()
        conn.execute(f"PRAGMA threads={max(1, self.settings.duckdb_threads)}")

        use_gcs = self.settings.warehouse_uri.startswith("gs://") and self.settings.upload_to_gcs

        if use_gcs:
            try:
                conn.execute("INSTALL httpfs;")
                conn.execute("LOAD httpfs;")
                conn.execute(f"SET gcs_region='{self.settings.gcp_region}';")
            except Exception as e:
                print(f"[duckdb-service] Warning: Failed to load httpfs extension: {e}")

        tables = ["merchants", "transactions", "device_telemetry"]

        for table in tables:
            dir_name = "device_telemetry" if table == "device_telemetry" else table
            
            if use_gcs:
                bucket = self.settings.gcs_bucket or self.settings.warehouse_uri.removeprefix("gs://").split("/")[0]
                prefix = self.settings.iceberg_namespace
                path = f"gs://{bucket}/{prefix}/{dir_name}/data/**/*.parquet"
            else:
                path = f"{self.settings.lakehouse_local_root}/{dir_name}/**/*.parquet"

            # Deduplication view: partition by id, order by updated_at DESC, take row_number = 1
            view_sql = f"""
                CREATE OR REPLACE VIEW {table} AS
                SELECT * EXCLUDE (_rn) FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY id ORDER BY updated_at DESC) as _rn
                    FROM read_parquet('{path}')
                ) WHERE _rn = 1
            """

            try:
                # Check files exist local or if GCS is targeted
                has_files = True
                if not use_gcs:
                    local_root = Path(self.settings.lakehouse_local_root)
                    has_files = any(local_root.glob(f"{dir_name}/**/*.parquet"))

                if has_files:
                    conn.execute(view_sql)
                    print(f"[duckdb-service] Registered deduplicated view '{table}' -> {path}")
                else:
                    print(f"[duckdb-service] No local parquet files found for '{table}' under local root. View registration skipped.")
            except Exception as e:
                print(f"[duckdb-service] Failed to register view for {table}: {e}")

        return conn

    def query(self, sql: str) -> list[tuple]:
        """Execute SQL query and return raw list of tuples."""
        conn = self.get_connection()
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def query_to_df(self, sql: str):
        """Execute SQL query and return a pandas DataFrame."""
        conn = self.get_connection()
        try:
            return conn.execute(sql).df()
        finally:
            conn.close()
