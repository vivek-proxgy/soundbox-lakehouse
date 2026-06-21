"""Stateless conversation context — validate inbound history only, never persist."""

from __future__ import annotations

import re
from typing import Any

from app.config.settings import get_settings
from app.core.enums.error_key import ErrorKey
from app.core.http_errors import bad_request
from app.core.messages.error_messages import ErrorMessage

_ALLOWED_ROLES = frozenset({"user", "assistant"})


def normalize_conversation_history(
    raw_history: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """
    Validate and sanitize conversation history supplied by the caller Backend.

    The intelligence service is stateless — history is read from the request payload
    for this invocation only and discarded after the response is returned.
    """
    if not raw_history:
        return []

    settings = get_settings()
    max_turns = settings.conversation_max_turns
    max_message_length = settings.conversation_max_message_length

    if len(raw_history) > max_turns:
        raise bad_request(
            ErrorKey.VALIDATION,
            ErrorMessage.CONVERSATION_TOO_LONG.value.format(max_turns=max_turns),
        )

    normalized: list[dict[str, str]] = []
    for index, message in enumerate(raw_history):
        role = str(message.get("role", "")).strip().lower()
        if role not in _ALLOWED_ROLES:
            raise bad_request(
                ErrorKey.VALIDATION,
                ErrorMessage.CONVERSATION_INVALID_ROLE.value.format(index=index),
            )

        content = str(message.get("content", "")).strip()
        if not content:
            raise bad_request(
                ErrorKey.VALIDATION,
                ErrorMessage.CONVERSATION_EMPTY_MESSAGE.value.format(index=index),
            )

        if len(content) > max_message_length:
            raise bad_request(
                ErrorKey.VALIDATION,
                ErrorMessage.CONVERSATION_MESSAGE_TOO_LONG.value.format(
                    index=index,
                    max_length=max_message_length,
                ),
            )

        content = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", content)
        normalized.append({"role": role, "content": content})

    return normalized[-max_turns:]
