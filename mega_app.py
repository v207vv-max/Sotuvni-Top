import os
import subprocess
import sys
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk

from mega_logic import (
    scan_authors_from_json, clean_telegram_data,
    scan_db_operators, process_sales_final
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class OperatorMapWindow(ctk.CTkToplevel):
    def __init__(self, parent, operators, callback):
        super().__init__(parent)
        self.title("Мэппинг (Связка имен)")
        self.geometry("350x450")
        self.attributes("-topmost", True)
        self.callback = callback
        self.checkboxes = {}

        ctk.CTkLabel(self, text="Выберите, как вас записывают в Базе:", font=ctk.CTkFont(weight="bold", size=14)).pack(
            pady=10, padx=10)

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=15, pady=5)

        for op in operators:
            var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(self.scroll, text=op, variable=var)
            chk.pack(anchor="w", pady=4, padx=5)
            self.checkboxes[op] = var

        ctk.CTkButton(self, text="Сохранить", command=self.save_and_close, fg_color="#10b981",
                      hover_color="#059669").pack(pady=15)

    def save_and_close(self):
        selected = [op for op, var in self.checkboxes.items() if var.get()]
        self.callback(selected)
        self.destroy()


class MegaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ASKO Mega App V2.0")
        self.geometry("700x700")
        self.resizable(False, False)

        # Переменные путей
        self.clean_in_path = ""
        self.clean_out_path = ""
        self.clean_base_path = ""

        self.chk_tg_path = ""
        self.chk_db_path = ""
        self.chk_kpi_path = ""
        self.chk_out_path = os.path.join(os.path.expanduser("~"), "Desktop")

        self.mapped_excel_names = []

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, corner_radius=12)
        header.pack(fill="x", padx=20, pady=(15, 10))
        ctk.CTkLabel(header, text="ASKO Mega App V2.0", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(10, 2))

        # Переключатель режимов
        self.mode_var = ctk.StringVar(value="cleaner")
        self.seg_btn = ctk.CTkSegmentedButton(
            header, values=["🧹 Режим 1: Очистка Telegram", "📊 Режим 2: Сверка Продаж"],
            command=self.switch_mode
        )
        self.seg_btn.pack(pady=(5, 10))

        # ФРЕЙМ 1: Очистка
        self.frame_cleaner = ctk.CTkFrame(self, fg_color="transparent")

        # Входной JSON
        ctk.CTkLabel(self.frame_cleaner, text="1. Исходный файл (result.json):", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 2))
        f_in = ctk.CTkFrame(self.frame_cleaner, fg_color="transparent")
        f_in.pack(fill="x", padx=10)
        self.ent_cl_in = ctk.CTkEntry(f_in, height=32)
        self.ent_cl_in.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(f_in, text="Обзор...", width=90,
                      command=lambda: self._browse_file(self.ent_cl_in, [('JSON', '*.json')])).pack(side="right")

        # Тип фильтра
        ctk.CTkLabel(self.frame_cleaner, text="2. Метод фильтрации:", font=ctk.CTkFont(weight="bold")).pack(anchor="w",
                                                                                                            padx=10,
                                                                                                            pady=(10,
                                                                                                                  2))
        self.cl_filter_mode = ctk.StringVar(value="tags")
        f_rad1 = ctk.CTkFrame(self.frame_cleaner, fg_color="transparent")
        f_rad1.pack(fill="x", padx=10)
        ctk.CTkRadioButton(f_rad1, text="По хэштегам", variable=self.cl_filter_mode, value="tags",
                           command=self.update_cleaner_ui).pack(side="left", padx=(0, 20))
        ctk.CTkRadioButton(f_rad1, text="По автору (from)", variable=self.cl_filter_mode, value="author",
                           command=self.update_cleaner_ui).pack(side="left")

        self.f_tags = ctk.CTkFrame(self.frame_cleaner, fg_color="transparent")
        self.f_tags.pack(fill="x", padx=10, pady=(5, 0))
        self.ent_tags = ctk.CTkEntry(self.f_tags, placeholder_text="#hashtag1, #hashtag2", height=32)
        self.ent_tags.pack(fill="x")

        self.f_auth = ctk.CTkFrame(self.frame_cleaner, fg_color="transparent")
        self.cmb_authors = ctk.CTkComboBox(self.f_auth, values=["(Сначала нажмите Сканировать)"], height=32)
        self.cmb_authors.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(self.f_auth, text="🔄 Скан авторов", width=110, command=self._scan_authors).pack(side="right")

        # Метод сохранения
        ctk.CTkLabel(self.frame_cleaner, text="3. Что делать с результатом:", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 2))
        self.cl_save_mode = ctk.StringVar(value="only_clean")
        f_rad2 = ctk.CTkFrame(self.frame_cleaner, fg_color="transparent")
        f_rad2.pack(fill="x", padx=10)
        ctk.CTkRadioButton(f_rad2, text="Новый чистый файл", variable=self.cl_save_mode, value="only_clean",
                           command=self.update_cleaner_ui).pack(side="left", padx=(0, 20))
        ctk.CTkRadioButton(f_rad2, text="Припаять к существующему", variable=self.cl_save_mode, value="merge",
                           command=self.update_cleaner_ui).pack(side="left")

        self.f_merge_base = ctk.CTkFrame(self.frame_cleaner, fg_color="transparent")
        self.ent_merge_base = ctk.CTkEntry(self.f_merge_base, placeholder_text="Выберите базовый JSON для припайки...",
                                           height=32)
        self.ent_merge_base.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(self.f_merge_base, text="Обзор...", width=90,
                      command=lambda: self._browse_file(self.ent_merge_base, [('JSON', '*.json')])).pack(side="right")

        # Куда сохранить
        ctk.CTkLabel(self.frame_cleaner, text="4. Куда сохранить итог:", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 2))
        f_out = ctk.CTkFrame(self.frame_cleaner, fg_color="transparent")
        f_out.pack(fill="x", padx=10)
        self.ent_cl_out = ctk.CTkEntry(f_out, height=32)
        self.ent_cl_out.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(f_out, text="Выбрать...", width=90, command=self._browse_save_cleaner).pack(side="right")

        self.btn_run_cleaner = ctk.CTkButton(self.frame_cleaner, text="🚀 ВЫПОЛНИТЬ ОЧИСТКУ", height=45,
                                             fg_color="#3b82f6", hover_color="#2563eb", command=self.run_cleaner)
        self.btn_run_cleaner.pack(fill="x", padx=10, pady=(25, 0))

        # ФРЕЙМ 2: Сверка
        self.frame_checker = ctk.CTkFrame(self, fg_color="transparent")

        # Входные файлы
        ctk.CTkLabel(self.frame_checker, text="1. Готовый JSON из Telegram:", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(5, 2))
        f_tg = ctk.CTkFrame(self.frame_checker, fg_color="transparent")
        f_tg.pack(fill="x", padx=10)
        self.ent_ch_tg = ctk.CTkEntry(f_tg, height=32)
        self.ent_ch_tg.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(f_tg, text="Обзор...", width=90,
                      command=lambda: self._browse_file(self.ent_ch_tg, [('JSON', '*.json')])).pack(side="right")

        ctk.CTkLabel(self.frame_checker, text="2. База продаж (Папка или Файл):", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 2))
        f_db = ctk.CTkFrame(self.frame_checker, fg_color="transparent")
        f_db.pack(fill="x", padx=10)
        self.ent_ch_db = ctk.CTkEntry(f_db, height=32)
        self.ent_ch_db.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(f_db, text="📁 Папка", width=70, command=self._browse_db_folder).pack(side="left", padx=(0, 5))
        ctk.CTkButton(f_db, text="📄 Файл", width=70,
                      command=lambda: self._browse_file(self.ent_ch_db, [('Excel', '*.xlsx *.xls')])).pack(side="left")

        ctk.CTkLabel(self.frame_checker, text="3. Файл KPI (Необязательно):", font=ctk.CTkFont(weight="bold"),
                     text_color="gray").pack(anchor="w", padx=10, pady=(10, 2))
        f_kpi = ctk.CTkFrame(self.frame_checker, fg_color="transparent")
        f_kpi.pack(fill="x", padx=10)
        self.ent_ch_kpi = ctk.CTkEntry(f_kpi, height=32)
        self.ent_ch_kpi.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(f_kpi, text="Обзор...", width=90, fg_color="#475569",
                      command=lambda: self._browse_file(self.ent_ch_kpi, [('Excel', '*.xlsx *.xls')])).pack(
            side="right")

        # Мэппинг
        self.btn_map = ctk.CTkButton(self.frame_checker, text="🔗 Связать имена (Мэппинг)", height=35,
                                     fg_color="#8b5cf6", hover_color="#7c3aed", command=self._open_mapping)
        self.btn_map.pack(fill="x", padx=10, pady=(15, 10))

        # Чекбоксы вывода
        ctk.CTkLabel(self.frame_checker, text="Что генерировать на выходе:", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(5, 2))
        self.var_yoqolgan = ctk.BooleanVar(value=True)
        self.var_sverka = ctk.BooleanVar(value=True)
        f_chk = ctk.CTkFrame(self.frame_checker, fg_color="transparent")
        f_chk.pack(fill="x", padx=10)
        ctk.CTkCheckBox(f_chk, text="Yoqolgan Sotuvlar (Потери)", variable=self.var_yoqolgan).pack(side="left",
                                                                                                   padx=(0, 20))
        ctk.CTkCheckBox(f_chk, text="Sverka (Еще не купили)", variable=self.var_sverka).pack(side="left")

        ctk.CTkLabel(self.frame_checker, text="Куда сохранить Excel-отчеты:", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=10, pady=(15, 2))
        f_cout = ctk.CTkFrame(self.frame_checker, fg_color="transparent")
        f_cout.pack(fill="x", padx=10)
        self.ent_ch_out = ctk.CTkEntry(f_cout, height=32)
        self.ent_ch_out.insert(0, self.chk_out_path)
        self.ent_ch_out.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(f_cout, text="Выбрать...", width=90, command=self._browse_save_checker).pack(side="right")

        self.btn_run_checker = ctk.CTkButton(self.frame_checker, text="🔍 ЗАПУСТИТЬ СВЕРКУ", height=45,
                                             fg_color="#10b981", hover_color="#059669", command=self.run_checker)
        self.btn_run_checker.pack(fill="x", padx=10, pady=(25, 0))

        # Старт программы с Режима 1
        self.seg_btn.set("🧹 Режим 1: Очистка Telegram")
        self.switch_mode("🧹 Режим 1: Очистка Telegram")

    # --- UI Logic ---
    def switch_mode(self, value):
        if "Режим 1" in value:
            self.frame_checker.pack_forget()
            self.frame_cleaner.pack(fill="both", expand=True)
        else:
            self.frame_cleaner.pack_forget()
            self.frame_checker.pack(fill="both", expand=True)

    def update_cleaner_ui(self):
        if self.cl_filter_mode.get() == "tags":
            self.f_auth.pack_forget()
            self.f_tags.pack(fill="x", padx=10, pady=(5, 0), after=self.frame_cleaner.winfo_children()[3])
        else:
            self.f_tags.pack_forget()
            self.f_auth.pack(fill="x", padx=10, pady=(5, 0), after=self.frame_cleaner.winfo_children()[3])

        if self.cl_save_mode.get() == "merge":
            self.f_merge_base.pack(fill="x", padx=10, pady=(5, 0), after=self.frame_cleaner.winfo_children()[6])
        else:
            self.f_merge_base.pack_forget()

    # --- Browse Helpers ---
    def _browse_file(self, entry_widget, ftypes):
        f = filedialog.askopenfilename(filetypes=ftypes)
        if f:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, f)

    def _browse_db_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.ent_ch_db.delete(0, 'end')
            self.ent_ch_db.insert(0, d)

    def _browse_save_cleaner(self):
        f = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON', '*.json')],
                                         initialfile='clean_sales.json')
        if f:
            self.ent_cl_out.delete(0, 'end')
            self.ent_cl_out.insert(0, f)

    def _browse_save_checker(self):
        d = filedialog.askdirectory()
        if d:
            self.ent_ch_out.delete(0, 'end')
            self.ent_ch_out.insert(0, d)

    # --- Cleaner Mode Logic ---
    def _scan_authors(self):
        src = self.ent_cl_in.get().strip()
        if not src or not os.path.exists(src):
            messagebox.showwarning("Внимание", "Сначала выберите исходный файл result.json!")
            return
        try:
            ac = scan_authors_from_json(src)
            dl = [f'{a} ({c} сообщ)' for a, c in sorted(ac.items(), key=lambda x: -x[1])]
            self.cmb_authors.configure(values=dl)
            if dl: self.cmb_authors.set(dl[0])
            messagebox.showinfo("Готово", f"Найдено авторов: {len(ac)}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def run_cleaner(self):
        src = self.ent_cl_in.get().strip()
        out = self.ent_cl_out.get().strip()
        if not src or not out:
            messagebox.showwarning("Внимание", "Укажите входной и выходной файлы!")
            return

        mode_filter = self.cl_filter_mode.get()
        filter_val = self.ent_tags.get() if mode_filter == "tags" else self.cmb_authors.get().rsplit(' (', 1)[0].strip()
        save_mode = self.cl_save_mode.get()
        base_file = self.ent_merge_base.get().strip() if save_mode == "merge" else None

        self.btn_run_cleaner.configure(state="disabled", text="ОБРАБОТКА...")
        threading.Thread(target=self._thread_cleaner, args=(src, out, mode_filter, filter_val, save_mode, base_file),
                         daemon=True).start()

    def _thread_cleaner(self, src, out, mode_filter, filter_val, save_mode, base_file):
        try:
            res = clean_telegram_data(src, out, mode_filter, filter_val, save_mode, base_file)
            self.after(0, lambda: messagebox.showinfo("Успех",
                                                      f"Отфильтровано: {res[0]}\nДобавлено новых: {res[1]}\nВсего в итоге: {res[2]}\n\nФайл сохранен: {out}"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        finally:
            self.after(0, lambda: self.btn_run_cleaner.configure(state="normal", text="🚀 ВЫПОЛНИТЬ ОЧИСТКУ"))

    # --- Checker Mode Logic ---
    def _open_mapping(self):
        db_path = self.ent_ch_db.get().strip()
        if not db_path or not os.path.exists(db_path):
            messagebox.showwarning("Внимание", "Сначала выберите Базу продаж (Файл или Папку)!")
            return

        self.btn_map.configure(state="disabled", text="Сканирование базы...")
        threading.Thread(target=self._thread_scan_mapping, args=(db_path,), daemon=True).start()

    def _thread_scan_mapping(self, db_path):
        try:
            ops = scan_db_operators(db_path)
            self.after(0, lambda: self._show_mapping_window(ops))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Ошибка сканирования", str(e)))
        finally:
            self.after(0, lambda: self.btn_map.configure(state="normal", text="🔗 Связать имена (Мэппинг)"))

    def _show_mapping_window(self, ops):
        if not ops:
            messagebox.showinfo("Пусто", "В базе не найдено имен операторов!")
            return
        OperatorMapWindow(self, ops, self._save_mapping)

    def _save_mapping(self, selected):
        self.mapped_excel_names = selected
        if selected:
            self.btn_map.configure(text=f"Связано вариантов: {len(selected)}", fg_color="#059669")
        else:
            self.btn_map.configure(text="🔗 Связать имена (Мэппинг)", fg_color="#8b5cf6")

    def run_checker(self):
        tg = self.ent_ch_tg.get().strip()
        db = self.ent_ch_db.get().strip()
        kpi = self.ent_ch_kpi.get().strip()
        out = self.ent_ch_out.get().strip()
        my = self.var_yoqolgan.get()
        ms = self.var_sverka.get()

        if not tg or not db or not out:
            messagebox.showwarning("Внимание", "Заполните обязательные поля (TG JSON, База, Папка сохранения)!")
            return
        if not my and not ms:
            messagebox.showwarning("Внимание", "Выберите хотя бы один отчет для генерации!")
            return
        if my and not kpi and not self.mapped_excel_names:
            if not messagebox.askyesno("Внимание",
                                       "Вы не связали имена (Мэппинг) и не указали KPI.\nПрограмма выдаст ВСЕ продажи как потерянные.\nПродолжить?"):
                return

        self.btn_run_checker.configure(state="disabled", text="ИДЕТ СВЕРКА...")
        threading.Thread(target=self._thread_checker, args=(tg, kpi, db, out, self.mapped_excel_names, my, ms),
                         daemon=True).start()

    def _thread_checker(self, tg, kpi, db, out, mapped, my, ms):
        try:
            res = process_sales_final(tg, kpi, db, out, mapped, my, ms)
            msg = f"Всего лидов: {res['tg_total']}\n\n"
            if my: msg += f"Потери (Yoqolgan): {res['auto_found']}\n"
            if ms: msg += f"Сверка (Еще не купили): {res['sverka_total']}\n"
            self.after(0, lambda: messagebox.showinfo("Готово", msg))
            if sys.platform == "win32": os.startfile(out)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        finally:
            self.after(0, lambda: self.btn_run_checker.configure(state="normal", text="🔍 ЗАПУСТИТЬ СВЕРКУ"))


if __name__ == "__main__":
    app = MegaApp()
    app.mainloop()