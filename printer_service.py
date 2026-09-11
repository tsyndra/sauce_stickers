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
# Physical pitch = label + gap between die-cuts (stops cumulative drift).
DEFAULT_LABEL_GAP_MM = 3.0
# EnumForms sizes are in thousandths of a millimeter.
_FORM_TOLERANCE = 1200  # ~1.2 mm


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
        form_name = _find_label_form_name(hprinter, pitch_mm)
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


def print_image(
    printer_name: str,
    image: Image.Image,
    copies: int = 1,
    *,
    offset_x_mm: float = 0.0,
    offset_y_mm: float = 0.0,
    gap_mm: float = DEFAULT_LABEL_GAP_MM,
) -> None:
    if copies < 1:
        raise ValueError("Количество копий должно быть не меньше 1")

    gap_mm = max(0.0, float(gap_mm))
    hdc = _create_printer_dc(printer_name, gap_mm=gap_mm)

    try:
        printable_w = hdc.GetDeviceCaps(win32con.HORZRES)
        printable_h = hdc.GetDeviceCaps(win32con.VERTRES)
        dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX) or 203
        dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY) or 203

        if image.mode != "RGB":
            image = image.convert("RGB")

        win32gui.SetStretchBltMode(hdc.GetHandleOutput(), win32con.COLORONCOLOR)

        # Draw only the 40x40 label area; blank remainder is the inter-label gap.
        draw_w = max(1, round(LABEL_MM / 25.4 * dpi_x))
        draw_h = max(1, round(LABEL_MM / 25.4 * dpi_y))

        if draw_w > printable_w or draw_h > printable_h:
            scale = min(printable_w / draw_w, printable_h / draw_h)
            draw_w = max(1, int(draw_w * scale))
            draw_h = max(1, int(draw_h * scale))

        # Top-aligned in the pitch (not vertically centered) + user offsets.
        offset_x = (printable_w - draw_w) // 2 + round(offset_x_mm / 25.4 * dpi_x)
        offset_y = round(offset_y_mm / 25.4 * dpi_y)

        hdc.StartDoc("SauceStickers")
        try:
            for _ in range(copies):
                hdc.StartPage()
                dib = ImageWin.Dib(image)
                dib.draw(
                    hdc.GetHandleOutput(),
                    (offset_x, offset_y, offset_x + draw_w, offset_y + draw_h),
                )
                hdc.EndPage()
        finally:
            hdc.EndDoc()
    finally:
        hdc.DeleteDC()
