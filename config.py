import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "SauceStickers"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with CONFIG_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_last_printer() -> str | None:
    return load_config().get("last_printer")


def set_last_printer(printer_name: str) -> None:
    config = load_config()
    config["last_printer"] = printer_name
    save_config(config)


def get_legal_entity() -> str | None:
    value = load_config().get("legal_entity")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def set_legal_entity(legal_entity: str) -> None:
    config = load_config()
    config["legal_entity"] = legal_entity.strip()
    save_config(config)


def get_update_base() -> str | None:
    value = load_config().get("update_base")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def set_update_base(update_base: str) -> None:
    config = load_config()
    config["update_base"] = update_base.strip()
    save_config(config)
