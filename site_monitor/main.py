import asyncio
import sys

from loguru import logger

from site_monitor.monitor.monitor import Monitor
from site_monitor.storage.database import init_database
from site_monitor.config.loader import load_config


async def run_once(config, from_db: bool = False):

    monitor = Monitor(config)

    # снимкам из базы браузер не нужен
    browser = not from_db

    await monitor.start(browser=browser)

    try:

        found = await monitor.run(
            config["sites"],
            from_db=from_db,
        )

        logger.info(
            f"Done: {len(found)} new opportunities"
        )

    finally:

        await monitor.stop(browser=browser)


async def main():

    logger.info(
        "Site Monitor started"
    )

    init_database()

    config = load_config()

    from_db = "--from-db" in sys.argv

    if from_db or "--scan-existing" in sys.argv or "--once" in sys.argv:

        await run_once(config, from_db=from_db)

        return


    interval_seconds = (
        config["monitor"]["interval_minutes"] * 60
    )

    while True:

        await run_once(config)

        logger.info(
            f"Cycle complete, next check in "
            f"{config['monitor']['interval_minutes']} minutes"
        )

        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    asyncio.run(main())
