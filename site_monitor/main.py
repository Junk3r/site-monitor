import asyncio

from loguru import logger

from site_monitor.monitor.monitor import Monitor
from site_monitor.storage.database import init_database
from site_monitor.config.loader import load_config


async def main():

    logger.info(
        "Site Monitor started"
    )

    init_database()

    config = load_config()

    monitor = Monitor()

    await monitor.start()

    try:

        await monitor.check_all(
            config["sites"]
        )

    finally:

        await monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())