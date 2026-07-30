from pathlib import Path
import yaml

from site_monitor.schemas.site import Site


BASE_DIR = Path(__file__).resolve().parent


def load_config():

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

    return {
        "app": data["app"],
        "monitor": data["monitor"],
        "database": data["database"],
        "telegram": data["telegram"],
        "sites": sites,
    }