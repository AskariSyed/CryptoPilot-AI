"""Safe notification adapters for operational events."""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import aiohttp

logger = logging.getLogger(__name__)


class NotificationAdapter(Protocol):
    """Delivers a human-readable operational event."""

    async def send(self, subject: str, message: str) -> None:
        """Send an event notification."""


@dataclass(slots=True)
class ConsoleNotification:
    """Writes notifications to the configured application logger."""

    async def send(self, subject: str, message: str) -> None:
        logger.warning("NOTIFICATION %s: %s", subject, message)


@dataclass(slots=True)
class WebhookNotification:
    """Posts a JSON event to a configured webhook endpoint."""

    url: str
    timeout_seconds: float = 10.0

    async def send(self, subject: str, message: str) -> None:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.url, json={"subject": subject, "message": message}
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(
                        f"Webhook notification failed ({response.status}): {body[:200]}"
                    )


@dataclass(slots=True)
class EmailNotification:
    """Sends an operational event through an authenticated SMTP relay."""

    host: str
    port: int
    username: str
    password: str
    sender: str
    recipient: str

    async def send(self, subject: str, message: str) -> None:
        email = EmailMessage()
        email["Subject"] = subject
        email["From"] = self.sender
        email["To"] = self.recipient
        email.set_content(message)

        def deliver() -> None:
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(self.username, self.password)
                smtp.send_message(email)

        import asyncio

        await asyncio.to_thread(deliver)


class NotificationService:
    """Fan-out service that keeps one failing adapter from hiding other alerts."""

    def __init__(self, adapters: list[NotificationAdapter] | None = None) -> None:
        self.adapters = adapters or [ConsoleNotification()]

    async def publish(self, subject: str, message: str) -> None:
        for adapter in self.adapters:
            try:
                await adapter.send(subject, message)
            except Exception:
                logger.exception("Notification adapter failed for subject '%s'", subject)
