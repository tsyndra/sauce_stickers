"""Print label images to a Windows printer via GDI."""

from __future__ import annotations

import pywintypes
import win32con
import win32gui
import win32print
import win32ui
from PIL import Image, ImageWin

# Must match label_renderer.LABEL_MM / intended physical size.
LABEL_MM = 40
# Typical die-cut gap on 40 mm round rolls (UI «Зазор»); pitch = label + gap.
DEFAULT_LABEL_GAP_MM = 2.875
# EnumForms sizes are in thousandths of a millimeter.
_FORM_TOLERANCE = 1200  # ~1.2 mm
_FORM_NAME_PREFIX = "SauceStickers"
# XP-365B: 203 dpi ≈ 8 dots/mm (TSPL coordinates are in dots).
TSPL_DOTS_PER_MM = 8


def list_printers() -> list[str]:
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    printers = win32print.EnumPrinters(flags)
    return [name for _, _, name, _ in printers]


def open_printer_preferences(printer_name: str, hwnd: int = 0) -> None:
    """Open the Windows printing preferences dialog for the selected printer."""
    if not printer_name.strip():
        raise ValueError("Принтер не выбран")

    hprinter = win32print.OpenPrinter(printer_name)
    try:
        properties = win32print.GetPrinter(hprinter, 2)
        devmode = properties.get("pDevMode")
        if devmode is None:
            raise RuntimeError("Не удалось получить настройки принтера")

        result = win32print.DocumentProperties(
            hwnd,
            hprinter,
            printer_name,
            devmode,
            devmode,
            win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER | win32con.DM_IN_PROMPT,
        )
        if result != win32con.IDOK:
            return

        # Persist user choices (paper size, smoothing, etc.) for this PC/printer.
        properties["pDevMode"] = devmode
        try:
            win32print.SetPrinter(hprinter, 2, properties, 0)
        except pywintypes.error:
            # Shared/network printers may deny saving defaults; dialog still applied for session.
            pass
    finally:
        win32print.ClosePrinter(hprinter)


def _find_label_form_name(hprinter, pitch_mm: float) -> str | None:
    try:
        forms = win32print.EnumForms(hprinter)
    except pywintypes.error:
        return None

    target_w = LABEL_MM * 1000
    target_h = pitch_mm * 1000
    best_name = None
    best_score = None
    for form in forms:
        size = form.get("Size") or {}
        width = size.get("cx", 0)
        height = size.get("cy", 0)
        if abs(width - target_w) > _FORM_TOLERANCE:
            continue
        score = abs(height - target_h)
        if score <= _FORM_TOLERANCE and (best_score is None or score < best_score):
            name = form.get("Name")
            if name:
                best_name = name
                best_score = score
    return best_name


def _ensure_label_form(hprinter, pitch_mm: float) -> str | None:
    """Create/update a Windows form = 40 mm × (40 + gap) so the spooler feeds pitch."""
    pitch_mm = max(float(LABEL_MM), float(pitch_mm))
    existing = _find_label_form_name(hprinter, pitch_mm)
    if existing:
        return existing

    target_w = int(LABEL_MM * 1000)
    target_h = max(1, int(round(pitch_mm * 1000)))
    name = f"{_FORM_NAME_PREFIX} {LABEL_MM}x{pitch_mm:.1f}".rstrip("0").rstrip(".")
    form = {
        "Flags": 0,
        "Name": name,
        "Size": {"cx": target_w, "cy": target_h},
        "ImageableArea": {
            "left": 0,
            "top": 0,
            "right": target_w,
            "bottom": target_h,
        },
    }
    try:
        win32print.AddForm(hprinter, form)
    except Exception:
        # Name collision with wrong size / no rights — try delete+add, else give up.
        try:
            win32print.DeleteForm(hprinter, name)
            win32print.AddForm(hprinter, form)
        except Exception:
            return _find_label_form_name(hprinter, pitch_mm)
    return _find_label_form_name(hprinter, pitch_mm) or name


def _apply_label_paper(devmode, form_name: str | None, gap_mm: float) -> None:
    """Force label width×pitch (label + gap) on a DEVMODE."""
    pitch_mm = LABEL_MM + max(0.0, gap_mm)
    paper_w = LABEL_MM * 10
    paper_h = max(1, round(pitch_mm * 10))

    if form_name:
        try:
            devmode.FormName = form_name
            devmode.Fields |= win32con.DM_FORMNAME
        except (AttributeError, TypeError):
            pass

    try:
        devmode.PaperSize = getattr(win32con, "DMPAPER_USER", 256)
        devmode.PaperWidth = paper_w
        devmode.PaperLength = paper_h
        devmode.Fields |= (
            win32con.DM_PAPERSIZE | win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH
        )
    except (AttributeError, TypeError):
        pass

    try:
        if getattr(devmode, "Fields", 0) & win32con.DM_ORIENTATION:
            devmode.Orientation = win32con.DMORIENT_PORTRAIT
            devmode.Fields |= win32con.DM_ORIENTATION
    except (AttributeError, TypeError):
        pass


