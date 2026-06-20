"""Device telemetry table query specification."""

from __future__ import annotations

from ingestion.queries.base import TableExportSpec

TELEMETRY_SPEC = TableExportSpec(
    name="device_telemetry",
    sql="""
SELECT
    h.id,
    h.organization_id,
    h.device_id,
    h.event_type,
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
    watermark_column="updated_at",
    column_types={
        "id": "string",
        "organization_id": "string",
        "device_id": "string",
        "event_type": "string",
    },
)
