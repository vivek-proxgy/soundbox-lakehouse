"""Router assembly — mirrors soundbox-chanakya build_api_router pattern."""

from __future__ import annotations

from fastapi import APIRouter

from app.routes import health, intelligence, internal


def build_api_router() -> APIRouter:
    root = APIRouter()
    root.include_router(health.router)
    root.include_router(intelligence.router)
    root.include_router(internal.router)
    return root
