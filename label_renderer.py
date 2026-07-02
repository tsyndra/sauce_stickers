"""Render 50 mm round sauce labels at 203 DPI for XP-365B."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

from sauces import STORAGE_ARC, SAUCES

DPI = 203
LABEL_MM = 50
SIZE_PX = round(LABEL_MM / 25.4 * DPI)
RENDER_SCALE = 4
EDGE_INSET_MM = 1.0
ARC_TEXT_INSET_MM = 2.2
COMPOSITION_FONT_SIZE = 12
COMPOSITION_ARC_SPAN_DEG = 168

# Rounded casual sans, closest match to the reference label on Windows.
FONT_REGULAR = "C:/Windows/Fonts/comic.ttf"
FONT_BOLD = "C:/Windows/Fonts/comicbd.ttf"
FONT_REGULAR_FALLBACKS = [
    FONT_REGULAR,
    "C:/Windows/Fonts/trebuc.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
FONT_BOLD_FALLBACKS = [
    FONT_BOLD,
    "C:/Windows/Fonts/trebucbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _s(value: float) -> int:
    return max(1, round(value * RENDER_SCALE))


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = _s(size)
    candidates = FONT_BOLD_FALLBACKS if bold else FONT_REGULAR_FALLBACKS

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _format_datetime(dt: datetime) -> str:
    return dt.strftime("%d.%m.%y %H:%M")


def _char_width(font: ImageFont.FreeTypeFont | ImageFont.ImageFont, char: str) -> float:
    if hasattr(font, "getlength"):
        return float(font.getlength(char))
    bbox = font.getbbox(char)
    return bbox[2] - bbox[0]


def _text_width(font: ImageFont.FreeTypeFont | ImageFont.ImageFont, text: str) -> float:
    if hasattr(font, "getlength"):
        return float(font.getlength(text))
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _text_height(font: ImageFont.FreeTypeFont | ImageFont.ImageFont, text: str) -> float:
    bbox = font.getbbox(text)
    return bbox[3] - bbox[1]


def _fit_arc_font(
    text: str,
    arc_span_deg: float,
    radius: float,
    start_size: int,
    min_size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    arc_length = math.radians(arc_span_deg) * radius
    for size in range(start_size, min_size - 1, -1):
        font = _load_font(size, bold=False)
        if _text_width(font, text) <= arc_length * 0.96:
            return font
    return _load_font(min_size, bold=False)


def _fit_title_font(title: str, max_width: float) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(32, 14, -1):
        font = _load_font(size, bold=True)
        if _text_width(font, title) <= max_width:
            return font
    return _load_font(14, bold=True)


def _paste_rgba(base: Image.Image, overlay: Image.Image, x: int, y: int) -> None:
    base.paste(overlay, (x, y), overlay)


def _draw_rotated_char(
    image: Image.Image,
    char: str,
    px: float,
    py: float,
    rotation_deg: float,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    box = _s(font.size * 2.8)
    char_img = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    char_draw = ImageDraw.Draw(char_img)
    char_draw.text((box / 2, box / 2), char, font=font, fill=(0, 0, 0, 255), anchor="mm")

    rotated = char_img.rotate(
        -rotation_deg,
        resample=Image.Resampling.BICUBIC,
        center=(box / 2, box / 2),
    )
    _paste_rgba(image, rotated, int(px - rotated.width / 2), int(py - rotated.height / 2))


def _draw_arc_text(
    image: Image.Image,
    text: str,
    center: tuple[float, float],
    radius: float,
    center_deg: float,
    max_span_deg: float,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    if not text:
        return

    cx, cy = center
    widths = [_char_width(font, ch) for ch in text]
    total_width = sum(widths)
    if total_width <= 0:
        return

    used_span = math.degrees(total_width / radius)
    if used_span > max_span_deg:
        used_span = max_span_deg
    arc_start = center_deg - used_span / 2
    arc_end = center_deg + used_span / 2

    walked = 0.0
    for char, char_w in zip(text, widths):
        mid = walked + char_w / 2
        t = mid / total_width
        angle_deg = arc_start + (arc_end - arc_start) * t
        angle_rad = math.radians(angle_deg)

        px = cx + radius * math.cos(angle_rad)
        py = cy + radius * math.sin(angle_rad)
        rotation_deg = angle_deg + 90

        _draw_rotated_char(image, char, px, py, rotation_deg, font)
        walked += char_w


def render_label(sauce_id: str, manufactured_at: datetime | None = None) -> Image.Image:
    sauce = SAUCES[sauce_id]
    manufactured_at = manufactured_at or datetime.now()
    expires_at = manufactured_at + timedelta(hours=24)

    canvas = _s(SIZE_PX)
    cx = cy = canvas / 2
    radius_mm = LABEL_MM / 2 - EDGE_INSET_MM
    outer_radius = radius_mm / LABEL_MM * canvas

    image = Image.new("RGBA", (canvas, canvas), (255, 255, 255, 255))

    arc_radius = outer_radius - (ARC_TEXT_INSET_MM / LABEL_MM * canvas)
    storage_font = _fit_arc_font(STORAGE_ARC, 158, arc_radius, 14, 10)
    arc_radius -= storage_font.size * 0.4

    _draw_arc_text(image, STORAGE_ARC, (cx, cy), arc_radius, 270, 158, storage_font)

    composition = sauce["composition"].strip()
    if composition:
        composition_text = f"Состав: {composition}"
        bottom_arc_radius = outer_radius - (ARC_TEXT_INSET_MM / LABEL_MM * canvas)
        composition_font = _load_font(COMPOSITION_FONT_SIZE, bold=False)
        bottom_arc_radius -= composition_font.size * 0.4
        _draw_arc_text(
            image,
            composition_text,
            (cx, cy),
            bottom_arc_radius,
            90,
            COMPOSITION_ARC_SPAN_DEG,
            composition_font,
        )

    draw = ImageDraw.Draw(image)

    title = sauce["label_title"]
    title_font = _fit_title_font(title, outer_radius * 1.25)
    title_w = _text_width(title_font, title)
    title_h = _text_height(title_font, title)

    body_font = _load_font(12, bold=False)
    lines = [
        f"Изготовлен: {_format_datetime(manufactured_at)}",
        f"Годен до: {_format_datetime(expires_at)}",
        f"масса нетто: {sauce['weight_g']}гр.",
    ]
    line_heights = [_text_height(body_font, line) for line in lines]
    body_gap = _s(3)
    body_block_h = sum(line_heights) + body_gap * (len(lines) - 1)

    block_h = title_h + _s(8) + body_block_h
    block_top = cy - block_h / 2 - _s(2)

    draw.text((cx - title_w / 2, block_top), title, font=title_font, fill=(0, 0, 0, 255))
    current_y = block_top + title_h + _s(8)
    for line, lh in zip(lines, line_heights):
        lw = _text_width(body_font, line)
        draw.text((cx - lw / 2, current_y), line, font=body_font, fill=(0, 0, 0, 255))
        current_y += lh + body_gap

    mask = Image.new("L", (canvas, canvas), 0)
    mask_draw = ImageDraw.Draw(mask)
    inset = (LABEL_MM / 2 - radius_mm) / LABEL_MM * canvas
    mask_draw.ellipse((inset, inset, canvas - inset, canvas - inset), fill=255)

    gray = image.convert("L")
    masked = Image.new("L", (canvas, canvas), 255)
    masked.paste(gray, mask=mask)

    final = masked.resize((SIZE_PX, SIZE_PX), Image.Resampling.LANCZOS)
    return final.point(lambda p: 0 if p < 128 else 255, mode="1")
