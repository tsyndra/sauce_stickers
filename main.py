"""GUI for printing round sauce and dessert labels."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import config
import label_renderer
import printer_service
import updater
from desserts import DESSERTS, LEGAL_ENTITIES
from sauces import SAUCES
from version import APP_VERSION


class LegalEntityDialog(tk.Toplevel):
    """Modal: pick branch IP once; required before using the app."""

    def __init__(self, master: tk.Tk, *, title: str = "ИП филиала") -> None:
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.result: str | None = None

        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Выберите ИП филиала — он будет печататься\nвнизу десертных наклеек:",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        self.entity_var = tk.StringVar()
        combo = ttk.Combobox(
            frame,
            textvariable=self.entity_var,
            values=LEGAL_ENTITIES,
            state="readonly",
            width=36,
        )
        combo.pack(fill=tk.X, pady=(12, 16))
        if LEGAL_ENTITIES:
            combo.current(0)
        combo.focus_set()

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Отмена", command=self._on_cancel).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Сохранить", command=self._on_ok).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self._on_cancel())

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.wait_window(self)

    def _on_ok(self) -> None:
        value = self.entity_var.get().strip()
        if value not in LEGAL_ENTITIES:
            messagebox.showwarning("ИП филиала", "Выберите ИП из списка", parent=self)
            return
        self.result = value
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


class SauceStickersApp(tk.Tk):
    COLUMNS = 3

    def __init__(self) -> None:
        super().__init__()
        self.title(f"Печать наклеек — соусы и десерты  v{APP_VERSION}")
        self.minsize(560, 560)
        self.legal_entity: str | None = None
        self._update_busy = False
        self._build_ui()
        self._refresh_printers()
        self.after(50, self._ensure_legal_entity)
        self.after(800, lambda: self._check_updates(silent=True))

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
        ttk.Button(top, text="Настройки…", command=self._open_printer_settings).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        branch = ttk.Frame(self, padding=(8, 0, 8, 0))
        branch.pack(fill=tk.X)
        ttk.Label(branch, text="ИП филиала:").pack(side=tk.LEFT)
        self.legal_var = tk.StringVar(value="не выбран")
        ttk.Label(branch, textvariable=self.legal_var).pack(side=tk.LEFT, padx=(6, 8))
        ttk.Button(branch, text="Сменить…", command=self._change_legal_entity).pack(
            side=tk.LEFT
        )
        ttk.Button(
            branch,
            text="Проверить обновления",
            command=lambda: self._check_updates(silent=False),
        ).pack(side=tk.RIGHT)

        offset_row = ttk.Frame(self, padding=(8, 6, 8, 0))
        offset_row.pack(fill=tk.X)
        ttk.Label(offset_row, text="Сдвиг мм:").pack(side=tk.LEFT)
        ttk.Label(offset_row, text="X").pack(side=tk.LEFT, padx=(8, 2))
        ox, oy = config.get_print_offset_mm()
        self.offset_x_var = tk.DoubleVar(value=ox)
        self.offset_y_var = tk.DoubleVar(value=oy)
        ttk.Spinbox(
            offset_row,
            from_=-10.0,
            to=10.0,
            increment=0.5,
            textvariable=self.offset_x_var,
            width=6,
            command=self._save_print_offset,
        ).pack(side=tk.LEFT)
        ttk.Label(offset_row, text="Y").pack(side=tk.LEFT, padx=(8, 2))
        ttk.Spinbox(
            offset_row,
            from_=-10.0,
            to=10.0,
            increment=0.5,
            textvariable=self.offset_y_var,
            width=6,
            command=self._save_print_offset,
        ).pack(side=tk.LEFT)
        ttk.Label(offset_row, text="Зазор").pack(side=tk.LEFT, padx=(10, 2))
        self.gap_var = tk.DoubleVar(value=config.get_label_gap_mm())
        ttk.Spinbox(
            offset_row,
            from_=0.0,
            to=10.0,
            increment=0.125,
            textvariable=self.gap_var,
            width=5,
            command=self._save_label_gap,
        ).pack(side=tk.LEFT)
        ttk.Label(offset_row, text="мм").pack(side=tk.LEFT, padx=(2, 0))
        self.tspl_var = tk.BooleanVar(value=config.get_tspl_mode())
        ttk.Checkbutton(
            offset_row,
            text="Прямая печать TSPL",
            variable=self.tspl_var,
            command=lambda: config.set_tspl_mode(bool(self.tspl_var.get())),
        ).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(
            offset_row,
            text="Проверить принтер",
            command=self._check_printer_setup,
        ).pack(side=tk.RIGHT)
        ttk.Button(
            offset_row,
            text="Калибровка зазора",
            command=self._calibrate_gap,
        ).pack(side=tk.RIGHT, padx=(0, 6))
        self.offset_x_var.trace_add("write", lambda *_: self._save_print_offset())
        self.offset_y_var.trace_add("write", lambda *_: self._save_print_offset())
        self.gap_var.trace_add("write", lambda *_: self._save_label_gap())

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

        sauces_tab = ttk.Frame(notebook)
        desserts_tab = ttk.Frame(notebook)
        notebook.add(sauces_tab, text="Соусы")
        notebook.add(desserts_tab, text="Десерты")

        self._build_button_grid(
            sauces_tab,
            items=SAUCES,
            on_click=self._print_sauce,
        )
        self._build_button_grid(
            desserts_tab,
            items=DESSERTS,
            on_click=self._print_dessert,
        )

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

        self.status_var = tk.StringVar(value="Выберите принтер и нажмите позицию для печати")
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.LEFT, padx=(16, 0))

    def _build_button_grid(self, parent: ttk.Frame, items: dict, on_click) -> None:
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")),
        )
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for idx, (item_id, item) in enumerate(items.items()):
            row = idx // self.COLUMNS
            col = idx % self.COLUMNS
            btn = ttk.Button(
                inner,
                text=item["button"],
                command=lambda iid=item_id, cb=on_click: cb(iid),
                width=24,
            )
            btn.grid(row=row, column=col, padx=6, pady=6, sticky=tk.NSEW)

        for col in range(self.COLUMNS):
            inner.columnconfigure(col, weight=1)

    def _set_legal_entity(self, legal_entity: str) -> None:
        self.legal_entity = legal_entity
        self.legal_var.set(legal_entity)
        config.set_legal_entity(legal_entity)

    def _ensure_legal_entity(self) -> None:
        saved = config.get_legal_entity()
        if saved in LEGAL_ENTITIES:
            self.legal_entity = saved
            self.legal_var.set(saved)
            return

        dialog = LegalEntityDialog(self)
        if dialog.result is None:
            messagebox.showinfo(
                "ИП филиала",
                "Нужно выбрать ИП филиала, чтобы печатать десертные наклейки.",
            )
            self.destroy()
            return

        self._set_legal_entity(dialog.result)

    def _change_legal_entity(self) -> None:
        dialog = LegalEntityDialog(self, title="Сменить ИП филиала")
        if dialog.result:
            self._set_legal_entity(dialog.result)
            self.status_var.set(f"ИП филиала: {dialog.result}")

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

    def _open_printer_settings(self) -> None:
        printer = self.printer_var.get().strip()
        if not printer:
            messagebox.showwarning("Принтер", "Сначала выберите принтер")
            return
        try:
            hwnd = int(self.winfo_id())
            printer_service.open_printer_preferences(printer, hwnd)
            self.status_var.set(f"Настройки принтера: {printer}")
        except Exception as exc:
            messagebox.showerror("Настройки принтера", str(exc))

    def _save_print_offset(self) -> None:
        try:
            x = float(self.offset_x_var.get())
            y = float(self.offset_y_var.get())
        except (tk.TclError, ValueError, TypeError):
            return
        config.set_print_offset_mm(x, y)

    def _save_label_gap(self) -> None:
        try:
            gap = float(self.gap_var.get())
        except (tk.TclError, ValueError, TypeError):
            return
        config.set_label_gap_mm(gap)

    def _print_offsets(self) -> tuple[float, float]:
        try:
            return float(self.offset_x_var.get()), float(self.offset_y_var.get())
        except (tk.TclError, ValueError, TypeError):
            return config.get_print_offset_mm()

    def _label_gap(self) -> float:
        try:
            return float(self.gap_var.get())
        except (tk.TclError, ValueError, TypeError):
            return config.get_label_gap_mm()

    def _print_label(self, printer: str, label, qty: int) -> None:
        ox, oy = self._print_offsets()
        if bool(self.tspl_var.get()):
            printer_service.print_image_tspl(
                printer,
                label,
                copies=qty,
                offset_x_mm=ox,
                offset_y_mm=oy,
                gap_mm=self._label_gap(),
                direction=config.get_tspl_direction(),
                sensor_from_left_mm=0.0,
            )
        else:
            printer_service.print_image(
                printer,
                label,
                copies=qty,
                offset_x_mm=ox,
                offset_y_mm=oy,
                gap_mm=self._label_gap(),
            )

    def _calibrate_gap(self) -> None:
        printer = self.printer_var.get().strip()
        if not printer:
            messagebox.showwarning("Принтер", "Сначала выберите принтер")
            return
        if not messagebox.askyesno(
            "Калибровка зазора",
            "Принтер промотает 2–3 пустые наклейки и запомнит зазор ленты.\n"
            "После этого текст перестанет сползать. Продолжить?",
        ):
            return
        try:
            printer_service.calibrate_gap_tspl(printer, gap_mm=self._label_gap())
        except Exception as exc:
            messagebox.showerror("Калибровка зазора", str(exc))
            return
        self.status_var.set("Калибровка отправлена — дождитесь, пока принтер остановится")

    def _check_printer_setup(self, *, silent_ok: bool = False) -> bool:
        printer = self.printer_var.get().strip()
        if not printer:
            messagebox.showwarning("Принтер", "Сначала выберите принтер")
            return False
        if bool(self.tspl_var.get()):
            gap = self._label_gap()
            summary = (
                f"TSPL непрерывно: шаг {40 + gap:.3f} мм "
                f"(40 + зазор {gap:g}), датчик выкл. "
                f"Сдвиг X/Y двигает картинку по наклейке"
            )
            self.status_var.set(summary)
            if not silent_ok:
                messagebox.showinfo("Принтер", summary)
            return True
        try:
            info = printer_service.inspect_printer(
                printer, gap_mm=self._label_gap()
            )
        except Exception as exc:
            messagebox.showerror("Принтер", str(exc))
            return False

        self.status_var.set(info["summary"])
        if info["ok"]:
            if not silent_ok:
                messagebox.showinfo("Принтер", info["summary"])
            return True

        return messagebox.askyesno(
            "Принтер",
            f"{info['summary']}\n\n"
            "Откройте «Настройки…» и выберите носитель 40×40 мм.\n"
            "Если наклейки «ползут» вдоль ленты — подкрутите «Зазор».\n"
            "Печатать всё равно?",
        )

    def _check_updates(self, *, silent: bool) -> None:
        if self._update_busy:
            return
        if silent and not updater.get_update_base():
            return

        self._update_busy = True
        if not silent:
            self.status_var.set("Проверка обновлений…")

        def worker() -> None:
            try:
                info = updater.fetch_update_info()
                self.after(
                    0,
                    lambda: self._on_update_check_done(info, silent=silent, error=None),
                )
            except Exception as exc:
                err = exc
                self.after(
                    0,
                    lambda: self._on_update_check_done(None, silent=silent, error=err),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_check_done(
        self, info, *, silent: bool, error: Exception | None
    ) -> None:
        self._update_busy = False
        if error is not None:
            if silent:
                return
            messagebox.showerror("Обновление", str(error))
            self.status_var.set("Не удалось проверить обновления")
            return

        if info is None:
            if not silent:
                messagebox.showinfo(
                    "Обновление",
                    f"Установлена актуальная версия {APP_VERSION}.",
                )
                self.status_var.set(f"Версия актуальна: {APP_VERSION}")
            return

        notes = f"\n\n{info.notes}" if info.notes else ""
        if not messagebox.askyesno(
            "Обновление",
            f"Доступна версия {info.version} (сейчас {APP_VERSION}).{notes}\n\n"
            "Скачать и установить?",
        ):
            self.status_var.set(f"Доступна версия {info.version}")
            return

        self._install_update(info)

    def _install_update(self, info: updater.UpdateInfo) -> None:
        if not updater.is_frozen():
            messagebox.showinfo(
                "Обновление",
                "Автоустановка работает только в собранном SauceStickers.exe.\n"
                f"Новая версия: {info.version}\nИсточник: {info.source}",
            )
            return

        progress = tk.Toplevel(self)
        progress.title("Обновление")
        progress.resizable(False, False)
        progress.transient(self)
        progress.grab_set()
        ttk.Label(progress, text=f"Скачивание {info.version}…").pack(
            padx=20, pady=(16, 8)
        )
        bar = ttk.Progressbar(progress, mode="determinate", length=280)
        bar.pack(padx=20, pady=(0, 16))
        progress.update_idletasks()

        def on_progress(done: int, total: int) -> None:
            def ui() -> None:
                if total > 0:
                    bar.configure(mode="determinate", maximum=total, value=done)
                else:
                    if str(bar.cget("mode")) != "indeterminate":
                        bar.configure(mode="indeterminate")
                        bar.start(10)

            self.after(0, ui)

        def worker() -> None:
            try:
                path = updater.download_update(info, progress=on_progress)
                self.after(0, lambda: self._on_update_downloaded(path, progress))
            except Exception as exc:
                err = exc
                self.after(0, lambda: self._on_update_failed(err, progress))

        self._update_busy = True
        self.status_var.set(f"Скачивание {info.version}…")
        threading.Thread(target=worker, daemon=True).start()

    def _on_update_failed(self, exc: Exception, progress: tk.Toplevel) -> None:
        self._update_busy = False
        try:
            progress.destroy()
        except tk.TclError:
            pass
        messagebox.showerror("Обновление", f"Не удалось скачать обновление:\n{exc}")
        self.status_var.set("Ошибка обновления")

    def _on_update_downloaded(self, new_exe, progress: tk.Toplevel) -> None:
        try:
            progress.destroy()
        except tk.TclError:
            pass
        try:
            updater.apply_update_and_restart(new_exe)
        except Exception as exc:
            self._update_busy = False
            messagebox.showerror("Обновление", str(exc))
            self.status_var.set("Ошибка обновления")
            return

        self.status_var.set("Установка обновления…")
        self.destroy()
        sys.exit(0)

    def _get_print_request(self) -> tuple[str, int] | None:
        printer = self.printer_var.get().strip()
        if not printer:
            messagebox.showwarning("Принтер", "Выберите принтер")
            return None

        if not self._check_printer_setup(silent_ok=True):
            return None

        try:
            qty = int(self.qty_var.get())
        except (tk.TclError, ValueError):
            messagebox.showwarning("Количество", "Введите корректное количество")
            return None

        if qty < 1:
            messagebox.showwarning("Количество", "Количество должно быть не меньше 1")
            return None

        return printer, qty

    def _print_sauce(self, sauce_id: str) -> None:
        req = self._get_print_request()
        if req is None:
            return
        printer, qty = req

        sauce_name = SAUCES[sauce_id]["button"]
        self.status_var.set(f"Печать: {sauce_name} × {qty}…")
        self.update_idletasks()

        try:
            label = label_renderer.render_label(sauce_id)
            self._print_label(printer, label, qty)
            config.set_last_printer(printer)
        except Exception as exc:
            self.status_var.set("Ошибка печати")
            messagebox.showerror("Ошибка печати", str(exc))
            return

        self.status_var.set(f"Напечатано: {sauce_name} × {qty}")

    def _print_dessert(self, dessert_id: str) -> None:
        if not self.legal_entity:
            messagebox.showwarning("ИП филиала", "Сначала выберите ИП филиала")
            self._ensure_legal_entity()
            if not self.legal_entity:
                return

        req = self._get_print_request()
        if req is None:
            return
        printer, qty = req

        dessert_name = DESSERTS[dessert_id]["button"]
        self.status_var.set(f"Печать: {dessert_name} × {qty}…")
        self.update_idletasks()

        try:
            label = label_renderer.render_dessert_label(
                dessert_id,
                legal_entity=self.legal_entity,
            )
            self._print_label(printer, label, qty)
            config.set_last_printer(printer)
        except Exception as exc:
            self.status_var.set("Ошибка печати")
            messagebox.showerror("Ошибка печати", str(exc))
            return

        self.status_var.set(f"Напечатано: {dessert_name} × {qty}")


def main() -> None:
    app = SauceStickersApp()
    app.mainloop()


if __name__ == "__main__":
    main()
