import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "SauceStickers"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Baked alignment for XP-365B + 40 mm round labels (site photos Sep 2026).
# Gap 2.75 → content low (feed long) → 2.5.
# Same strip: block right+low → X left, Y up (negative).
BAKED_OFFSET_X_MM = -2.5
BAKED_OFFSET_Y_MM = -3.5
BAKED_LABEL_GAP_MM = 2.5
# Bump to re-apply baked values once on each site after an alignment release.
ALIGNMENT_REV = 10


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


def ensure_alignment_defaults() -> None:
    """Force gap/X/Y from this release once (overwrites old site fiddling)."""
    config = load_config()
    if int(config.get("alignment_rev", 0) or 0) >= ALIGNMENT_REV:
        return
    config["print_offset_x_mm"] = BAKED_OFFSET_X_MM
    config["print_offset_y_mm"] = BAKED_OFFSET_Y_MM
    config["label_gap_mm"] = BAKED_LABEL_GAP_MM
    config["sensor_from_left_mm"] = 0.0
    config["tspl_mode"] = True
    config["alignment_rev"] = ALIGNMENT_REV
    save_config(config)


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
    ensure_alignment_defaults()
    data = load_config()
    try:
        x = float(data.get("print_offset_x_mm", BAKED_OFFSET_X_MM) or 0)
    except (TypeError, ValueError):
        x = BAKED_OFFSET_X_MM
    try:
        y = float(data.get("print_offset_y_mm", BAKED_OFFSET_Y_MM) or 0)
    except (TypeError, ValueError):
        y = BAKED_OFFSET_Y_MM
    return x, y


def set_print_offset_mm(x_mm: float, y_mm: float = 0.0) -> None:
    config = load_config()
    config["print_offset_x_mm"] = round(float(x_mm), 2)
    config["print_offset_y_mm"] = round(float(y_mm), 2)
    save_config(config)


def get_label_gap_mm() -> float:
    ensure_alignment_defaults()
    data = load_config()
    try:
        return max(0.0, float(data.get("label_gap_mm", BAKED_LABEL_GAP_MM) or 0))
    except (TypeError, ValueError):
        return BAKED_LABEL_GAP_MM


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


def get_sensor_from_left_mm() -> float:
    return 0.0


def set_sensor_from_left_mm(mm: float) -> None:
    config = load_config()
    config["sensor_from_left_mm"] = round(max(0.0, float(mm)), 2)
    save_config(config)
