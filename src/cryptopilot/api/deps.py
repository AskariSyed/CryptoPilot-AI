"""
CryptoPilot AI - FastAPI Dependency Injection Providers.
Supplies async database sessions, singleton paper broker execution engine,
and bearer token authentication guards.
"""

from collections.abc import AsyncGenerator

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from cryptopilot.config.settings import get_settings
from cryptopilot.database.connection import get_db_manager
from cryptopilot.execution.broker import PaperBroker

# Optional bearer token scheme
security_bearer = HTTPBearer(auto_error=False)

# Singleton broker instance for API simulation
_api_broker_instance: PaperBroker | None = None


def get_paper_broker() -> PaperBroker:
    """Returns singleton PaperBroker instance initialized from application settings."""
    global _api_broker_instance
    if _api_broker_instance is None:
        settings = get_settings()
        _api_broker_instance = PaperBroker(
            small_account_capital=settings.initial_capital,
            small_account_contribution=settings.monthly_contribution,
            research_capital=10000.0,
        )
    return _api_broker_instance


def reset_api_broker() -> None:
    """Resets the singleton PaperBroker (primarily for test fixture isolation)."""
    global _api_broker_instance
    _api_broker_instance = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated AsyncSession with automatic transaction rollback on failure."""
    manager = get_db_manager()
    async with manager.session() as session:
        yield session


def verify_admin_token(
    credentials: HTTPAuthorizationCredentials | None = Security(security_bearer),
) -> str:
    """
    Validates Bearer token against settings.api_secret_key.
    Required for administrative actions (deposits, manual halts, cancellations).
    """
    settings = get_settings()
    expected_secret = settings.api_secret_key

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid administrative secret token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
