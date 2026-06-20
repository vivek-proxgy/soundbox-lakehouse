"""Transactions table query specification."""

from __future__ import annotations

from ingestion.queries.base import TableExportSpec

TRANSACTIONS_SPEC = TableExportSpec(
    name="transactions",
    sql="""
SELECT
    tx._id,
    tx.merchant_id,
    tx.organization_id,
    tx.device_id,
    tx."commandId",
    tx.amount,
    EXTRACT(EPOCH FROM tx.latency) AS latency,
    tx.name,
    tx.branch,
    tx.region,
    tx.zone,
    tx.branch_taxonomy_id,
    tx.state,
    tx.city,
    tx.pincode,
    tx.vpa,
    tx.language,
    tx.created_at,
    tx.updated_at
FROM transactions tx
WHERE tx.deleted_at IS NULL
  AND tx.merchant_id IS NOT NULL
""",
    watermark_column="updated_at",
    decrypt_columns=("name",),
    column_mapping={
        "_id": "id",
        "commandId": "command_id",
    },
    column_types={
        "id": "string",
        "merchant_id": "string",
        "organization_id": "string",
        "device_id": "string",
        "branch_taxonomy_id": "string",
        "amount": "double",
        "latency": "double",
    },
)
