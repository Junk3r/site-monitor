import os

from pathlib import Path

import yaml

from dotenv import load_dotenv

from site_monitor.schemas.site import Site


BASE_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = BASE_DIR.parent.parent


def load_config():

    load_dotenv(PROJECT_ROOT / ".env")

    config_path = BASE_DIR / "settings.yaml"

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as file:
        data = yaml.safe_load(file)


    sites = [
        Site(**site)
        for site in data["sites"]
    ]

    telegram = {
        "enabled": data["telegram"]["enabled"],
        "token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    }

    return {
        "app": data["app"],
        "monitor": data["monitor"],
        "database": data["database"],
        "telegram": telegram,
        "keywords": data["keywords"],
        "sites": sites,
    }
