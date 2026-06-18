"""Optional PII decryption as Spark column transforms."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from app.ingestion.queries import TableExportSpec
from app.utils.decryption import decrypt_field

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def _decrypt_udf():
    return F.udf(decrypt_field, StringType())


def maybe_decrypt_columns(df: DataFrame, spec: TableExportSpec) -> DataFrame:
    if not spec.decrypt_columns:
        return df
    decrypt = _decrypt_udf()
    for column in spec.decrypt_columns:
        if column in df.columns:
            df = df.withColumn(column, decrypt(F.col(column)))
    return df
