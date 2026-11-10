"""
CryptoPilot AI - API Middleware & Exception Handlers.
Implements request timing, CORS headers, and global exception envelopes.
"""

import logging
import time
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from cryptopilot.api.schemas import ApiResponse

logger = logging.getLogger("cryptopilot.api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming HTTP requests, response status, and processing duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        logger.debug(
            "%s %s -> %d (%.2fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Registers standard envelope error handlers on the FastAPI application."""

    @app.exception_handler(StarletteHTTPException)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException | HTTPException
    ) -> JSONResponse:
        envelope = ApiResponse[None](
            success=False,
            data=None,
            error=str(exc.detail),
            timestamp=datetime.now(UTC),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope.model_dump(mode="json"),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error_msgs = [
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in exc.errors()
        ]
        combined_error = "; ".join(error_msgs)

        envelope = ApiResponse[None](
            success=False,
            data=None,
            error=combined_error,
            timestamp=datetime.now(UTC),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=envelope.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server exception: %s", exc)
        envelope = ApiResponse[None](
            success=False,
            data=None,
            error="Internal server error occurred.",
            timestamp=datetime.now(UTC),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=envelope.model_dump(mode="json"),
        )
