"""Merchants table query specification."""

from __future__ import annotations

from ingestion.queries.base import TableExportSpec

MERCHANTS_SPEC = TableExportSpec(
    name="merchants",
    sql="""
SELECT
    m.id,
    m.organization_id,
    m.name,
    m.email,
    m.phone,
    m.branch_id,
    m.address,
    m.state,
    m.city,
    m.pincode,
    m.payment_interface_type,
    m.mid,
    m.vpa,
    m.language,
    m.created_at,
    m.updated_at,
    m.awb_number,
    m.partner_name,
    m.package_status,
    m.vendor_name,
    m.package_update_at,
    m.device_id,
    m.merchant_activity_status,
    m.merchant_activated_at
FROM merchants m
WHERE m.deleted_at IS NULL
  AND m.role::text = 'merchant'
""",
    watermark_column="updated_at",
    decrypt_columns=("name", "email", "phone", "address"),
    column_types={
        "id": "string",
        "organization_id": "string",
        "payment_interface_type": "string",
        "language": "string",
        "package_status": "string",
        "vendor_name": "string",
        "device_id": "string",
        "merchant_activity_status": "string",
    },
)
