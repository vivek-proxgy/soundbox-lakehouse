"""AI Service using Google Gemini to query DuckDB parquet tables and synthesize answers."""

from __future__ import annotations

import json
import os
import re
from typing import Any

try:
    import google.generativeai as genai
    HAS_GEMINI_SDK = True
except ImportError:
    genai = None
    HAS_GEMINI_SDK = False

from app.config.settings import Settings, get_settings
from app.core.enums.error_key import ErrorKey
from app.core.http_errors import service_unavailable
from app.core.messages.error_messages import ErrorMessage
from app.core.sql_security import sanitize_sql
from app.services.duckdb_service import DuckDBService


class AIService:
    """Uses Google Gemini to write SQL queries against DuckDB and synthesize text insights."""

    def __init__(self, settings: Settings | None = None, duckdb_service: DuckDBService | None = None):
        self.settings = settings or get_settings()
        self.duckdb_service = duckdb_service or DuckDBService(self.settings)

        api_key = (
            self.settings.gemini_api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if api_key and HAS_GEMINI_SDK and genai is not None:
            genai.configure(api_key=api_key)
            self.model_name = "gemini-2.5-flash"
        else:
            self.model_name = None

    def is_configured(self) -> bool:
        return self.model_name is not None

    def _get_schema_prompt(self) -> str:
        """Provide detailed schema context of the tables in DuckDB."""
        return """
You are a database copilot translating natural language questions into DuckDB-compliant SQL.
The database has three tables:

1. `merchants` - List of active merchants.
   Columns:
   - `id` (VARCHAR) - Unique identifier of the merchant.
   - `organization_id` (VARCHAR) - Group organization of the merchant.
   - `name` (VARCHAR) - Merchant business name (decrypted).
   - `email` (VARCHAR) - Email.
   - `phone` (VARCHAR) - Contact phone.
   - `branch_id` (VARCHAR)
   - `address` (VARCHAR)
   - `state` (VARCHAR)
   - `city` (VARCHAR)
   - `pincode` (VARCHAR)
   - `payment_interface_type` (VARCHAR)
   - `mid` (VARCHAR) - Merchant ID.
   - `vpa` (VARCHAR) - VPA address.
   - `language` (VARCHAR)
   - `created_at` (TIMESTAMP)
   - `updated_at` (TIMESTAMP)
   - `device_id` (VARCHAR) - Device ID linked to merchant.
   - `merchant_activity_status` (VARCHAR)
   - `merchant_activated_at` (TIMESTAMP)
   - `head_office_id` (VARCHAR) - Taxonomy scope for head office.
   - `zone_office_id` (VARCHAR) - Taxonomy scope for zone office.
   - `regional_office_id` (VARCHAR) - Taxonomy scope for regional office.
   - `branch_office_id` (VARCHAR) - Taxonomy scope for branch office.

2. `transactions` - List of financial transactions.
   Columns:
   - `id` (VARCHAR) - Unique identifier of transaction.
   - `merchant_id` (VARCHAR) - Foreign key referencing merchants(id).
   - `organization_id` (VARCHAR)
   - `device_id` (VARCHAR)
   - `command_id` (VARCHAR)
   - `amount` (DOUBLE) - Financial value.
   - `latency` (DOUBLE) - Latency in seconds.
   - `name` (VARCHAR)
   - `branch` (VARCHAR)
   - `region` (VARCHAR)
   - `zone` (VARCHAR)
   - `branch_taxonomy_id` (VARCHAR)
   - `state` (VARCHAR)
   - `city` (VARCHAR)
   - `pincode` (VARCHAR)
   - `vpa` (VARCHAR)
   - `language` (VARCHAR)
   - `created_at` (TIMESTAMP)
   - `updated_at` (TIMESTAMP)

3. `device_telemetry` - Log of device status signals (heartbeats).
   Columns:
   - `id` (VARCHAR)
   - `organization_id` (VARCHAR)
   - `device_id` (VARCHAR) - Foreign key linking to merchant device.
   - `event_type` (VARCHAR)
   - `firmware_version` (VARCHAR)
   - `imei` (VARCHAR)
   - `sim_number` (VARCHAR)
   - `signal_strength` (BIGINT)
   - `battery_voltage` (BIGINT)
   - `network_type` (VARCHAR)
   - `ota_status` (VARCHAR)
   - `core_ver` (VARCHAR)
   - `charger` (BOOLEAN)
   - `volume` (BIGINT)
   - `language` (VARCHAR)
   - `created_at` (TIMESTAMP)
   - `updated_at` (TIMESTAMP)

Instructions:
1. Translate the user's natural language request into a valid, single DuckDB SQL query.
2. Return ONLY a JSON object with the key "sql" containing the query.
   Example response format:
   {
      "sql": "SELECT count(*) FROM merchants"
   }
3. Do not include markdown code block formatting (like ```json) in your raw response. Just return the JSON object.
"""

    def generate_sql(self, user_prompt: str, access_scope=None) -> str:
        """Translate a user prompt into a DuckDB SQL query using Gemini."""
        if not self.model_name:
            raise service_unavailable(ErrorKey.CONFIG, ErrorMessage.GEMINI_NOT_CONFIGURED.value)

        scope_hint = ""
        if access_scope is not None:
            scope_hint = (
                f"\nMandatory data scope: organization_id = '{access_scope.organization_id}'. "
                "Every query MUST filter by this organization_id while querying"
            )
            if access_scope.hierarchy_filter:
                scope_hint += (
                    f" Also filter merchants.{access_scope.hierarchy_filter.column} = "
                    f"'{access_scope.hierarchy_filter.taxonomy_id}' and scope transactions/telemetry to those merchants."
                )

        system_prompt = self._get_schema_prompt() + scope_hint
        model = genai.GenerativeModel(
            self.model_name,
            system_instruction=system_prompt
        )

        response = model.generate_content(
            f"Question: {user_prompt}\nTranslate to SQL JSON:",
            generation_config={"response_mime_type": "application/json"}
        )

        try:
            # Clean up potential markdown formatting if returned
            text = response.text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            
            data = json.loads(text)
            return data["sql"]
        except Exception as e:
            raise ValueError(f"AI returned invalid SQL JSON response: {response.text}. Error: {e}")

    def query_with_ai(self, user_prompt: str, access_scope=None) -> dict[str, Any]:
        """Convert natural language to SQL, run the query, and return results + synthesis."""
        from app.services.copilot.access_scope import apply_scope_to_dynamic_sql

        sql = self.generate_sql(user_prompt, access_scope=access_scope)
        safe_sql = sanitize_sql(sql)
        safe_sql = apply_scope_to_dynamic_sql(safe_sql, access_scope)

        df = self.duckdb_service.query_to_df(safe_sql)
        records = df.to_dict(orient="records")
        if not self.model_name:
            return {
                "sql": safe_sql,
                "data": records,
                "answer": "Results fetched successfully (Text synthesis requires Gemini API key).",
            }

        synthesis_prompt = f"""
You are an expert analyst. Answer the user's question by reviewing the database query results.
User Question: "{user_prompt}"
Executed SQL: "{safe_sql}"
Query Results (JSON):
{json.dumps(records, indent=2, default=str)}

Provide a concise, direct, professional answer summarizing the findings. Do not show raw JSON in the answer unless requested.
"""
        model = genai.GenerativeModel(self.model_name)
        synthesis_response = model.generate_content(synthesis_prompt)

        return {
            "sql": safe_sql,
            "data": records,
            "answer": synthesis_response.text.strip(),
        }
