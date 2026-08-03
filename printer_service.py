"""Print label images to a Windows printer via GDI."""

from __future__ import annotations

import win32con
import win32gui
import win32print
import win32ui
from PIL import Image, ImageWin

# Must match label_renderer.LABEL_MM / intended physical size.
LABEL_MM = 40
# DEVMODE paper size is in tenths of a millimeter.
_PAPER_TENTHS_MM = LABEL_MM * 10
# EnumForms sizes are in thousandths of a millimeter.
_FORM_THOUSANDTHS_MM = LABEL_MM * 1000
_FORM_TOLERANCE = 800  # ~0.8 mm


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
        except win32print.error:
            # Shared/network printers may deny saving defaults; dialog still applied for session.
            pass
    finally:
        win32print.ClosePrinter(hprinter)


def _find_label_form_name(hprinter) -> str | None:
    try:
        forms = win32print.EnumForms(hprinter)
    except win32print.error:
        return None

    target = _FORM_THOUSANDTHS_MM
    for form in forms:
        size = form.get("Size") or {}
        width = size.get("cx", 0)
        height = size.get("cy", 0)
        if (
            abs(width - target) <= _FORM_TOLERANCE
            and abs(height - target) <= _FORM_TOLERANCE
        ):
            name = form.get("Name")
            if name:
                return name
    return None


def _apply_label_paper(devmode, form_name: str | None) -> None:
    """Force 40×40 mm paper on a DEVMODE (per print job)."""
    if form_name:
        # Prefer an existing driver form when the printer already has 40×40.
        try:
            devmode.FormName = form_name
            devmode.Fields |= win32con.DM_FORMNAME
        except (AttributeError, TypeError):
            pass

    # Always also set custom size — many thermal drivers honor Width/Length.
    try:
        # 0 = custom; DMPAPER_USER (256) also accepted by some drivers.
        devmode.PaperSize = getattr(win32con, "DMPAPER_USER", 256)
        devmode.PaperWidth = _PAPER_TENTHS_MM
        devmode.PaperLength = _PAPER_TENTHS_MM
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


def _devmode_for_label(printer_name: str):
    """Build a printer DEVMODE with 40×40 mm for this job only."""
    hprinter = win32print.OpenPrinter(printer_name)
    try:
        properties = win32print.GetPrinter(hprinter, 2)
        devmode = properties.get("pDevMode")
        if devmode is None:
            return None

        form_name = _find_label_form_name(hprinter)
        _apply_label_paper(devmode, form_name)

        # Let the driver merge private DEVMODE data after our changes.
        try:
            win32print.DocumentProperties(
                0,
                hprinter,
                printer_name,
                devmode,
                devmode,
                win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER,
            )
        except win32print.error:
            pass

        # Some drivers reset PaperSize on merge — force 40×40 again for CreateDC.
        _apply_label_paper(devmode, form_name)
        return devmode
    except win32print.error:
        return None
    finally:
        win32print.ClosePrinter(hprinter)


def _create_printer_dc(printer_name: str):
    """Create a printer DC, preferably with 40×40 mm DEVMODE."""
    hdc = win32ui.CreateDC()
    devmode = _devmode_for_label(printer_name)
    if devmode is not None:
        try:
            hdc.CreateDC("WINSPOOL", printer_name, None, devmode)
            return hdc
        except win32ui.error:
            hdc.DeleteDC()
            hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    return hdc


def print_image(printer_name: str, image: Image.Image, copies: int = 1) -> None:
    if copies < 1:
        raise ValueError("Количество копий должно быть не меньше 1")

    hdc = _create_printer_dc(printer_name)

    try:
        printable_w = hdc.GetDeviceCaps(win32con.HORZRES)
        printable_h = hdc.GetDeviceCaps(win32con.VERTRES)
        dpi_x = hdc.GetDeviceCaps(win32con.LOGPIXELSX) or 203
        dpi_y = hdc.GetDeviceCaps(win32con.LOGPIXELSY) or 203

        if image.mode != "RGB":
            image = image.convert("RGB")

        # Soft image as-is. Driver smoothing must stay «Нет».
        # Do NOT hard-threshold here — that made arcs jagged/worse than the good print.
        win32gui.SetStretchBltMode(hdc.GetHandleOutput(), win32con.COLORONCOLOR)

        img_w, img_h = image.size
        target_w = max(1, round(LABEL_MM / 25.4 * dpi_x))
        target_h = max(1, round(LABEL_MM / 25.4 * dpi_y))

        if abs(img_w - target_w) <= 2 and abs(img_h - target_h) <= 2:
            draw_w, draw_h = img_w, img_h
        else:
            draw_w, draw_h = target_w, target_h

        if draw_w > printable_w or draw_h > printable_h:
            scale = min(printable_w / draw_w, printable_h / draw_h)
            draw_w = max(1, int(draw_w * scale))
            draw_h = max(1, int(draw_h * scale))

        offset_x = (printable_w - draw_w) // 2
        offset_y = (printable_h - draw_h) // 2

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
