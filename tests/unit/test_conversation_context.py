import pytest
from fastapi import HTTPException

from app.services.copilot.conversation_context import normalize_conversation_history


def test_empty_history_returns_empty_list():
    assert normalize_conversation_history(None) == []
    assert normalize_conversation_history([]) == []


def test_valid_history_normalized():
    raw = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    result = normalize_conversation_history(raw)
    assert len(result) == 2
    assert result[0]["role"] == "user"


def test_invalid_role_rejected():
    with pytest.raises(HTTPException):
        normalize_conversation_history([{"role": "system", "content": "bad"}])


def test_empty_content_rejected():
    with pytest.raises(HTTPException):
        normalize_conversation_history([{"role": "user", "content": "  "}])
