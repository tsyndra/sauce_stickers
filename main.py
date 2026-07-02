"""GUI for printing round sauce labels."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import config
import label_renderer
import printer_service
from sauces import SAUCES


class SauceStickersApp(tk.Tk):
    COLUMNS = 3

    def __init__(self) -> None:
        super().__init__()
        self.title("Печать наклеек — соусы")
        self.minsize(520, 480)
        self._build_ui()
        self._refresh_printers()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Принтер:").pack(side=tk.LEFT)
        self.printer_var = tk.StringVar()
        self.printer_combo = ttk.Combobox(
            top,
            textvariable=self.printer_var,
            state="readonly",
            width=45,
        )
        self.printer_combo.pack(side=tk.LEFT, padx=(6, 6), fill=tk.X, expand=True)
        ttk.Button(top, text="Обновить", command=self._refresh_printers).pack(side=tk.LEFT)

        canvas_frame = ttk.Frame(self, padding=(8, 0))
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scroll_inner = ttk.Frame(self.canvas)

        self.scroll_inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.scroll_inner, anchor=tk.NW)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_sauce_buttons()

        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill=tk.X)

        ttk.Label(bottom, text="Количество:").pack(side=tk.LEFT)
        self.qty_var = tk.IntVar(value=1)
        qty_spin = ttk.Spinbox(
            bottom,
            from_=1,
            to=999,
            textvariable=self.qty_var,
            width=6,
        )
        qty_spin.pack(side=tk.LEFT, padx=(6, 0))

        self.status_var = tk.StringVar(value="Выберите принтер и нажмите соус для печати")
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.LEFT, padx=(16, 0))

    def _build_sauce_buttons(self) -> None:
        for idx, (sauce_id, sauce) in enumerate(SAUCES.items()):
            row = idx // self.COLUMNS
            col = idx % self.COLUMNS
            btn = ttk.Button(
                self.scroll_inner,
                text=sauce["button"],
                command=lambda sid=sauce_id: self._print_sauce(sid),
                width=22,
            )
            btn.grid(row=row, column=col, padx=6, pady=6, sticky=tk.NSEW)

        for col in range(self.COLUMNS):
            self.scroll_inner.columnconfigure(col, weight=1)

    def _refresh_printers(self) -> None:
        try:
            printers = printer_service.list_printers()
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось получить список принтеров:\n{exc}")
            return

        self.printer_combo["values"] = printers
        if not printers:
            self.status_var.set("Принтеры не найдены")
            return

        last = config.get_last_printer()
        if last and last in printers:
            self.printer_var.set(last)
        else:
            self.printer_var.set(printers[0])

    def _print_sauce(self, sauce_id: str) -> None:
        printer = self.printer_var.get().strip()
        if not printer:
            messagebox.showwarning("Принтер", "Выберите принтер")
            return

        try:
            qty = int(self.qty_var.get())
        except (tk.TclError, ValueError):
            messagebox.showwarning("Количество", "Введите корректное количество")
            return

        if qty < 1:
            messagebox.showwarning("Количество", "Количество должно быть не меньше 1")
            return

        sauce_name = SAUCES[sauce_id]["button"]
        self.status_var.set(f"Печать: {sauce_name} × {qty}…")
        self.update_idletasks()

        try:
            label = label_renderer.render_label(sauce_id)
            printer_service.print_image(printer, label, copies=qty)
            config.set_last_printer(printer)
        except Exception as exc:
            self.status_var.set("Ошибка печати")
            messagebox.showerror("Ошибка печати", str(exc))
            return

        self.status_var.set(f"Напечатано: {sauce_name} × {qty}")


def main() -> None:
    app = SauceStickersApp()
    app.mainloop()


if __name__ == "__main__":
    main()
