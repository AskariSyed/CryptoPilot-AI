"""
CryptoPilot AI - FastAPI Application Factory.
Configures CORS, global middleware, standard exception envelopes,
and API v1 routing controllers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cryptopilot.api.middleware import RequestLoggingMiddleware, register_exception_handlers
from cryptopilot.api.routers import (
    control,
    decisions,
    market,
    portfolio,
    risk,
    system,
    trading,
)
from cryptopilot.database.connection import get_db_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown hooks."""
    # Startup: Ensure database schema is initialized
    db_mgr = get_db_manager()
    await db_mgr.init_db()
    yield
    # Shutdown: Close database connection pool
    await db_mgr.close()


def create_app() -> FastAPI:
    """Creates and configures a production-ready FastAPI application."""
    app = FastAPI(
        title="CryptoPilot AI API",
        description="Autonomous Cryptocurrency Spot Trading Agent & Virtual Execution Engine",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 1. CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Permits React dashboard in dev and production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Custom Logging & Diagnostic Middleware
    app.add_middleware(RequestLoggingMiddleware)

    # 3. Global Exception Envelope Registration
    register_exception_handlers(app)

    # 4. Mount API v1 Routers
    api_prefix = "/api/v1"
    app.include_router(system.router, prefix=api_prefix)
    app.include_router(market.router, prefix=api_prefix)
    app.include_router(portfolio.router, prefix=api_prefix)
    app.include_router(trading.router, prefix=api_prefix)
    app.include_router(decisions.router, prefix=api_prefix)
    app.include_router(risk.router, prefix=api_prefix)
    app.include_router(control.router, prefix=api_prefix)

    return app


# Module-level FastAPI instance for Uvicorn ASGI runner
app = create_app()
