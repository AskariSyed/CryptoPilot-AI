"""
Unit tests for cryptopilot.api.middleware.
Validates custom exception envelope formatting, validation error messages, and timing headers.
"""

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from cryptopilot.api.middleware import RequestLoggingMiddleware, register_exception_handlers


@pytest.fixture
def dummy_app() -> FastAPI:
    """Creates a minimal FastAPI app configured with CryptoPilot exception handlers and middleware."""
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    @app.get("/test-http-error")
    async def trigger_http_error():
        raise HTTPException(status_code=400, detail="Custom bad request")

    @app.get("/test-generic-error")
    async def trigger_generic_error():
        raise ValueError("Unexpected explosion")

    return app


@pytest.mark.asyncio
async def test_middleware_timing_and_error_envelopes(dummy_app: FastAPI) -> None:
    """Verifies timing header and structured error response envelopes."""
    transport = httpx.ASGITransport(app=dummy_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 400 Custom HTTPException
        res_400 = await client.get("/test-http-error")
        assert res_400.status_code == 400
        assert "X-Process-Time-Ms" in res_400.headers

        body_400 = res_400.json()
        assert body_400["success"] is False
        assert body_400["data"] is None
        assert body_400["error"] == "Custom bad request"

        # 2. 500 Generic Unhandled Exception
        res_500 = await client.get("/test-generic-error")
        assert res_500.status_code == 500
        body_500 = res_500.json()
        assert body_500["success"] is False
        assert "Internal server error" in body_500["error"]

        # 3. 404 Route Not Found
        res_404 = await client.get("/non-existent-endpoint")
        assert res_404.status_code == 404
        body_404 = res_404.json()
        assert body_404["success"] is False
        assert "Not Found" in body_404["error"]

