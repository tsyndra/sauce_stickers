"""Render 40 mm round sauce labels at 203 DPI for XP-365B."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from sauces import STORAGE_ARC, SAUCES
from desserts import BRAND, DESSERTS

DPI = 203
LABEL_MM = 40
SIZE_PX = round(LABEL_MM / 25.4 * DPI)
RENDER_SCALE = 6
EDGE_INSET_MM = 0.8
ARC_TEXT_INSET_MM = 2.2
COMPOSITION_FONT_SIZE = 13
STORAGE_ARC_SPAN_DEG = 130
COMPOSITION_ARC_SPAN_DEG = 185
COMPOSITION_MIN_SIZE = 9
SHELF_LIFE = timedelta(days=1) - timedelta(minutes=1)
BODY_FONT_SIZE = 16
STORAGE_ARC_START = 16
STORAGE_ARC_MIN = 13
# Bottom arc stays a bit smaller than top (like the good physical print).
COMPOSITION_SMALLER_THAN_TOP = 2
TITLE_MAX = 30
TITLE_MIN = 15
BODY_GAP = 3
TITLE_BODY_GAP = 8
# Soft AA → solid black for thermal with smoothing «Нет» (gray would vanish into holes).
PRINT_BLACK_BELOW = 205
# Intermediate supersample before final 203 DPI (smoother curves, then BOX down).
PRINT_OVERSAMPLE = 2

FONT_REGULAR = "C:/Windows/Fonts/arial.ttf"
FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_REGULAR_FALLBACKS = [
    FONT_REGULAR,
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/seguisb.ttf",
]
FONT_BOLD_FALLBACKS = [
    FONT_BOLD,
    "C:/Windows/Fonts/ariblk.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/tahomabd.ttf",
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


def _arc_fits(text: str, arc_span_deg: float, radius: float, font: ImageFont.ImageFont) -> bool:
    arc_length = math.radians(arc_span_deg) * radius
    return _text_width(font, text) <= arc_length * 0.96


def _fit_arc_font(
    text: str,
    arc_span_deg: float,
    radius: float,
    start_size: int,
    min_size: int,
    *,
    bold: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(start_size, min_size - 1, -1):
        font = _load_font(size, bold=bold)
        if _arc_fits(text, arc_span_deg, radius, font):
            return font
    return _load_font(min_size, bold=bold)


def _fit_title_font(title: str, max_width: float) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(TITLE_MAX, TITLE_MIN - 1, -1):
        font = _load_font(size, bold=True)
        if _text_width(font, title) <= max_width:
            return font
    return _load_font(TITLE_MIN, bold=True)


def _to_print_image(masked_gray: Image.Image, *, tight_close: bool = True) -> Image.Image:
    """Hi-res soft → solid B/W at 2× DPI → optional hole-close → BOX to printer DPI.

    Thermal with smoothing «Нет» needs pure black/white; gray AA becomes striped dither.
    tight_close fills 1px holes in sauce arcs; desserts skip it so letters don't fuse.
    """
    mid_size = SIZE_PX * PRINT_OVERSAMPLE
    soft = masked_gray.resize((mid_size, mid_size), Image.Resampling.LANCZOS)
    solid = soft.point(lambda p: 0 if p < PRINT_BLACK_BELOW else 255)
    if tight_close:
        # Morphological close: fill single-pixel gaps (sauces/arcs).
        solid = solid.filter(ImageFilter.MinFilter(3))
        solid = solid.filter(ImageFilter.MaxFilter(3))
    down = solid.resize((SIZE_PX, SIZE_PX), Image.Resampling.BOX)
    return down.point(lambda p: 0 if p < 128 else 255).convert("RGB")


def _spaced_text_width(
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    text: str,
    tracking: float,
) -> float:
    if not text:
        return 0.0
    return sum(_char_width(font, ch) for ch in text) + tracking * max(0, len(text) - 1)


def _draw_centered_spaced(
    draw: ImageDraw.ImageDraw,
    cx: float,
    y: float,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    tracking: float,
) -> None:
    total_w = _spaced_text_width(font, text, tracking)
    x = cx - total_w / 2
    for ch in text:
        draw.text((x, y), ch, font=font, fill=(0, 0, 0, 255))
        x += _char_width(font, ch) + tracking


def _draw_arc_text(
    image: Image.Image,
    text: str,
    center: tuple[float, float],
    radius: float,
    center_deg: float,
    max_span_deg: float,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    """Warp a whole text strip onto an arc (no per-glyph rotate — that shreds thermal print)."""
    if not text:
        return

    cx, cy = center
    text_w = _text_width(font, text)
    if text_w <= 0:
        return

    bbox = font.getbbox(text)
    pad_x = max(4, int(font.size * 0.15))
    pad_y = max(4, int(font.size * 0.25))
    strip_w = int(math.ceil(text_w)) + pad_x * 2
    strip_h = (bbox[3] - bbox[1]) + pad_y * 2
    if strip_w < 2 or strip_h < 2:
        return

    strip = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))
    strip_draw = ImageDraw.Draw(strip)
    # Keep existing 1px outline (not thicker).
    tx, ty = pad_x, pad_y - bbox[1]
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        strip_draw.text((tx + dx, ty + dy), text, font=font, fill=(0, 0, 0, 255))

    used_span = math.degrees(text_w / radius)
    if used_span > max_span_deg * 1.08:
        used_span = max_span_deg
    arc_start = center_deg - used_span / 2
    arc_end = center_deg + used_span / 2

    half_h = strip_h / 2.0
    r_inner = radius - half_h - 2
    r_outer = radius + half_h + 2

    # Bounding box of the annular sector (loose).
    margin = int(r_outer) + 2
    x0 = max(0, int(cx - margin))
    y0 = max(0, int(cy - margin))
    x1 = min(image.width, int(cx + margin) + 1)
    y1 = min(image.height, int(cy + margin) + 1)

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    out = overlay.load()
    src = strip.load()
    sw, sh = strip.size

    span = arc_end - arc_start
    if abs(span) < 1e-6:
        return

    def angle_in_span(deg: float) -> float | None:
        """Map angle into [arc_start, arc_end]; return t in [0,1] or None."""
        # Normalize relative distance along shortest compatible path.
        d = (deg - arc_start) % 360.0
        if span < 0:
            return None
        if d <= span:
            return d / span
        # Also accept tiny numeric overshoot
        if d > 360.0 - 0.5:
            return 0.0
        return None

    for y in range(y0, y1):
        for x in range(x0, x1):
            dx = x + 0.5 - cx
            dy = y + 0.5 - cy
            r = math.hypot(dx, dy)
            if r < r_inner or r > r_outer:
                continue

            ang = math.degrees(math.atan2(dy, dx))
            t = angle_in_span(ang)
            if t is None:
                continue

            # u along strip; v radial (toward center = up on strip, same as old rotate+90).
            u = pad_x + t * text_w
            v = half_h + (radius - r)

            if u < 0 or v < 0 or u >= sw - 1 or v >= sh - 1:
                continue

            # Bilinear sample of black text with AA alpha.
            ui = int(u)
            vi = int(v)
            fu = u - ui
            fv = v - vi
            a00 = src[ui, vi][3]
            a10 = src[ui + 1, vi][3]
            a01 = src[ui, vi + 1][3]
            a11 = src[ui + 1, vi + 1][3]
            a = (
                a00 * (1 - fu) * (1 - fv)
                + a10 * fu * (1 - fv)
                + a01 * (1 - fu) * fv
                + a11 * fu * fv
            )
            if a < 8:
                continue
            out[x, y] = (0, 0, 0, int(a))

    image.alpha_composite(overlay)

def _split_composition(text: str) -> tuple[str, str]:
    """Split long ingredients near the middle at a comma."""
    body = text
    prefix = ""
    if text.startswith("Состав: "):
        prefix = "Состав: "
        body = text[len(prefix) :]

    target = len(body) // 2
    best = -1
    for i, ch in enumerate(body):
        if ch == "," and abs(i - target) < abs(best - target):
            best = i
    if best < 0:
        best = target

    left = prefix + body[: best + 1].rstrip()
    right = body[best + 1 :].lstrip()
    return left, right


def _font_logical_size(font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    return max(1, int(round(getattr(font, "size", RENDER_SCALE) / RENDER_SCALE)))


def _draw_composition_arc(
    image: Image.Image,
    composition_text: str,
    center: tuple[float, float],
    canvas: float,
    outer_radius: float,
    max_size: int,
) -> None:
    """Bottom arc — always <= max_size (kept smaller than the top storage arc)."""
    cx, cy = center
    radius = outer_radius - (ARC_TEXT_INSET_MM / LABEL_MM * canvas)
    max_size = max(COMPOSITION_MIN_SIZE, min(max_size, COMPOSITION_FONT_SIZE))

    def pick_font(text: str, r: float, start: int) -> tuple[ImageFont.ImageFont, float]:
        for size in range(start, COMPOSITION_MIN_SIZE - 1, -1):
            font = _load_font(size, bold=True)
            draw_r = r - font.size * 0.35
            if _arc_fits(text, COMPOSITION_ARC_SPAN_DEG, draw_r, font):
                return font, draw_r
        font = _load_font(COMPOSITION_MIN_SIZE, bold=True)
        return font, r - font.size * 0.35

    font, draw_r = pick_font(composition_text, radius, max_size)
    if _arc_fits(composition_text, COMPOSITION_ARC_SPAN_DEG, draw_r, font):
        _draw_arc_text(
            image,
            composition_text,
            (cx, cy),
            draw_r,
            90,
            COMPOSITION_ARC_SPAN_DEG,
            font,
        )
        return

    line1, line2 = _split_composition(composition_text)
    outer_font, r1 = pick_font(line1, radius, max_size)
    _draw_arc_text(image, line1, (cx, cy), r1, 90, COMPOSITION_ARC_SPAN_DEG, outer_font)

    r2_base = r1 - outer_font.size * 1.05
    inner_font, r2 = pick_font(line2, r2_base, max_size)
    _draw_arc_text(image, line2, (cx, cy), r2, 90, COMPOSITION_ARC_SPAN_DEG, inner_font)


def render_label(sauce_id: str, manufactured_at: datetime | None = None) -> Image.Image:
    sauce = SAUCES[sauce_id]
    manufactured_at = manufactured_at or datetime.now()
    expires_at = manufactured_at + SHELF_LIFE

    canvas = _s(SIZE_PX)
    cx = cy = canvas / 2
    radius_mm = LABEL_MM / 2 - EDGE_INSET_MM
    outer_radius = radius_mm / LABEL_MM * canvas

    image = Image.new("RGBA", (canvas, canvas), (255, 255, 255, 255))

    arc_radius = outer_radius - (ARC_TEXT_INSET_MM / LABEL_MM * canvas)
    storage_font = _fit_arc_font(
        STORAGE_ARC,
        STORAGE_ARC_SPAN_DEG,
        arc_radius,
        STORAGE_ARC_START,
        STORAGE_ARC_MIN,
        bold=True,
    )
    arc_radius -= storage_font.size * 0.4

    _draw_arc_text(
        image,
        STORAGE_ARC,
        (cx, cy),
        arc_radius,
        270,
        STORAGE_ARC_SPAN_DEG,
        storage_font,
    )

    composition = sauce["composition"].strip()
    if composition:
        storage_logical = _font_logical_size(storage_font)
        comp_max = storage_logical - COMPOSITION_SMALLER_THAN_TOP
        _draw_composition_arc(
            image,
            f"Состав: {composition}",
            (cx, cy),
            canvas,
            outer_radius,
            max_size=comp_max,
        )

    draw = ImageDraw.Draw(image)

    title = sauce["label_title"]
    title_font = _fit_title_font(title, outer_radius * 1.35)
    title_w = _text_width(title_font, title)
    title_h = _text_height(title_font, title)

    body_font = _load_font(BODY_FONT_SIZE, bold=True)
    lines = [
        f"Изготовлен: {_format_datetime(manufactured_at)}",
        f"Годен до: {_format_datetime(expires_at)}",
        f"масса нетто: {sauce['weight_g']}гр.",
    ]
    line_heights = [_text_height(body_font, line) for line in lines]
    body_gap = _s(BODY_GAP)
    body_block_h = sum(line_heights) + body_gap * (len(lines) - 1)

    block_h = title_h + _s(TITLE_BODY_GAP) + body_block_h
    block_top = cy - block_h / 2 - _s(2)

    draw.text((cx - title_w / 2, block_top), title, font=title_font, fill=(0, 0, 0, 255))
    current_y = block_top + title_h + _s(TITLE_BODY_GAP)
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

    return _to_print_image(masked)


def _format_dessert_datetime(dt: datetime) -> str:
    return f"{dt.strftime('%d.%m.%Y')}   {dt.strftime('%H:%M')}"


def _wrap_centered_lines(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: float,
    max_lines: int = 3,
) -> list[str]:
    words = text.split()
    if not words:
        return [text]

    lines: list[str] = []
    current_words: list[str] = []

    for i, word in enumerate(words):
        trial_words = [*current_words, word]
        trial = " ".join(trial_words)
        if not current_words or _text_width(font, trial) <= max_width:
            current_words = trial_words
            continue

        lines.append(" ".join(current_words))
        if len(lines) >= max_lines - 1:
            lines.append(" ".join(words[i:]))
            return lines[:max_lines]
        current_words = [word]

    if current_words:
        lines.append(" ".join(current_words))
    return lines[:max_lines]


def _fit_dessert_title_font(
    title: str, max_width: float
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str]]:
    # Long titles: prefer 2 lines at a larger size over one cramped line.
    if len(title) >= 22:
        for size in range(18, 12, -1):
            font = _load_font(size, bold=False)
            lines = _wrap_centered_lines(title, font, max_width * 0.98, max_lines=2)
            if len(lines) >= 2 and all(
                _text_width(font, line) <= max_width * 1.01 for line in lines
            ):
                return font, lines

    for size in range(20, 12, -1):
        font = _load_font(size, bold=False)
        if _text_width(font, title) <= max_width:
            return font, [title]
    for size in range(18, 11, -1):
        font = _load_font(size, bold=False)
        lines = _wrap_centered_lines(title, font, max_width, max_lines=3)
        if all(_text_width(font, line) <= max_width * 1.02 for line in lines):
            return font, lines
    font = _load_font(11, bold=False)
    return font, _wrap_centered_lines(title, font, max_width, max_lines=3)


def render_dessert_label(
    dessert_id: str,
    defrosted_at: datetime | None = None,
    *,
    legal_entity: str,
) -> Image.Image:
    """Round HATIMAKI dessert label: brand, title, defrost/expiry, storage, legal."""
    dessert = DESSERTS[dessert_id]
    defrosted_at = defrosted_at or datetime.now()
    expires_at = defrosted_at + dessert["shelf_life"]
    legal_entity = legal_entity.strip()
    if not legal_entity:
        raise ValueError("Не выбран ИП филиала")

    canvas = _s(SIZE_PX)
    cx = cy = canvas / 2
    radius_mm = LABEL_MM / 2 - EDGE_INSET_MM
    outer_radius = radius_mm / LABEL_MM * canvas
    content_width = outer_radius * 1.55

    image = Image.new("RGBA", (canvas, canvas), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)

    brand_font = _load_font(14, bold=False)
    meta_font = _load_font(12, bold=False)
    date_font = _load_font(13, bold=False)
    storage_font = _load_font(11, bold=False)
    legal_font = _load_font(11, bold=False)
    title_font, title_lines = _fit_dessert_title_font(dessert["label_title"], content_width)

    gap_sm = _s(5)
    gap_md = _s(9)
    gap_lg = _s(11)

    blocks: list[tuple[str, ImageFont.ImageFont, int]] = []
    blocks.append((BRAND, brand_font, gap_md))
    for i, line in enumerate(title_lines):
        after = gap_lg if i == len(title_lines) - 1 else gap_sm
        blocks.append((line, title_font, after))
    blocks.append(("Разморожен:", meta_font, gap_sm))
    blocks.append((_format_dessert_datetime(defrosted_at), date_font, gap_md))
    blocks.append(("Годен до:", meta_font, gap_sm))
    blocks.append((_format_dessert_datetime(expires_at), date_font, gap_md))
    blocks.append((dessert["storage"], storage_font, gap_md))
    blocks.append((legal_entity, legal_font, 0))

    heights = [_text_height(font, text) for text, font, _ in blocks]
    total_h = sum(heights) + sum(gap for _, _, gap in blocks[:-1])
    y = cy - total_h / 2

    for (text, font, gap), h in zip(blocks, heights):
        tw = _text_width(font, text)
        draw.text((cx - tw / 2, y), text, font=font, fill=(0, 0, 0, 255))
        y += h + gap

    mask = Image.new("L", (canvas, canvas), 0)
    mask_draw = ImageDraw.Draw(mask)
    inset = (LABEL_MM / 2 - radius_mm) / LABEL_MM * canvas
    mask_draw.ellipse((inset, inset, canvas - inset, canvas - inset), fill=255)

    gray = image.convert("L")
    masked = Image.new("L", (canvas, canvas), 255)
    masked.paste(gray, mask=mask)

    # Solid B/W for thermal (no gray AA dither stripes); no morph close (keeps kerning).
    return _to_print_image(masked, tight_close=False)