def _devmode_for_label(printer_name: str, gap_mm: float = DEFAULT_LABEL_GAP_MM):
    """Build a printer DEVMODE with label + gap pitch for this job."""
    hprinter = win32print.OpenPrinter(printer_name)
    try:
        properties = win32print.GetPrinter(hprinter, 2)
        devmode = properties.get("pDevMode")
        if devmode is None:
            return None

        pitch_mm = LABEL_MM + max(0.0, gap_mm)
        try:
            form_name = _ensure_label_form(hprinter, pitch_mm)
        except Exception:
            form_name = None
        _apply_label_paper(devmode, form_name, gap_mm)

        try:
            win32print.DocumentProperties(
                0,
                hprinter,
                printer_name,
                devmode,
                devmode,
                win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER,
            )
        except pywintypes.error:
            pass

        _apply_label_paper(devmode, form_name, gap_mm)
        return devmode
    except pywintypes.error:
        return None
    finally:
        win32print.ClosePrinter(hprinter)


def _create_printer_dc(printer_name: str, gap_mm: float = DEFAULT_LABEL_GAP_MM):
    """Create a printer DC with label+gap DEVMODE when possible."""
    devmode = _devmode_for_label(printer_name, gap_mm=gap_mm)
    if devmode is not None:
        try:
            handle = win32gui.CreateDC("WINSPOOL", printer_name, None, devmode)
            return win32ui.CreateDCFromHandle(handle)
        except Exception:
            pass

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    return hdc


def inspect_printer(
    printer_name: str, *, gap_mm: float = DEFAULT_LABEL_GAP_MM
) -> dict:
    """Read effective paper size / DPI after applying label+gap DEVMODE."""
    if not printer_name.strip():
        raise ValueError("Принтер не выбран")

    pitch_mm = LABEL_MM + max(0.0, gap_mm)
    hdc = _create_printer_dc(printer_name, gap_mm=gap_mm)
    try:
        printable_w = hdc.GetDeviceCaps(win32con.HORZRES)
        printable_h = hdc.GetDeviceCaps(win32con.VERTRES)
        dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX) or 203
        dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY) or 203
        size_w_mm = float(hdc.GetDeviceCaps(win32con.HORZSIZE) or 0)
        size_h_mm = float(hdc.GetDeviceCaps(win32con.VERTSIZE) or 0)
        if size_w_mm <= 0:
            size_w_mm = printable_w * 25.4 / dpi_x
        if size_h_mm <= 0:
            size_h_mm = printable_h * 25.4 / dpi_y
    finally:
        hdc.DeleteDC()

    tol_mm = 2.5
    ok_size = (
        abs(size_w_mm - LABEL_MM) <= tol_mm
        and abs(size_h_mm - pitch_mm) <= tol_mm
    )
    messages: list[str] = []
    if ok_size:
        messages.append(
            f"Шаг ~ {size_w_mm:.0f}x{size_h_mm:.0f} мм (наклейка {LABEL_MM}+зазор) — ок"
        )
    else:
        messages.append(
            f"Шаг сейчас ~ {size_w_mm:.0f}x{size_h_mm:.0f} мм, "
            f"ожидаем {LABEL_MM}x{pitch_mm:.0f} мм (наклейка+зазор)"
        )
    messages.append(f"DPI {dpi_x}x{dpi_y}")

    return {
        "ok": ok_size,
        "paper_mm": (round(size_w_mm, 1), round(size_h_mm, 1)),
        "pitch_mm": round(pitch_mm, 1),
        "dpi": (dpi_x, dpi_y),
        "printable_px": (printable_w, printable_h),
        "messages": messages,
        "summary": "; ".join(messages),
    }


def _label_to_tspl_bitmap(
    image: Image.Image,
    *,
    offset_x_mm: float,
    offset_y_mm: float,
) -> tuple[int, int, bytes]:
    """Return (width_bytes, height, data) for TSPL BITMAP, label sized, 1 = white."""
    side = LABEL_MM * TSPL_DOTS_PER_MM  # 320 dots at 203 dpi
    src = image.convert("L").resize((side, side), Image.Resampling.LANCZOS)
    canvas = Image.new("L", (side, side), 255)
    dx = round(offset_x_mm * TSPL_DOTS_PER_MM)
    dy = round(offset_y_mm * TSPL_DOTS_PER_MM)
    canvas.paste(src, (dx, dy))
    mono = canvas.point(lambda p: 255 if p > 128 else 0).convert("1")
    width_bytes = (side + 7) // 8
    return width_bytes, side, mono.tobytes()


