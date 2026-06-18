"""SQL for soundbox-backend tables — aligned with soundbox-chanakya postgres_exporter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TableExportSpec:
    name: str
    sql: str
    watermark_column: str | None = None
    decrypt_columns: tuple[str, ...] = ()


MERCHANTS_SPEC = TableExportSpec(
    name="merchants",
    sql="""
SELECT
    m.id::text AS id,
    m.organization_id::text AS organization_id,
    m.name,
    m.email,
    m.phone,
    m.branch_id,
    m.address,
    m.state,
    m.city,
    m.pincode,
    m.payment_interface_type::text AS payment_interface_type,
    m.mid,
    m.vpa,
    m.language::text AS language,
    m.created_at,
    m.updated_at,
    m.awb_number,
    m.partner_name,
    m.package_status::text AS package_status,
    m.vendor_name::text AS vendor_name,
    m.package_update_at,
    m.device_id::text AS device_id,
    m.merchant_activity_status::text AS merchant_activity_status,
    m.merchant_activated_at
FROM merchants m
WHERE m.deleted_at IS NULL
  AND m.role::text = 'merchant'
""",
    watermark_column="created_at",
    decrypt_columns=("name", "email", "phone", "address"),
)

TRANSACTIONS_SPEC = TableExportSpec(
    name="transactions",
    sql="""
SELECT
    tx._id::text AS id,
    tx.merchant_id::text AS merchant_id,
    tx.organization_id::text AS organization_id,
    tx.device_id::text AS device_id,
    tx."commandId" AS command_id,
    tx.amount::double precision AS amount,
    EXTRACT(EPOCH FROM tx.latency)::double precision AS latency,
    tx.name,
    tx.branch,
    tx.region,
    tx.zone,
    tx.branch_taxonomy_id::text AS branch_taxonomy_id,
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
    watermark_column="created_at",
    decrypt_columns=("name",),
)

TELEMETRY_SPEC = TableExportSpec(
    name="device_telemetry",
    sql="""
SELECT
    h.id::text AS id,
    h.organization_id::text AS organization_id,
    h.device_id::text AS device_id,
    h.event_type::text AS event_type,
    h.firmware_version,
    h.imei,
    h.sim_number,
    h.signal_strength,
    h.battery_voltage,
    h.network_type,
    h.ota_status,
    h.core_ver,
    h.charger,
    h.volume,
    h.language,
    h.language_version,
    h.created_at,
    h.updated_at
FROM heartbeats h
WHERE h.deleted_at IS NULL
""",
    watermark_column="created_at",
)

EXPORT_TABLES: tuple[TableExportSpec, ...] = (
    MERCHANTS_SPEC,
    TRANSACTIONS_SPEC,
    TELEMETRY_SPEC,
)

