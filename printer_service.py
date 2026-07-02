"""Print label images to a Windows printer via GDI."""

from __future__ import annotations

import win32con
import win32print
import win32ui
from PIL import Image, ImageWin


def list_printers() -> list[str]:
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    printers = win32print.EnumPrinters(flags)
    return [name for _, _, name, _ in printers]


def print_image(printer_name: str, image: Image.Image, copies: int = 1) -> None:
    if copies < 1:
        raise ValueError("Количество копий должно быть не меньше 1")

    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)

    try:
        printable_w = hdc.GetDeviceCaps(win32con.HORZRES)
        printable_h = hdc.GetDeviceCaps(win32con.VERTRES)

        if image.mode != "RGB":
            image = image.convert("RGB")

        img_w, img_h = image.size
        scale = min(printable_w / img_w, printable_h / img_h)
        draw_w = int(img_w * scale)
        draw_h = int(img_h * scale)
        offset_x = (printable_w - draw_w) // 2
        offset_y = (printable_h - draw_h) // 2

        hdc.StartDoc("SauceStickers")
        try:
            for _ in range(copies):
                hdc.StartPage()
                dib = ImageWin.Dib(image)
                dib.draw(hdc.GetHandleOutput(), (offset_x, offset_y, offset_x + draw_w, offset_y + draw_h))
                hdc.EndPage()
        finally:
            hdc.EndDoc()
    finally:
        hdc.DeleteDC()
