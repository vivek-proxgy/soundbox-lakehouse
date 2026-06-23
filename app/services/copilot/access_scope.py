"""Access scope for org + hierarchy filtering — supplied by on-prem-soundbox-backend."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.sql_security import sanitize_org_id

HierarchyColumn = Literal[
    "head_office_id",
    "zone_office_id",
    "regional_office_id",
    "branch_office_id",
]

_VALID_HIERARCHY_COLUMNS = frozenset(HierarchyColumn.__args__)  # type: ignore[attr-defined]

_WHERE_PATTERN = re.compile(r"\bWHERE\b", re.IGNORECASE)
_SQL_AND = " AND "
_SQL_WHERE = "WHERE "


class HierarchyScopeFilter(BaseModel):
    column: HierarchyColumn
    taxonomy_id: str = Field(..., max_length=64)


class AccessScope(BaseModel):
    """Resolved caller context — backend is authoritative; lakehouse applies SQL filters only."""

    organization_id: str = Field(..., max_length=64)
    roles: list[str] = Field(default_factory=list)
    can_view_pii: bool = False
    hierarchy_enabled: bool = False
    hierarchy_filter: HierarchyScopeFilter | None = None


def _safe_id(value: str | None) -> str | None:
    if not value:
        return None
    return sanitize_org_id(value.strip())


def _merchant_conditions(scope: AccessScope | None, alias: str = "") -> list[str]:
    if scope is None:
        return []
    prefix = f"{alias}." if alias else ""
    conditions: list[str] = []
    org_id = _safe_id(scope.organization_id)
    if org_id:
        conditions.append(f"{prefix}organization_id = '{org_id}'")
    if scope.hierarchy_filter:
        column = scope.hierarchy_filter.column
        if column not in _VALID_HIERARCHY_COLUMNS:
            return conditions
        taxonomy_id = _safe_id(scope.hierarchy_filter.taxonomy_id)
        if taxonomy_id:
            conditions.append(f"{prefix}{column} = '{taxonomy_id}'")
    return conditions


def _merge_where_clause(where_clause: str, joined: str) -> str:
    if where_clause.strip():
        if _WHERE_PATTERN.search(where_clause):
            return f"{where_clause}{_SQL_AND}{joined}"
        return f"{where_clause} {_SQL_WHERE}{joined}"
    return f"{_SQL_WHERE}{joined}"


def merchant_scope_where(scope: AccessScope | None, alias: str = "") -> str:
    conditions = _merchant_conditions(scope, alias)
    if not conditions:
        return ""
    return f"{_SQL_WHERE}{_SQL_AND.join(conditions)}"


def append_merchant_scope(where_clause: str, scope: AccessScope | None, alias: str = "") -> str:
    conditions = _merchant_conditions(scope, alias)
    if not conditions:
        return where_clause
    return _merge_where_clause(where_clause, _SQL_AND.join(conditions))


def scoped_merchant_id_subquery(scope: AccessScope | None) -> str:
    inner = merchant_scope_where(scope)
    if inner:
        return f"(SELECT id FROM merchants {inner})"
    return "(SELECT id FROM merchants WHERE 1 = 0)"


def scoped_device_id_subquery(scope: AccessScope | None) -> str:
    where = append_merchant_scope("WHERE device_id IS NOT NULL", scope)
    return f"(SELECT device_id FROM merchants {where})"


def append_transaction_scope(where_clause: str, scope: AccessScope | None) -> str:
    clause = f"merchant_id IN {scoped_merchant_id_subquery(scope)}"
    return _merge_where_clause(where_clause, clause)


def append_telemetry_scope(where_clause: str, scope: AccessScope | None) -> str:
    org_id = _safe_id(scope.organization_id) if scope else None
    conditions: list[str] = []
    if org_id:
        conditions.append(f"organization_id = '{org_id}'")
    device_subq = scoped_device_id_subquery(scope)
    conditions.append(f"device_id IN {device_subq}")
    return _merge_where_clause(where_clause, _SQL_AND.join(conditions))


def apply_scope_to_dynamic_sql(sql: str, scope: AccessScope | None) -> str:
    """Best-effort scope injection for NL-generated SQL."""
    if not scope:
        return sql
    clean = sql.strip().rstrip(";")
    upper = clean.upper()
    if re.search(r"\bFROM\s+MERCHANTS\b", upper):
        return append_merchant_scope(clean, scope)
    if re.search(r"\bFROM\s+TRANSACTIONS\b", upper):
        return append_transaction_scope(clean, scope)
    if re.search(r"\bFROM\s+DEVICE_TELEMETRY\b", upper):
        return append_telemetry_scope(clean, scope)
    return clean


def scope_from_org_id(org_id: Optional[str]) -> AccessScope | None:
    if not org_id or org_id.lower() in ("all", "null", "undefined", ""):
        return None
    safe_org = _safe_id(org_id)
    if not safe_org:
        return None
    return AccessScope(organization_id=safe_org)


def coerce_access_scope(value: AccessScope | object | None) -> AccessScope | None:
    """Accept runtime or API schema access scope objects."""
    if value is None:
        return None
    if isinstance(value, AccessScope):
        return value
    if hasattr(value, "model_dump"):
        return AccessScope(**value.model_dump())
    return None
