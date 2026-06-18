"""Query Iceberg Parquet tables on GCS directly using DuckDB."""

from __future__ import annotations

import duckdb
from app.config.settings import get_settings
from app.utils.data_access import get_duckdb_connection


def query_gcs_transactions() -> list[tuple[str, float]]:
    """Query top 10 merchants by GMV directly from Iceberg Parquet files on GCS."""
    settings = get_settings()
    settings.require_gcs()

    bucket = settings.gcs_bucket
    namespace = settings.iceberg_namespace
    gcs_glob = f"gs://{bucket}/{namespace}/transactions/data/**/*.parquet"
    
    conn = get_duckdb_connection()
    try:
        # Load GCS connectivity extension
        conn.execute("INSTALL httpfs;")
        conn.execute("LOAD httpfs;")
        conn.execute(f"SET gcs_region='{settings.gcp_region}';")
        
        query = f"""
            SELECT 
                merchant_id, 
                round(sum(amount), 2) AS total_gmv 
            FROM read_parquet('{gcs_glob}')
            GROUP BY merchant_id
            ORDER BY total_gmv DESC
            LIMIT 10;
        """
        results: list[tuple[str, float]] = conn.execute(query).fetchall()
        return results
    finally:
        conn.close()


def main() -> None:
    print("[duckdb-gcs] Querying raw_transactions on GCS...")
    try:
        results = query_gcs_transactions()
        print("[duckdb-gcs] Top merchants by GMV:")
        for merchant, gmv in results:
            print(f"  Merchant: {merchant} | GMV: {gmv}")
    except Exception as exc:
        print(f"[duckdb-gcs] Query failed: {exc}")
        print("[duckdb-gcs] Ensure you have GCP Application Default Credentials configured.")


if __name__ == "__main__":
    main()
