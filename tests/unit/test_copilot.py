import pytest
import pandas as pd
from app.services.copilot import CopilotService
from app.routes.copilot import (
    query_copilot,
    get_copilot_history,
    delete_copilot_session,
    export_excel_report,
    export_pdf_report,
    CopilotQueryRequest,
    ExportExcelRequest,
    ExportPDFRequest,
)
from app.services.copilot.tools import QueryCache


def test_classify_intent():
    service = CopilotService()
    assert service.classify_intent("Give me the daily brief for my portfolio") == "daily_brief"
    assert service.classify_intent("profile for merchant m123") == "merchant_profile"
    assert service.classify_intent("check battery of the fleet") == "fleet_health"
    assert service.classify_intent("forecast revenue next week") == "gmv_trend"
    assert service.classify_intent("explain risk for merchant abc") == "merchant_risk"
    assert service.classify_intent("random question about payments") == "unknown"


def test_sql_security_sanitizer():
    service = CopilotService()
    # Safe reads should pass
    service.sanitize_sql("SELECT * FROM merchants")
    service.sanitize_sql("SELECT count(*), city FROM merchants GROUP BY city")
    
    # Forbidden writes should raise ValueError
    with pytest.raises(ValueError, match="Security Policy Violation"):
        service.sanitize_sql("DROP TABLE merchants")
    with pytest.raises(ValueError, match="Security Policy Violation"):
        service.sanitize_sql("DELETE FROM transactions WHERE amount > 10")
    with pytest.raises(ValueError, match="Security Policy Violation"):
        service.sanitize_sql("UPDATE merchants SET name = 'Hacker'")
    with pytest.raises(ValueError, match="Security Policy Violation"):
        service.sanitize_sql("ALTER TABLE device_telemetry ADD COLUMN mal_data VARCHAR")


def test_sql_enforce_limit():
    service = CopilotService()
    assert "LIMIT 100" in service.enforce_limit("SELECT * FROM merchants")
    assert "LIMIT 5" in service.enforce_limit("SELECT * FROM merchants LIMIT 5")


def test_query_cache_functionality():
    cache = QueryCache(ttl_seconds=10)
    df = pd.DataFrame([{"col1": "val1"}])
    cache.set("SELECT * FROM test", df)
    
    cached_df = cache.get("SELECT * FROM test")
    assert cached_df is not None
    assert cached_df.iloc[0]["col1"] == "val1"
    
    # Test LRU eviction logic
    cache = QueryCache(ttl_seconds=10, max_size=2)
    cache.set("q1", pd.DataFrame([{"x": 1}]))
    cache.set("q2", pd.DataFrame([{"x": 2}]))
    cache.set("q3", pd.DataFrame([{"x": 3}]))
    
    assert cache.get("q1") is None  # Evicted as oldest
    assert cache.get("q2") is not None
    assert cache.get("q3") is not None


@pytest.mark.asyncio
async def test_copilot_query_api_fallback():
    # Test router post query directly
    session_id = "fallback-session-888"
    req = CopilotQueryRequest(
        prompt="Give me a daily brief overview",
        session_id=session_id
    )
    
    response = await query_copilot(req)
    assert response.session_id == session_id
    assert response.intent == "daily_brief"
    assert "Portfolio" in response.answer or "No matching records" in response.answer
    assert response.sql_query is not None
    assert response.data is not None
    
    # Test router get history directly
    history_resp = await get_copilot_history(session_id=session_id)
    assert history_resp.session_id == session_id
    assert len(history_resp.history) == 2
    assert history_resp.history[0].role == "user"

    # Clean up session history
    await delete_copilot_session(session_id=session_id)


@pytest.mark.asyncio
async def test_session_lifecycle_and_termination(tmp_path):
    import os
    
    # Configure temporary local storage directory via env
    session_dir = str(tmp_path / "sessions")
    os.environ["SESSION_LOCAL_DIR"] = session_dir
    os.environ["SESSION_STORAGE_TYPE"] = "local"
    
    session_id = "lifecycle-session-999"
    
    # 1. Start query (which creates session file)
    req = CopilotQueryRequest(
        prompt="Explain risk for merchant abc",
        session_id=session_id
    )
    await query_copilot(req)
    
    # Check that local file exists
    expected_file = os.path.join(session_dir, f"{session_id}.json")
    assert os.path.exists(expected_file)
    
    # 2. Get history and check contents
    history_resp = await get_copilot_history(session_id=session_id)
    assert len(history_resp.history) == 2
    
    # 3. Terminate session (which deletes the file)
    del_res = await delete_copilot_session(session_id=session_id)
    assert del_res["status"] == "success"
    
    # Check file is deleted
    assert not os.path.exists(expected_file)
    
    # Check history is now empty
    history_resp_after = await get_copilot_history(session_id=session_id)
    assert len(history_resp_after.history) == 0
    
    # Cleanup env
    del os.environ["SESSION_LOCAL_DIR"]
    del os.environ["SESSION_STORAGE_TYPE"]


@pytest.mark.asyncio
async def test_copilot_pagination_and_export():
    # 1. Test query pagination metadata
    req = CopilotQueryRequest(
        prompt="Give me a daily brief overview",
        session_id="pager-session-123",
        limit=10,
        offset=0
    )
    response = await query_copilot(req)
    assert response.pagination is not None
    assert response.pagination["limit"] == 10
    assert response.pagination["offset"] == 0
    assert "total_count" in response.pagination
    assert "has_more" in response.pagination

    # 2. Test Excel exporting
    excel_req = ExportExcelRequest(
        data=[{"merchant_id": "m1", "sales": 500}, {"merchant_id": "m2", "sales": 800}],
        session_id="pager-session-123"
    )
    excel_resp = await export_excel_report(excel_req)
    assert excel_resp is not None
    
    excel_data = b""
    async for chunk in excel_resp.body_iterator:
        excel_data += chunk
    assert len(excel_data) > 0

    # 3. Test PDF exporting
    pdf_req = ExportPDFRequest(
        answer="Here is your portfolio overview showing solid transaction growth.",
        data=[{"merchant_id": "m1", "sales": 500}],
        session_id="pager-session-123"
    )
    pdf_resp = await export_pdf_report(pdf_req)
    assert pdf_resp is not None
    
    pdf_data = b""
    async for chunk in pdf_resp.body_iterator:
        pdf_data += chunk
    assert len(pdf_data) > 0

