import argparse
import asyncio

from loguru import logger

from site_monitor.monitor.monitor import Monitor
from site_monitor.storage.database import init_database
from site_monitor.config.loader import load_config


def parse_args(argv=None):

    parser = argparse.ArgumentParser(
        prog="site-monitor",
        description=(
            "Collect vacancies from careers pages, filter them by rules "
            "and a local LLM, send new ones to Telegram."
        ),
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="run a single pass instead of looping",
    )

    parser.add_argument(
        "--from-db",
        action="store_true",
        help="re-read stored snapshots without fetching",
    )

    parser.add_argument(
        "--site",
        action="append",
        metavar="NAME",
        help="check only this site (repeatable)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="log results instead of sending them to Telegram",
    )

    parser.add_argument(
        "--min-score",
        type=int,
        metavar="N",
        help="only send vacancies scored N or higher",
    )

    # previous name of --once
    parser.add_argument(
        "--scan-existing",
        dest="once",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    return parser.parse_args(argv)


def apply_args(config, args):

    if args.dry_run:

        config["telegram"]["enabled"] = False

        # в отличие от telegram.enabled: false, разовая проверка не
        # должна съедать очередь ещё не отправленных вакансий
        config["telegram"]["dry_run"] = True

        logger.info(
            "Dry run: Telegram disabled, nothing will be marked as sent"
        )


    if args.min_score is not None:
        config["telegram"]["min_score"] = args.min_score


    if args.site:

        wanted = {name.lower() for name in args.site}

        config["sites"] = [
            site
            for site in config["sites"]
            if site.name.lower() in wanted
        ]

        if not config["sites"]:

            raise SystemExit(
                f"No sites matched {sorted(wanted)}"
            )

        logger.info(
            f"Limited to {len(config['sites'])} site(s)"
        )


    return config


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

        # это вся очередь неотправленного, а не только найденное сейчас
        logger.info(
            f"Done: {len(found)} opportunities reported"
        )

    finally:

        await monitor.stop(browser=browser)


async def main(argv=None):

    args = parse_args(argv)

    logger.info("Site Monitor started")

    config = apply_args(
        load_config(),
        args,
    )

    init_database(
        config["database"]["url"]
    )

    if args.once or args.from_db:

        await run_once(config, from_db=args.from_db)

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
