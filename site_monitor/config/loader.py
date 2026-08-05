import os

from pathlib import Path

import yaml

from dotenv import load_dotenv
from loguru import logger

from site_monitor.schemas.site import Site


BASE_DIR = Path(__file__).resolve().parent

PROJECT_ROOT = BASE_DIR.parent.parent

PROFILE_PATH = BASE_DIR / "profile.yaml"

PROFILE_EXAMPLE_PATH = BASE_DIR / "profile.yaml.example"


def load_profile() -> dict:
    """Профиль кандидата держится вне репозитория: это личные данные,
    а не настройка приложения."""

    path = PROFILE_PATH

    if not path.exists():

        logger.warning(
            f"{path.name} not found, falling back to "
            f"{PROFILE_EXAMPLE_PATH.name} — AI scores will be meaningless "
            f"until you copy it and describe yourself"
        )

        path = PROFILE_EXAMPLE_PATH


    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:
        data = yaml.safe_load(file) or {}


    return {
        "candidate": data.get("candidate", ""),
        "scale": data.get("scale", ""),
    }


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
        "min_score": data["telegram"].get("min_score", 0),
    }

    return {
        "app": data["app"],
        "monitor": data["monitor"],
        "database": data["database"],
        "telegram": telegram,
        "ai": data.get("ai", {"enabled": False}),
        "keywords": data["keywords"],
        "profile": load_profile(),
        "sites": sites,
    }
