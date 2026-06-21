"""Orchestrator service for Chanakya Copilot logic incorporating clean registry patterns, paging, and report exports."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from app.config.settings import Settings, get_settings
from app.services.duckdb_service import DuckDBService
from app.services.ai_service import AIService
from app.services.copilot.intents import classify_intent
from app.services.copilot import tools
from app.services.copilot.templates import generate_template_fallback
from app.services.copilot import session
from app.services.copilot.providers import GeminiProvider

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
            "daily_brief": self._handle_daily_brief,
            "merchant_profile": self._handle_merchant_profile,
            "merchant_risk": self._handle_merchant_risk,
            "fleet_health": self._handle_fleet_health,
            "gmv_trend": self._handle_gmv_trend,
            "unknown": self._handle_unknown,
        }

    def classify_intent(self, prompt: str) -> str:
        """Classify user prompt into a predefined domain intent."""
        return classify_intent(prompt)

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve message history for the session."""
        return session.get_history(session_id)

    def terminate_session(self, session_id: str) -> None:
        """Terminate session and delete its conversation history from storage."""
        session.delete_session(session_id)

    def sanitize_sql(self, sql: str) -> None:
        """Enforce strict read-only execution by blocking write or destructive operations."""
        clean = sql.upper().strip()
        forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE", "RENAME", "GRANT", "REVOKE"]
        for token in forbidden:
            if re.search(rf"\b{token}\b", clean):
                raise ValueError(f"Security Policy Violation: Forbidden write SQL keyword detected: {token}")

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

    def _handle_daily_brief(self, prompt: str, org_id: str | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Fetch daily portfolio metrics summary."""
        context = tools.get_daily_brief_context(self.duckdb_service, org_id)
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

    def _handle_merchant_profile(self, prompt: str, org_id: str | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Lookup merchant profiles matching name or ID with pagination."""
        profile_res = tools.get_merchant_profile_context(self.duckdb_service, prompt, org_id, limit=limit, offset=offset)
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

    def _handle_merchant_risk(self, prompt: str, org_id: str | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Evaluate operational risk and transaction health for a merchant."""
        risk_res = tools.get_merchant_risk_context(self.duckdb_service, prompt, org_id)
        
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

    def _handle_fleet_health(self, prompt: str, org_id: str | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Review hardware issues and telemetry warning states."""
        context = tools.get_fleet_health_context(self.duckdb_service, org_id)
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

    def _handle_gmv_trend(self, prompt: str, org_id: str | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Perform regression predictions and return historical GMV curves with pagination."""
        context = tools.get_gmv_trend_context(self.duckdb_service, org_id, limit=limit, offset=offset)
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

    def _handle_unknown(self, prompt: str, org_id: str | None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Dynamically generate, sanitize, and run SQL queries for custom analytical requests with pagination."""
        try:
            sql = self.ai_service.generate_sql(prompt)
            self.sanitize_sql(sql)
            
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
                "intent": "unknown",
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total_count": total_count,
                    "has_more": (offset + limit) < total_count
                }
            }
        except Exception as e:
            print(f"[copilot-service] Dynamic SQL pipeline failed: {e}. Falling back to daily brief.")
            brief = self._handle_daily_brief(prompt, org_id, limit=limit, offset=offset)
            brief["intent"] = "daily_brief"
            brief["sources"] = ["DuckDB: portfolio_overview"]
            brief["suggestions"] = ["Show daily brief summary", "Show fleet battery health"]
            return brief

    # =====================================================================
    # Answer Generation and Synthesis Methods
    # =====================================================================

    def _generate_answer(
        self,
        intent: str,
        prompt: str,
        target_model: str,
        context: Dict[str, Any],
        sql_query: str,
        data: List[Dict[str, Any]],
        sid: str,
    ) -> str:
        """Flattened answer generation using guard clauses for provider availability checks."""
        if not self.provider.is_available():
            return self._generate_fallback(intent, prompt, context, data, sql_query)

        try:
            if intent == "unknown":
                return self._generate_dynamic_synthesis(prompt, sql_query, data, target_model)
            
            return self._generate_standard_synthesis(prompt, context, target_model, sid)
        except Exception as e:
            print(f"[copilot-service] Generation error: {e}. Falling back to templates.")
            return self._generate_fallback(intent, prompt, context, data, sql_query)

    def _generate_fallback(self, intent: str, prompt: str, context: Dict[str, Any], data: List[Dict[str, Any]], sql_query: str) -> str:
        """Fall back to markdown templates if LLM execution is unavailable."""
        if intent == "unknown":
            return f"Retrieved {len(data)} matching records dynamically from DuckDB."
        return generate_template_fallback(intent, prompt, context)

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

    def _generate_standard_synthesis(self, prompt: str, context: Dict[str, Any], target_model: str, sid: str) -> str:
        """Prompt LLM using standard templates with recent chat history."""
        history = session.get_history(sid)[-6:]
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
        session_id: Optional[str] = None,
        org_id: Optional[str] = None,
        model_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Process a query: classify, execute handler dynamically, synthesize answer, and return response dict."""
        start_time = time.time()
        sid = session.get_or_create_session(session_id)
        
        # 1. Classify intent
        intent = self.classify_intent(prompt)
        
        # 2. Get handler from registry and execute (Early returns and registry pattern)
        handler = self.intent_handlers.get(intent, self._handle_unknown)
        res = handler(prompt, org_id, limit=limit, offset=offset)
        
        final_intent = res.get("intent", intent)
        
        # 3. Generate answer using flattened method
        target_model = model_name or "gemini-2.5-flash"
        answer = self._generate_answer(
            intent=final_intent,
            prompt=prompt,
            target_model=target_model,
            context=res["context"],
            sql_query=res["sql_query"],
            data=res["data"],
            sid=sid
        )

        # 4. Update message history
        session.append_history(sid, prompt, answer)
        
        latency = time.time() - start_time
        
        return {
            "session_id": sid,
            "answer": answer,
            "intent": final_intent,
            "sources": res["sources"],
            "suggestions": res["suggestions"],
            "latency": round(latency, 3),
            "sql_query": res["sql_query"] or None,
            "data": res["data"],
            "merchant_references": res["merchant_references"],
            "merchant_lookup": res["merchant_lookup"],
            "pagination": res.get("pagination")
        }
