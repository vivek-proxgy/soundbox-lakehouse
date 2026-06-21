import pytest
import pandas as pd
from fastapi import HTTPException

from app.security.enums.auth_method import AuthMethod
from app.services.copilot.enums.intent import CopilotIntent
from app.services.copilot import CopilotService
from app.routes.copilot import (
    query_copilot,
    export_excel_report,
    export_pdf_report,
)
from app.routes.schemas.copilot import (
    CopilotQueryRequest,
    ConversationMessage,
    ExportExcelRequest,
    ExportPDFRequest,
)
from app.services.copilot.tools import QueryCache
from app.security.auth import AuthContext

_TEST_AUTH = AuthContext(
    user_id="test",
    session_id=None,
    role=None,
    org_id=None,
    auth_method=AuthMethod.DISABLED,
)


def test_classify_intent():
    service = CopilotService()
    assert service.classify_intent("Give me the daily brief for my portfolio") == CopilotIntent.DAILY_BRIEF
    assert service.classify_intent("profile for merchant m123") == CopilotIntent.MERCHANT_PROFILE
    assert service.classify_intent("check battery of the fleet") == CopilotIntent.FLEET_HEALTH
    assert service.classify_intent("forecast revenue next week") == CopilotIntent.GMV_TREND
    assert service.classify_intent("explain risk for merchant abc") == CopilotIntent.MERCHANT_RISK
    assert service.classify_intent("random question about payments") == CopilotIntent.UNKNOWN


def test_sql_security_sanitizer():
    service = CopilotService()
    service.sanitize_sql("SELECT * FROM merchants")
    with pytest.raises(HTTPException):
        service.sanitize_sql("DROP TABLE merchants")


def test_sql_enforce_limit():
    service = CopilotService()
    assert "LIMIT 100" in service.enforce_limit("SELECT * FROM merchants")


def test_query_cache_functionality():
    cache = QueryCache(ttl_seconds=10)
    df = pd.DataFrame([{"col1": "val1"}])
    cache.set("SELECT * FROM test", df)
    assert cache.get("SELECT * FROM test") is not None


def test_stateless_copilot_accepts_backend_history():
    req = CopilotQueryRequest(
        prompt="Give me a daily brief overview",
        conversation_id="conv-backend-001",
        conversation_history=[
            ConversationMessage(role="user", content="Previous question"),
            ConversationMessage(role="assistant", content="Previous answer"),
        ],
    )
    response = query_copilot(req, auth=_TEST_AUTH)
    assert response.conversation_id == "conv-backend-001"
    assert response.intent == CopilotIntent.DAILY_BRIEF.value
    assert response.answer


def test_copilot_pagination_and_export():
    req = CopilotQueryRequest(
        prompt="Give me a daily brief overview",
        conversation_id="pager-conv-123",
        limit=10,
        offset=0,
    )
    response = query_copilot(req, auth=_TEST_AUTH)
    assert response.pagination is not None

    excel_req = ExportExcelRequest(
        data=[{"merchant_id": "m1", "sales": 500}],
        filename_hint="pager-conv-123",
    )
    excel_resp = export_excel_report(excel_req, auth=_TEST_AUTH)
    assert excel_resp.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    pdf_req = ExportPDFRequest(
        answer="Portfolio overview.",
        data=[{"merchant_id": "m1", "sales": 500}],
        filename_hint="pager-conv-123",
    )
    pdf_resp = export_pdf_report(pdf_req, auth=_TEST_AUTH)
    assert pdf_resp.media_type == "application/pdf"
