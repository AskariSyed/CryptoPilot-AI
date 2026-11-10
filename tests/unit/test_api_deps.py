"""
Unit tests for cryptopilot.api.deps.
Validates paper broker singleton, database session generator, and admin bearer auth.
"""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from cryptopilot.api.deps import (
    get_db_session,
    get_paper_broker,
    reset_api_broker,
    verify_admin_token,
)
from cryptopilot.config.settings import get_settings
from cryptopilot.execution.broker import PaperBroker


def test_paper_broker_singleton() -> None:
    """Verifies get_paper_broker returns persistent instance and reset_api_broker resets it."""
    reset_api_broker()
    b1 = get_paper_broker()
    b2 = get_paper_broker()
    assert isinstance(b1, PaperBroker)
    assert b1 is b2

    reset_api_broker()
    b3 = get_paper_broker()
    assert b3 is not b1
    reset_api_broker()


def test_verify_admin_token() -> None:
    """Tests bearer authentication token validation."""
    settings = get_settings()
    valid_key = settings.api_secret_key

    # 1. Missing credentials -> 401 Unauthorized
    with pytest.raises(HTTPException) as exc_401:
        verify_admin_token(None)
    assert exc_401.value.status_code == 401

    # Empty token -> 401 Unauthorized
    with pytest.raises(HTTPException) as exc_empty:
        verify_admin_token(HTTPAuthorizationCredentials(scheme="Bearer", credentials=""))
    assert exc_empty.value.status_code == 401

    # 2. Invalid secret key -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_403:
        verify_admin_token(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-secret")
        )
    assert exc_403.value.status_code == 403

    # 3. Valid key -> Returns secret
    result = verify_admin_token(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_key)
    )
    assert result == valid_key


@pytest.mark.asyncio
async def test_get_db_session_dependency() -> None:
    """Verifies get_db_session yields an active async session."""
    gen = get_db_session()
    session = await anext(gen)
    assert session is not None
    await gen.aclose()
