from __future__ import annotations

from enum import StrEnum


class ErrorMessage(StrEnum):
    """User-facing error messages — no inline strings in handlers."""

    AUTH_REQUIRED = "Authentication required"
    AUTH_NOT_CONFIGURED = "Authentication is not configured"
    TOKEN_EXPIRED = "Token is expired"
    TOKEN_INVALID = "Could not validate credentials"
    TOKEN_TYPE_INVALID = "Invalid token type"
    TOKEN_PAYLOAD_INVALID = "Invalid token payload"
    API_KEY_NOT_CONFIGURED = "API key authentication is not configured"
    API_KEY_REQUIRED = "API key required — JWT authentication is disabled in production mode"
    API_KEY_INVALID = "Invalid API key"
    FORBIDDEN = "Insufficient permissions"
    GENERIC_FAILURE = "Request could not be processed. Please try again."
    SQL_EMPTY = "SQL query cannot be empty"
    SQL_FORBIDDEN_KEYWORD = "Forbidden SQL keyword detected: {keyword}"
    SQL_SELECT_ONLY = "Only SELECT or WITH queries are allowed"
    SQL_MAX_LENGTH = "SQL query exceeds maximum length of {max_length} characters"
    GEMINI_NOT_CONFIGURED = "Gemini API key is not configured. Set GEMINI_API_KEY."
    RATE_LIMIT = "Too many requests. Please try again later."
    CONVERSATION_TOO_LONG = "conversation_history exceeds maximum of {max_turns} messages"
    CONVERSATION_INVALID_ROLE = "conversation_history[{index}] has invalid role; use user or assistant"
    CONVERSATION_EMPTY_MESSAGE = "conversation_history[{index}] content cannot be empty"
    CONVERSATION_MESSAGE_TOO_LONG = "conversation_history[{index}] exceeds maximum length of {max_length} characters"
