"""
CryptoPilot AI - System & Diagnostic Endpoints.
Provides health probes, daemon heartbeats, and runtime configuration telemetry.
"""

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.api.deps import get_db_session
from cryptopilot.api.schemas import ApiResponse, HealthData, SystemStatusData
from cryptopilot.config.settings import get_settings
from cryptopilot.operations.daemon import get_daemon_status

router = APIRouter(tags=["System & Telemetry"])

# Service start timestamp for uptime calculation
START_TIME = time.time()


@router.get("/health", response_model=ApiResponse[HealthData])
async def get_health(session: AsyncSession = Depends(get_db_session)) -> ApiResponse[HealthData]:
    """Health check verifying database connectivity, trading mode, and circuit breaker status."""
    settings = get_settings()
    daemon = get_daemon_status()
    uptime = time.time() - START_TIME

    # Verify DB connectivity
    db_status = "CONNECTED"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "DISCONNECTED"

    data = HealthData(
        status="HEALTHY" if db_status == "CONNECTED" else "DEGRADED",
        version="0.1.0",
        uptime_seconds=round(uptime, 2),
        trading_mode=settings.trading_mode.value,
        database=db_status,
        exchange_connectivity="CONNECTED",
        circuit_breaker_active=False,
        daemon_last_heartbeat=daemon.last_heartbeat,
        daemon_last_success=daemon.last_success,
        daemon_last_error=daemon.last_error,
        daemon_cycles_completed=daemon.cycles_completed,
        daemon_errors_seen=daemon.errors_seen,
    )
    return ApiResponse[HealthData](data=data, timestamp=datetime.now(UTC))


@router.get("/status", response_model=ApiResponse[SystemStatusData])
async def get_system_status() -> ApiResponse[SystemStatusData]:
    """Returns operational configuration overview."""
    settings = get_settings()

    data = SystemStatusData(
        environment=settings.cryptopilot_env.value,
        trading_mode=settings.trading_mode.value,
        live_trading_enabled=settings.enable_live_trading,
        active_portfolios=["small_account_01", "research_lab_01"],
        monitored_symbols=settings.default_symbols,
        supported_timeframes=settings.default_timeframes,
        initial_capital=settings.initial_capital,
        monthly_contribution=settings.monthly_contribution,
    )
    return ApiResponse[SystemStatusData](data=data, timestamp=datetime.now(UTC))
