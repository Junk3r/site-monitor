import asyncio
import sys

from loguru import logger

from site_monitor.monitor.monitor import Monitor
from site_monitor.storage.database import init_database
from site_monitor.config.loader import load_config


async def run_cycle(config):

    monitor = Monitor(config)

    await monitor.start()

    try:

        await monitor.check_all(
            config["sites"]
        )

    finally:

        await monitor.stop()


async def run_scan(config):

    monitor = Monitor(config)

    await monitor.start()

    try:

        events = await monitor.scan_all(
            config["sites"]
        )

        logger.info(
            f"Scan complete: {len(events)} opportunities"
        )

    finally:

        await monitor.stop()


async def main():

    logger.info(
        "Site Monitor started"
    )

    init_database()

    config = load_config()

    if "--scan-existing" in sys.argv:

        await run_scan(config)

        return

    interval_seconds = (
        config["monitor"]["interval_minutes"] * 60
    )

    while True:

        await run_cycle(config)

        logger.info(
            f"Cycle complete, next check in "
            f"{config['monitor']['interval_minutes']} minutes"
        )

        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    asyncio.run(main())
