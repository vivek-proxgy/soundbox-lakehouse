"""Write parquet snapshots to local staging path."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config.settings import get_settings


def write_snapshot(table: str, df: pd.DataFrame, root: str | None = None) -> Path | None:
    if df.empty:
        print(f"[parquet] Skip empty table {table}")
        return None

    base = Path(root or get_settings().lakehouse_local_root)
    dest_dir = base / table
    dest_dir.mkdir(parents=True, exist_ok=True)

    for existing in dest_dir.glob("*.parquet"):
        existing.unlink()

    output = dest_dir / f"{table}_snapshot.parquet"
    df.to_parquet(output, index=False, engine="pyarrow")
    print(f"[parquet] Wrote {len(df):,} rows -> {output}")
    return output
