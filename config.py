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


def get_print_offset_mm() -> tuple[float, float]:
    data = load_config()
    # Photo: content shifted left + up → +X right, +Y down.
    if "print_offset_x_mm" not in data and "print_offset_y_mm" not in data:
        return 2.0, 2.5
    try:
        x = float(data.get("print_offset_x_mm", 0) or 0)
    except (TypeError, ValueError):
        x = 0.0
    try:
        y = float(data.get("print_offset_y_mm", 0) or 0)
    except (TypeError, ValueError):
        y = 0.0
    return x, y


def set_print_offset_mm(x_mm: float, y_mm: float = 0.0) -> None:
    config = load_config()
    config["print_offset_x_mm"] = round(float(x_mm), 2)
    config["print_offset_y_mm"] = round(float(y_mm), 2)
    save_config(config)


def get_label_gap_mm() -> float:
    data = load_config()
    default = 2.625
    if "label_gap_mm" not in data:
        return default
    try:
        gap = max(0.0, float(data.get("label_gap_mm", default) or 0))
    except (TypeError, ValueError):
        return default
    # Old default 3.0 didn't match the physical roll gap.
    if abs(gap - 3.0) < 0.05:
        return default
    return gap


def get_tspl_mode() -> bool:
    """Direct TSPL printing (XP-365B native) instead of the Windows GDI driver."""
    value = load_config().get("tspl_mode", True)
    return bool(value)


def set_tspl_mode(enabled: bool) -> None:
    config = load_config()
    config["tspl_mode"] = bool(enabled)
    save_config(config)


def get_tspl_direction() -> int:
    """TSPL DIRECTION (0/1) — flip if labels come out upside down."""
    try:
        return 1 if int(load_config().get("tspl_direction", 1)) else 0
    except (TypeError, ValueError):
        return 1


def set_label_gap_mm(gap_mm: float) -> None:
    config = load_config()
    config["label_gap_mm"] = round(max(0.0, float(gap_mm)), 3)
    save_config(config)
