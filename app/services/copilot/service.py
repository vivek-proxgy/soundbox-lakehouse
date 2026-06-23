"""Orchestrator service for Chanakya Copilot logic incorporating clean registry patterns, paging, and report exports."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from app.services.copilot.enums.intent import CopilotIntent
from app.core.sql_security import sanitize_sql as validate_readonly_sql

from app.config.settings import Settings, get_settings
from app.services.duckdb_service import DuckDBService
from app.services.ai_service import AIService
from app.services.copilot.intents import classify_intent
from app.services.copilot import tools
from app.services.copilot.templates import generate_template_fallback
from app.services.copilot.conversation_context import normalize_conversation_history
from app.services.copilot.providers import GeminiProvider
from app.services.copilot.access_scope import AccessScope, apply_scope_to_dynamic_sql, scope_from_org_id

# Optional ReportLab PDF imports
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class CopilotService:
    """Copilot service class coordinating intents, dynamic tools, pagination, and report generation."""

    def __init__(self, settings: Settings | None = None, duckdb_service: DuckDBService | None = None):
        self.settings = settings or get_settings()
        self.duckdb_service = duckdb_service or DuckDBService(self.settings)
        self.provider = GeminiProvider()
        self.ai_service = AIService(self.settings, self.duckdb_service)
        
        # Clean-code registry mapping intents to handlers
        self.intent_handlers = {
            CopilotIntent.DAILY_BRIEF: self._handle_daily_brief,
            CopilotIntent.MERCHANT_PROFILE: self._handle_merchant_profile,
            CopilotIntent.MERCHANT_RISK: self._handle_merchant_risk,
            CopilotIntent.FLEET_HEALTH: self._handle_fleet_health,
            CopilotIntent.GMV_TREND: self._handle_gmv_trend,
            CopilotIntent.UNKNOWN: self._handle_unknown,
        }

    def classify_intent(self, prompt: str) -> CopilotIntent:
        return classify_intent(prompt)

    def sanitize_sql(self, sql: str) -> None:
        """Enforce strict read-only execution by blocking write or destructive operations."""
        validate_readonly_sql(sql)

    def enforce_limit(self, sql: str, max_limit: int = 100) -> str:
        """Append a LIMIT constraint to dynamic queries if not already present."""
        clean = sql.strip().rstrip(';')
        if "LIMIT" not in clean.upper():
            return f"{clean} LIMIT {max_limit}"
        return sql

    def get_dynamic_count_sql(self, sql: str) -> str:
        """Wrap dynamic query to count the total records, stripping existing limit bounds."""
        clean_sql = re.sub(r"\bLIMIT\s+\d+(\s+OFFSET\s+\d+)?\b", "", sql, flags=re.IGNORECASE).strip().rstrip(';')
        return f"SELECT COUNT(*) as total_count FROM ({clean_sql}) AS subquery"

    # =====================================================================
    # Intent Handlers Registry Methods
    # =====================================================================

    def _handle_daily_brief(self, prompt: str, access_scope: AccessScope | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Fetch daily portfolio metrics summary."""
        context = tools.get_daily_brief_context(self.duckdb_service, access_scope=access_scope)
        return {
            "context": context,
            "sources": ["DuckDB: merchants", "DuckDB: transactions", "DuckDB: device_telemetry"],
            "sql_query": context.get("sql_query", ""),
            "data": [context],
            "merchant_references": [],
            "merchant_lookup": [],
            "suggestions": [
                "Show me fleet health anomalies",
                "Are there any high risk merchants today?",
                "What is our GMV forecast for next week?",
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_count": 1,
                "has_more": False
            }
        }

    def _handle_merchant_profile(self, prompt: str, access_scope: AccessScope | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Lookup merchant profiles matching name or ID with pagination."""
        profile_res = tools.get_merchant_profile_context(
            self.duckdb_service,
            prompt,
            access_scope=access_scope,
            limit=limit,
            offset=offset,
        )
        lookup_res = profile_res.get("search_results", [])
        total_count = profile_res.get("total_count", len(lookup_res))
        
        merchant_refs = [{"id": m["id"], "name": m["name"]} for m in lookup_res]
        suggestions = [
            f"Explain risk factors for merchant {lookup_res[0]['id']}" if lookup_res else "Search merchants in Bangalore",
            "Show overall portfolio summary",
        ]
        
        return {
            "context": {"search_results": lookup_res},
            "sources": ["DuckDB: merchants"],
            "sql_query": profile_res.get("sql_query", ""),
            "data": lookup_res,
            "merchant_references": merchant_refs,
            "merchant_lookup": lookup_res,
            "suggestions": suggestions,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_count": total_count,
                "has_more": (offset + limit) < total_count
            }
        }

    def _handle_merchant_risk(self, prompt: str, access_scope: AccessScope | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Evaluate operational risk and transaction health for a merchant."""
        risk_res = tools.get_merchant_risk_context(self.duckdb_service, prompt, access_scope=access_scope)
        
        merchant_refs = []
        if "profile" in risk_res:
            prof = risk_res["profile"]
            merchant_refs.append({"id": prof["id"], "name": prof["name"]})
            suggestions = [
                f"Show GMV trend for merchant {prof['id']}",
                "Trigger remote diagnostics on this merchant device",
            ]
        else:
            suggestions = ["Show high-risk merchants queue"]

        return {
            "context": risk_res,
            "sources": ["DuckDB: merchants", "DuckDB: transactions", "DuckDB: device_telemetry"],
            "sql_query": risk_res.get("sql_query", ""),
            "data": [risk_res],
            "merchant_references": merchant_refs,
            "merchant_lookup": [],
            "suggestions": suggestions,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_count": 1,
                "has_more": False
            }
        }

    def _handle_fleet_health(self, prompt: str, access_scope: AccessScope | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Review hardware issues and telemetry warning states."""
        context = tools.get_fleet_health_context(self.duckdb_service, access_scope=access_scope)
        return {
            "context": context,
            "sources": ["DuckDB: device_telemetry"],
            "sql_query": context.get("sql_query", ""),
            "data": [context],
            "merchant_references": [],
            "merchant_lookup": [],
            "suggestions": [
                "Which devices have critical battery voltage?",
                "Show network signal distribution",
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_count": 1,
                "has_more": False
            }
        }

    def _handle_gmv_trend(self, prompt: str, access_scope: AccessScope | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Perform regression predictions and return historical GMV curves with pagination."""
        context = tools.get_gmv_trend_context(
            self.duckdb_service,
            access_scope=access_scope,
            limit=limit,
            offset=offset,
        )
        historical = context.get("historical_daily_gmv", [])
        total_count = context.get("total_count", len(historical))
        
        return {
            "context": context,
            "sources": ["DuckDB: transactions"],
            "sql_query": context.get("sql_query", ""),
            "data": historical,
            "merchant_references": [],
            "merchant_lookup": [],
            "suggestions": [
                "Summarize daily transaction velocity",
                "Analyze merchant growth segmentation",
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_count": total_count,
                "has_more": (offset + limit) < total_count
            }
        }

    def _handle_unknown(self, prompt: str, access_scope: AccessScope | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Dynamically generate, sanitize, and run SQL queries for custom analytical requests with pagination."""
        try:
            sql = self.ai_service.generate_sql(prompt)
            self.sanitize_sql(sql)
            sql = apply_scope_to_dynamic_sql(sql, access_scope)

            # Fetch total count first
            count_sql = self.get_dynamic_count_sql(sql)
            count_df = self.duckdb_service.query_to_df(count_sql)
            total_count = int(count_df["total_count"].iloc[0]) if not count_df.empty else 0
            
            # Construct paginated SQL
            base_sql = re.sub(r"\bLIMIT\s+\d+(\s+OFFSET\s+\d+)?\b", "", sql, flags=re.IGNORECASE).strip().rstrip(';')
            paginated_sql = f"{base_sql} LIMIT {limit} OFFSET {offset}"
            
            # Fetch row data utilizing cache
            from app.services.copilot.tools import cached_query_to_df
            df = cached_query_to_df(self.duckdb_service, paginated_sql)
            records = df.to_dict(orient="records")
            
            return {
                "context": {"query_results": records, "sql_query": paginated_sql},
                "sources": ["DuckDB: dynamic query"],
                "sql_query": paginated_sql,
                "data": records,
                "merchant_references": [],
                "merchant_lookup": [],
                "suggestions": ["Show daily brief summary", "Show fleet battery health"],
                "intent": CopilotIntent.UNKNOWN.value,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total_count": total_count,
                    "has_more": (offset + limit) < total_count
                }
            }
        except Exception as e:
            print(f"[copilot-service] Dynamic SQL pipeline failed: {e}. Falling back to daily brief.")
            brief = self._handle_daily_brief(prompt, access_scope, limit=limit, offset=offset)
            brief["intent"] = CopilotIntent.DAILY_BRIEF.value
            brief["sources"] = ["DuckDB: portfolio_overview"]
            brief["suggestions"] = ["Show daily brief summary", "Show fleet battery health"]
            return brief

    # =====================================================================
    # Answer Generation and Synthesis Methods
    # =====================================================================

    def _intent_value(self, intent: CopilotIntent | str) -> str:
        return intent.value if isinstance(intent, CopilotIntent) else str(intent)

    def _generate_answer(
        self,
        intent: CopilotIntent | str,
        prompt: str,
        target_model: str,
        context: Dict[str, Any],
        sql_query: str,
        data: List[Dict[str, Any]],
        conversation_history: list[dict[str, str]],
    ) -> str:
        """Flattened answer generation using guard clauses for provider availability checks."""
        if not self.provider.is_available():
            return self._generate_fallback(intent, prompt, context, data, sql_query)

        try:
            if self._intent_value(intent) == CopilotIntent.UNKNOWN.value:
                return self._generate_dynamic_synthesis(prompt, sql_query, data, target_model)
            
            return self._generate_standard_synthesis(
                prompt, context, target_model, conversation_history
            )
        except Exception as e:
            print(f"[copilot-service] Generation error: {e}. Falling back to templates.")
            return self._generate_fallback(intent, prompt, context, data, sql_query)

    def _generate_fallback(
        self,
        intent: CopilotIntent | str,
        prompt: str,
        context: Dict[str, Any],
        data: List[Dict[str, Any]],
        sql_query: str,
    ) -> str:
        if self._intent_value(intent) == CopilotIntent.UNKNOWN.value:
            return f"Retrieved {len(data)} matching records dynamically from DuckDB."
        return generate_template_fallback(self._intent_value(intent), prompt, context)

    def _generate_dynamic_synthesis(self, prompt: str, sql_query: str, data: List[Dict[str, Any]], target_model: str) -> str:
        """Ask LLM to explain raw query records from custom dynamic joins/filters."""
        synthesis_prompt = f"""
        You are an expert analyst. Answer the user's question by reviewing the database query results.
        User Question: "{prompt}"
        Executed SQL: "{sql_query}"
        Query Results (JSON):
        {json.dumps(data, indent=2, default=str)}
        
        Provide a concise, direct, professional answer summarizing the findings. Do not show raw JSON in the answer unless requested.
        """
        return self.provider.generate(
            prompt=synthesis_prompt,
            system_instruction="You are Chanakya, the highly intelligent operational copilot for Soundbox operations.",
            history=[],
            model_name=target_model
        )

    def _generate_standard_synthesis(
        self,
        prompt: str,
        context: Dict[str, Any],
        target_model: str,
        conversation_history: list[dict[str, str]],
    ) -> str:
        """Prompt LLM using standard templates with caller-supplied recent history."""
        settings = get_settings()
        history = conversation_history[-settings.llm_context_window :]
        system_instruction = f"""
        You are Chanakya, the highly intelligent operational copilot for Soundbox payment and device operations.
        Analyze the user's question using the retrieved database context below.
        
        Retrieved Context:
        {json.dumps(context, indent=2, default=str)}
        
        Instructions:
        1. Provide a professional, concise, and structured answer.
        2. Use bullet points and clean markdown formatting.
        3. Base your answer STRICTLY on the retrieved context. If details are missing or empty, explain that the context is unavailable.
        4. Do NOT disclose raw JSON formats in the text unless asked.
        """
        return self.provider.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            history=history,
            model_name=target_model
        )

    # =====================================================================
    # Export Report Generators
    # =====================================================================

    def generate_excel_report(self, data: List[Dict[str, Any]]) -> bytes:
        """Convert a list of dictionary records to a downloadable Excel binary stream, falling back to CSV if openpyxl is missing."""
        import io
        import pandas as pd
        df = pd.DataFrame(data)
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Report')
            return output.getvalue()
        except (ImportError, ValueError, ModuleNotFoundError):
            output_str = io.StringIO()
            df.to_csv(output_str, index=False)
            return output_str.getvalue().encode('utf-8')

    def generate_pdf_report(self, answer: str, data: List[Dict[str, Any]]) -> bytes:
        """Convert response text and records to a styled PDF binary stream (ReportLab with text fallbacks)."""
        import io
        
        if not HAS_REPORTLAB:
            # Fallback text-based report formatted as a byte stream if ReportLab is missing
            fallback = f"--- Soundbox Lakehouse Report ---\n\n{answer}\n\n"
            if data:
                fallback += "Raw Records:\n"
                fallback += json.dumps(data, indent=2)
            return fallback.encode('utf-8')
            
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []
        styles = getSampleStyleSheet()
        
        # Styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#1E3A8A'),
            spaceAfter=15
        )
        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['BodyText'],
            fontSize=10,
            leading=14,
            spaceAfter=15
        )
        
        # Add Title & Summary
        story.append(Paragraph("Soundbox Lakehouse Analytics Report", title_style))
        story.append(Spacer(1, 10))
        clean_text = answer.replace('\n', '<br/>')
        story.append(Paragraph(clean_text, body_style))
        story.append(Spacer(1, 15))
        
        # Add Data Table
        if data and isinstance(data, list):
            headers = list(data[0].keys())
            table_data = [headers]
            for row in data[:50]:  # Cap to 50 rows for safety
                table_data.append([str(row.get(h, '')) for h in headers])
                
            col_width = (doc.width) / len(headers) if headers else doc.width
            t = Table(table_data, colWidths=[col_width]*len(headers))
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 9),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F3F4F6')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,1), (-1,-1), 8),
                ('TOPPADDING', (0,1), (-1,-1), 4),
                ('BOTTOMPADDING', (0,1), (-1,-1), 4),
            ]))
            story.append(t)
            
        doc.build(story)
        return buffer.getvalue()

    # =====================================================================
    # Public API Method
    # =====================================================================

    def query(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        org_id: Optional[str] = None,
        access_scope: Optional[AccessScope] = None,
        model_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Stateless query — history from request only; nothing persisted after response."""
        start_time = time.time()
        normalized_history = normalize_conversation_history(conversation_history)
        scope = access_scope or scope_from_org_id(org_id)

        intent = self.classify_intent(prompt)
        handler = self.intent_handlers.get(intent, self._handle_unknown)
        res = handler(prompt, scope, limit=limit, offset=offset)

        final_intent = res.get("intent", intent)
        final_intent_value = self._intent_value(final_intent)

        target_model = model_name or "gemini-2.5-flash"
        answer = self._generate_answer(
            intent=final_intent,
            prompt=prompt,
            target_model=target_model,
            context=res["context"],
            sql_query=res["sql_query"],
            data=res["data"],
            conversation_history=normalized_history,
        )

        latency = time.time() - start_time

        return {
            "conversation_id": conversation_id,
            "answer": answer,
            "intent": final_intent_value,
            "sources": res["sources"],
            "suggestions": res["suggestions"],
            "latency": round(latency, 3),
            "sql_query": res["sql_query"] or None,
            "data": res["data"],
            "merchant_references": res["merchant_references"],
            "merchant_lookup": res["merchant_lookup"],
            "pagination": res.get("pagination"),
        }