def print_image_tspl(
    printer_name: str,
    image: Image.Image,
    copies: int = 1,
    *,
    offset_x_mm: float = 0.0,
    offset_y_mm: float = 0.0,
    gap_mm: float = DEFAULT_LABEL_GAP_MM,
    direction: int = 1,
) -> None:
    """Send raw TSPL with fixed pitch (label + gap).

    XP-365B often fails gap sensing on yellow-liner round labels, so we do NOT
    rely on GAP/sensor. Page height = 40 + gap mm, GAP 0 (continuous). The
    bitmap is only the 40 mm label at the top; blank bottom is the inter-label
    advance. Field «Зазор» = physical gap between die-cuts.
    """
    if copies < 1:
        raise ValueError("Количество копий должно быть не меньше 1")
    if not printer_name.strip():
        raise ValueError("Принтер не выбран")

    gap_mm = max(0.0, float(gap_mm))
    # Pitch in whole dots (203 dpi = 8 dot/mm) — avoids mm rounding underfeed.
    pitch_dots = LABEL_MM * TSPL_DOTS_PER_MM + max(0, round(gap_mm * TSPL_DOTS_PER_MM))
    width_bytes, height, data = _label_to_tspl_bitmap(
        image, offset_x_mm=offset_x_mm, offset_y_mm=offset_y_mm
    )

    # One PRINT per label: fixed motor advance of pitch, no sensor hunt.
    head = (
        f"SIZE {LABEL_MM * TSPL_DOTS_PER_MM} dot,{pitch_dots} dot\r\n"
        "GAP 0 mm,0 mm\r\n"
        f"DIRECTION {1 if direction else 0}\r\n"
        "REFERENCE 0,0\r\n"
        "OFFSET 0 mm\r\n"
        "SET TEAR ON\r\n"
        "CLS\r\n"
        f"BITMAP 0,0,{width_bytes},{height},0,"
    ).encode("ascii")
    body = data + b"\r\nPRINT 1,1\r\n"
    payload = b"".join(head + body for _ in range(copies))
    _send_raw(printer_name, payload)


def _send_raw(printer_name: str, payload: bytes, doc_name: str = "SauceStickers") -> None:
    hprinter = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(hprinter, 1, (doc_name, None, "RAW"))
        try:
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, payload)
            win32print.EndPagePrinter(hprinter)
        finally:
            win32print.EndDocPrinter(hprinter)
    finally:
        win32print.ClosePrinter(hprinter)


def calibrate_gap_tspl(printer_name: str, *, gap_mm: float = DEFAULT_LABEL_GAP_MM) -> None:
    """Ask the printer to measure the roll (feeds 2–3 labels) so it syncs on the gap."""
    if not printer_name.strip():
        raise ValueError("Принтер не выбран")
    gap_mm = max(0.0, float(gap_mm))
    payload = (
        f"SIZE {LABEL_MM} mm,{LABEL_MM} mm\r\n"
        f"GAP {gap_mm:g} mm,0 mm\r\n"
        "GAPDETECT\r\n"
    ).encode("ascii")
    _send_raw(printer_name, payload, "SauceStickers calibrate")


def print_image(
    printer_name: str,
    image: Image.Image,
    copies: int = 1,
    *,
    offset_x_mm: float = 0.0,
    offset_y_mm: float = 0.0,
    gap_mm: float = DEFAULT_LABEL_GAP_MM,
) -> None:
    """Print via Windows GDI driver (fallback when TSPL mode is off)."""
    if copies < 1:
        raise ValueError("Количество копий должно быть не меньше 1")

    gap_mm = max(0.0, float(gap_mm))
    if image.mode != "RGB":
        image = image.convert("RGB")

    # One StartDoc per label: Xprinter gap-sensor re-syncs between jobs.
    # Multi-page inside one job often drifts even when «Зазор» changes.
    for _ in range(copies):
        hdc = _create_printer_dc(printer_name, gap_mm=gap_mm)
        try:
            printable_w = hdc.GetDeviceCaps(win32con.HORZRES)
            printable_h = hdc.GetDeviceCaps(win32con.VERTRES)
            dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX) or 203
            dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY) or 203

            win32gui.SetStretchBltMode(hdc.GetHandleOutput(), win32con.COLORONCOLOR)

            label_w = max(1, round(LABEL_MM / 25.4 * dpi_x))
            label_h = max(1, round(LABEL_MM / 25.4 * dpi_y))

            draw_w = label_w
            draw_h = label_h
            if draw_w > printable_w or draw_h > printable_h:
                scale = min(printable_w / draw_w, printable_h / draw_h)
                draw_w = max(1, int(draw_w * scale))
                draw_h = max(1, int(draw_h * scale))

            # Top-aligned in the page pitch; blank bottom is the inter-label gap
            # when the Windows form/DEVMODE height is label+gap.
            offset_x = (printable_w - draw_w) // 2 + round(offset_x_mm / 25.4 * dpi_x)
            offset_y = round(offset_y_mm / 25.4 * dpi_y)

            hdc.StartDoc("SauceStickers")
            try:
                hdc.StartPage()
                page = Image.new("RGB", (printable_w, printable_h), (255, 255, 255))
                resized = image.resize((draw_w, draw_h), Image.Resampling.LANCZOS)
                page.paste(resized, (max(0, offset_x), max(0, offset_y)))
                dib = ImageWin.Dib(page)
                dib.draw(hdc.GetHandleOutput(), (0, 0, printable_w, printable_h))
                hdc.EndPage()
            finally:
                hdc.EndDoc()
        finally:
            hdc.DeleteDC()
