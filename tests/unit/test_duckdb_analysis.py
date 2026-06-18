"""DuckDB analysis path — same engine the AI service uses on parquet snapshots."""

from pathlib import Path

import pandas as pd

from app.utils.duckdb_client import query_parquet_glob


def test_duckdb_aggregate_on_parquet(tmp_path: Path):
    df = pd.DataFrame(
        {
            "merchant_id": ["m1", "m1", "m2"],
            "amount": [100.0, 50.0, 200.0],
        }
    )
    parquet_dir = tmp_path / "raw_transactions"
    parquet_dir.mkdir()
    df.to_parquet(parquet_dir / "part.parquet", index=False)

    sql = (
        "SELECT merchant_id, sum(amount) AS gmv FROM data GROUP BY merchant_id ORDER BY merchant_id"
    )
    rows = query_parquet_glob(str(parquet_dir / "*.parquet"), sql)
    assert rows == [("m1", 150.0), ("m2", 200.0)]
