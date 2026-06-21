"""DuckDB data retrieval tools for Soundbox Copilot context with caching and concurrency."""

from __future__ import annotations

import re
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, NamedTuple, Optional
import pandas as pd

from app.core.sql_security import sanitize_org_id
from app.services.duckdb_service import DuckDBService
from app.services.copilot.forecaster import forecast_next_days


# =====================================================================
# TTL LRU Query Cache Implementation
# =====================================================================

class CacheEntry(NamedTuple):
    value: pd.DataFrame
    expiry: float


class QueryCache:
    """Simple in-memory query cache with TTL expiration."""

    def __init__(self, ttl_seconds: float = 300, max_size: int = 128):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self.cache = OrderedDict()

    def get(self, key: str) -> pd.DataFrame | None:
        if key not in self.cache:
            return None
        entry = self.cache[key]
        if time.time() > entry.expiry:
            del self.cache[key]
            return None
        # Move to end (LRU behavior)
        self.cache.move_to_end(key)
        return entry.value

    def set(self, key: str, value: pd.DataFrame) -> None:
        if key in self.cache:
            del self.cache[key]
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)  # Evict oldest
        self.cache[key] = CacheEntry(value=value.copy(), expiry=time.time() + self.ttl)

    def clear(self) -> None:
        self.cache.clear()


# Global query cache instance
GLOBAL_QUERY_CACHE = QueryCache(ttl_seconds=300)


def cached_query_to_df(duckdb_service: DuckDBService, sql: str) -> pd.DataFrame:
    """Fetch from cache or execute query against DuckDB, caching the result."""
    cache_key = sql.strip()
    cached = GLOBAL_QUERY_CACHE.get(cache_key)
    if cached is not None:
        return cached.copy()
    
    df = duckdb_service.query_to_df(sql)
    GLOBAL_QUERY_CACHE.set(cache_key, df)
    return df


# =====================================================================
# Scoping & Database Tools
# =====================================================================

def apply_org_filter(where_clause: str, org_id: Optional[str]) -> str:
    """Safely append organization ID filter to SQL query conditions."""
    if not org_id or org_id.lower() in ("all", "null", "undefined", ""):
        return where_clause
    prefix = "AND" if where_clause.strip() else "WHERE"
    clean_org = sanitize_org_id(org_id)
    if not clean_org:
        return where_clause
    return f"{where_clause} {prefix} organization_id = '{clean_org}'"


def get_daily_brief_context(duckdb_service: DuckDBService, org_id: Optional[str] = None) -> Dict[str, Any]:
    """Fetch high-level portfolio summary metrics from database views concurrently."""
    try:
        m_where = apply_org_filter("", org_id)
        m_sql = f"SELECT count(*) as total_merchants, count(CASE WHEN merchant_activity_status = 'active' THEN 1 END) as active_count FROM merchants {m_where}"
        
        t_where = apply_org_filter("", org_id)
        t_sql = f"SELECT count(*) as total_tx, COALESCE(sum(amount), 0.0) as total_gmv, COALESCE(avg(latency), 0.0) as avg_latency FROM transactions {t_where}"
        
        tele_where = apply_org_filter("", org_id)
        tele_sql = f"SELECT COALESCE(avg(signal_strength), 0.0) as avg_signal, count(CASE WHEN battery_voltage < 3500 THEN 1 END) as low_battery_count FROM device_telemetry {tele_where}"

        # Execute the queries in parallel to minimize latency
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_m = executor.submit(cached_query_to_df, duckdb_service, m_sql)
            future_t = executor.submit(cached_query_to_df, duckdb_service, t_sql)
            future_tele = executor.submit(cached_query_to_df, duckdb_service, tele_sql)
            
            m_df = future_m.result()
            t_df = future_t.result()
            tele_df = future_tele.result()

        sql_trace = f"-- Merchants query:\n{m_sql};\n\n-- Transactions query:\n{t_sql};\n\n-- Telemetry query:\n{tele_sql};"

        return {
            "total_merchants": int(m_df["total_merchants"].iloc[0]) if not m_df.empty else 0,
            "active_merchants": int(m_df["active_count"].iloc[0]) if not m_df.empty else 0,
            "total_transactions": int(t_df["total_tx"].iloc[0]) if not t_df.empty else 0,
            "total_gmv": float(t_df["total_gmv"].iloc[0]) if not t_df.empty else 0.0,
            "average_latency_seconds": float(t_df["avg_latency"].iloc[0]) if not t_df.empty else 0.0,
            "average_signal_strength": float(tele_df["avg_signal"].iloc[0]) if not tele_df.empty else 0.0,
            "low_battery_devices": int(tele_df["low_battery_count"].iloc[0]) if not tele_df.empty else 0,
            "sql_query": sql_trace,
        }
    except Exception as e:
        print(f"[copilot-tools] Daily brief retrieval failed: {e}")
        return {"sql_query": ""}


