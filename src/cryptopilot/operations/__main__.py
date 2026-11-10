"""Run the continuous paper-trading daemon with ``python -m cryptopilot.operations``."""

import asyncio

from cryptopilot.config.settings import get_settings
from cryptopilot.operations.daemon import TradingDaemon
from cryptopilot.operations.logging import configure_logging


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file_path)
    daemon = TradingDaemon(cycle_interval_seconds=settings.daemon_cycle_interval_seconds)
    await daemon.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
