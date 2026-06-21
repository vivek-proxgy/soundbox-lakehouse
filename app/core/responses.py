"""Standard error response envelope matching on-prem-soundbox-backend."""

from __future__ import annotations

from typing import Any


def build_error_response(
    status: int,
    errors: dict[str, Any],
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"status": status, "errors": errors}
    if request_id:
        body["request_id"] = request_id
    return body


def format_validation_errors(errors: list[dict[str, Any]]) -> dict[str, str]:
    """Flatten FastAPI/Pydantic validation errors into field → message map."""
    formatted: dict[str, str] = {}

    def walk(err: dict[str, Any], prefix: str = "") -> None:
        loc = err.get("loc", ())
        field = ".".join(str(part) for part in loc if part != "body")
        if prefix and field:
            field = f"{prefix}.{field}"
        elif prefix:
            field = prefix
        elif not field:
            field = "body"

        if err.get("type") == "value_error" or err.get("msg"):
            formatted[field] = err.get("msg", "Invalid value")
        for sub in err.get("ctx", {}).get("errors", []) if isinstance(err.get("ctx"), dict) else []:
            walk(sub, field)

    for err in errors:
        loc = err.get("loc", ())
        field = ".".join(str(part) for part in loc if part != "body") or "body"
        formatted[field] = err.get("msg", "Invalid value")

    return formatted