def get_merchant_profile_context(
    duckdb_service: DuckDBService,
    search_term: str,
    org_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Lookup specific merchant profiles by matching ID or name with pagination."""
    try:
        clean_term = re.sub(r"[^a-zA-Z0-9\s\-_]", "", search_term).strip()
        if not clean_term:
            return {"search_results": [], "sql_query": "", "total_count": 0}
        
        where = f"WHERE id = '{clean_term}' OR name ILIKE '%{clean_term}%'"
        where = apply_org_filter(where, org_id)
        
        # Run parallel or sequential count
        count_sql = f"SELECT count(*) as total_count FROM merchants {where}"
        count_df = cached_query_to_df(duckdb_service, count_sql)
        total_count = int(count_df["total_count"].iloc[0]) if not count_df.empty else 0
        
        sql = f"SELECT id, name, email, phone, state, city, merchant_activity_status, device_id FROM merchants {where} LIMIT {limit} OFFSET {offset}"
        df = cached_query_to_df(duckdb_service, sql)
        records = df.to_dict(orient="records")
        
        return {
            "search_results": records,
            "sql_query": sql,
            "total_count": total_count
        }
    except Exception as e:
        print(f"[copilot-tools] Merchant profile lookup failed: {e}")
        return {"search_results": [], "sql_query": "", "total_count": 0}


def get_merchant_risk_context(
    duckdb_service: DuckDBService,
    search_term: str,
    org_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Gather transaction profile and newest telemetry metrics for a given merchant concurrently."""
    profile_res = get_merchant_profile_context(duckdb_service, search_term, org_id)
    profiles = profile_res.get("search_results", [])
    if not profiles:
        return {"sql_query": profile_res.get("sql_query", "")}
    
    profile = profiles[0]
    m_id = profile["id"]
    
    try:
        t_sql = f"SELECT count(*) as tx_count, COALESCE(sum(amount), 0.0) as gmv, COALESCE(avg(latency), 0.0) as avg_latency FROM transactions WHERE merchant_id = '{m_id}'"
        tele_sql = f"SELECT event_type, firmware_version, battery_voltage, signal_strength, charger FROM device_telemetry WHERE device_id = '{profile['device_id']}' ORDER BY updated_at DESC LIMIT 1"
        
        # Execute secondary queries concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_t = executor.submit(cached_query_to_df, duckdb_service, t_sql)
            future_tele = executor.submit(cached_query_to_df, duckdb_service, tele_sql)
            
            t_df = future_t.result()
            tele_df = future_tele.result()

        sql_trace = f"{profile_res.get('sql_query', '')}\n\n-- Transactions summary:\n{t_sql};\n\n-- Latest telemetry:\n{tele_sql};"

        return {
            "profile": profile,
            "transaction_metrics": t_df.to_dict(orient="records")[0] if not t_df.empty else {},
            "latest_telemetry": tele_df.to_dict(orient="records")[0] if not tele_df.empty else {},
            "sql_query": sql_trace,
        }
    except Exception as e:
        print(f"[copilot-tools] Merchant risk diagnostics lookup failed: {e}")
        return {"profile": profile, "sql_query": profile_res.get("sql_query", "")}


def get_fleet_health_context(duckdb_service: DuckDBService, org_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve operational telemetry summaries for warning bands."""
    try:
        where = apply_org_filter("", org_id)
        sql = f"""
            SELECT 
                count(*) as total_devices,
                count(CASE WHEN battery_voltage < 3500 THEN 1 END) as critical_battery,
                count(CASE WHEN battery_voltage >= 3500 AND battery_voltage < 3700 THEN 1 END) as warning_battery,
                count(CASE WHEN signal_strength < 10 THEN 1 END) as critical_signal,
                count(CASE WHEN charger = true THEN 1 END) as charging_count
            FROM device_telemetry
            {where}
        """
        df = cached_query_to_df(duckdb_service, sql)
        res = df.to_dict(orient="records")[0] if not df.empty else {}
        res["sql_query"] = sql
        return res
    except Exception as e:
        print(f"[copilot-tools] Fleet health diagnostics lookup failed: {e}")
        return {"sql_query": ""}


def get_gmv_trend_context(
    duckdb_service: DuckDBService,
    org_id: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Compute trend projections and historical daily sums with pagination."""
    try:
        where = apply_org_filter("", org_id)
        date_col = "created_at::date"
        prefix = "AND" if "WHERE" in where else "WHERE"
        
        # Count total matching distinct days
        count_sql = f"""
            SELECT count(distinct {date_col}) as total_count
            FROM transactions
            {where} {prefix} {date_col} >= CURRENT_DATE - INTERVAL '{days} days'
        """
        count_df = cached_query_to_df(duckdb_service, count_sql)
        total_count = int(count_df["total_count"].iloc[0]) if not count_df.empty else 0
        
        sql = f"""
            SELECT {date_col} as date, COALESCE(sum(amount), 0.0) as gmv, count(*) as tx_count
            FROM transactions
            {where} {prefix} {date_col} >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY date
            ORDER BY date ASC
            LIMIT {limit} OFFSET {offset}
        """
        df = cached_query_to_df(duckdb_service, sql)
        
        forecast = []
        if not df.empty and len(df) >= 2:
            forecast = forecast_next_days(df, target_days=7)
            
        return {
            "historical_daily_gmv": df.to_dict(orient="records"),
            "seven_day_forecast": forecast,
            "sql_query": sql,
            "total_count": total_count,
        }
    except Exception as e:
        print(f"[copilot-tools] Trend analysis query failed: {e}")
        return {"sql_query": "", "total_count": 0}
