import os
import subprocess
import sys
import tempfile
import threading
import webbrowser
from tkinter import filedialog, messagebox
import customtkinter as ctk

from core_logic import process_sales_data, get_operators_from_tg

TRANSLATIONS = {
    "UZ": {
        "title": "Sotuvlarni nazorat qilish | ASKO",
        "header": "Sotuvlarni tekshirish va qidirish",
        "btn_tg": "1. Telegram fayli (JSON)",
        "btn_op": "👥 Operatorlarni tanlash",
        "btn_kpi": "2. KPI fayli (Ixtiyoriy/Neobyazatelno)",
        "btn_daily_folder": "3. 📁 Baza (Papka)",
        "btn_daily_file": "3. 📄 Baza (Fayl)",
        "btn_save": "4. Saqlash joyi (Papka)",
        "btn_run": "🔍 SVERKA VA QIDIRISH",
        "btn_open_folder": "📁 Natijalar papkasini ochish",
        "btn_manual": "📖 Qo'llanma",
        "processing": "Tekshirilmoqda, kuting...",
        "file_not_selected": "Tanlanmagan",
        "warn_title": "Diqqat",
        "warn_text": "Telegram fayli va Bazani tanlash majburiy!",
        "card_auto": "Topilgan / Yo'qolgan",
        "card_sverka": "Sverka (Kutilyotgan)",
        "success_title": "Muvaffaqiyatli!",
        "success_text": "Tekshiruv yakunlandi!\n\nTopilgan/Yoqolgan: {auto} ta\nSverka: {sverka} ta\n\nFayl saqlandi: Sverka_va_Sotuvlar.xlsx"
    },
    "RU": {
        "title": "Контроль продаж | ASKO",
        "header": "Сверка и поиск пропущенных продаж",
        "btn_tg": "1. Файл Telegram (JSON)",
        "btn_op": "👥 Выбрать операторов",
        "btn_kpi": "2. Файл KPI (Необязательно)",
        "btn_daily_folder": "3. 📁 База (Папка)",
        "btn_daily_file": "3. 📄 База (Файл)",
        "btn_save": "4. Папка для сохранения",
        "btn_run": "🔍 СВЕРКА И ПОИСК",
        "btn_open_folder": "📁 Открыть папку с результатами",
        "btn_manual": "📖 Инструкция",
        "processing": "Идет обработка...",
        "file_not_selected": "Не выбран",
        "warn_title": "Внимание",
        "warn_text": "Файл Telegram и База продаж обязательны!",
        "card_auto": "Найдено / Потери",
        "card_sverka": "Сверка (Ожидают)",
        "success_title": "Успешно!",
        "success_text": "Обработка завершена!\n\nПотери/Найдено: {auto}\nВ Сверке: {sverka}\n\nФайл сохранен: Sverka_va_Sotuvlar.xlsx"
    }
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class OperatorsWindow(ctk.CTkToplevel):
    def __init__(self, parent, operators, current_selection, callback):
        super().__init__(parent)
        self.title("Выбор операторов")
        self.geometry("350x400")
        self.attributes("-topmost", True)
        self.callback = callback
        self.checkboxes = {}

        lbl = ctk.CTkLabel(self, text="Кого будем проверять?", font=ctk.CTkFont(weight="bold", size=16))
        lbl.pack(pady=10)

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=15, pady=5)

        for op in operators:
            var = ctk.BooleanVar(value=(op in current_selection) if current_selection else False)
            chk = ctk.CTkCheckBox(self.scroll, text=f"#{op}", variable=var)
            chk.pack(anchor="w", pady=5, padx=10)
            self.checkboxes[op] = var

        btn = ctk.CTkButton(self, text="Сохранить", command=self.save_and_close)
        btn.pack(pady=15)

    def save_and_close(self):
        selected = [op for op, var in self.checkboxes.items() if var.get()]
        self.callback(selected)
        self.destroy()


class SalesCheckerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.current_lang = "UZ"
        self.geometry("640x700")
        self.resizable(False, False)

        self.tg_path = ""
        self.kpi_path = ""
        self.daily_source_path = ""
        self.save_folder_path = os.path.join(os.path.expanduser("~"), "Desktop")

        self.available_operators = []
        self.selected_operators = []

        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=25, pady=(12, 0))

        self.lang_menu = ctk.CTkSegmentedButton(self.top_frame, values=["UZ", "RU"], command=self.change_language)
        self.lang_menu.set("UZ")
        self.lang_menu.pack(side="right")

        self.header_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=20, weight="bold"))
        self.header_label.pack(pady=(5, 12))

        # 1. Telegram + Операторы
        self.frame_tg = ctk.CTkFrame(self)
        self.frame_tg.pack(fill="x", padx=25, pady=4)
        self.btn_tg = ctk.CTkButton(self.frame_tg, width=150, command=self.select_tg_file)
        self.btn_tg.pack(side="left", padx=(10, 5), pady=8)
        self.btn_op = ctk.CTkButton(self.frame_tg, width=60, fg_color="#475569", state="disabled",
                                    command=self.open_operators_window)
        self.btn_op.pack(side="left", padx=5, pady=8)
        self.lbl_tg = ctk.CTkLabel(self.frame_tg, text="", text_color="gray", anchor="w")
        self.lbl_tg.pack(side="left", fill="x", expand=True, padx=5)

        # 2. KPI
        self.frame_kpi = ctk.CTkFrame(self)
        self.frame_kpi.pack(fill="x", padx=25, pady=4)
        self.btn_kpi = ctk.CTkButton(self.frame_kpi, width=220, command=self.select_kpi_file, fg_color="#3b82f6")
        self.btn_kpi.pack(side="left", padx=10, pady=8)
        self.lbl_kpi = ctk.CTkLabel(self.frame_kpi, text="", text_color="gray", anchor="w")
        self.lbl_kpi.pack(side="left", fill="x", expand=True, padx=5)

        # 3. База (Папка или Файл)
        self.frame_daily = ctk.CTkFrame(self)
        self.frame_daily.pack(fill="x", padx=25, pady=4)
        self.btn_daily_folder = ctk.CTkButton(self.frame_daily, width=105, command=self.select_daily_folder)
        self.btn_daily_folder.pack(side="left", padx=(10, 5), pady=8)
        self.btn_daily_file = ctk.CTkButton(self.frame_daily, width=105, command=self.select_daily_file)
        self.btn_daily_file.pack(side="left", padx=(5, 10), pady=8)
        self.lbl_daily = ctk.CTkLabel(self.frame_daily, text="", text_color="gray", anchor="w")
        self.lbl_daily.pack(side="left", fill="x", expand=True, padx=5)

        # 4. Папка сохранения
        self.frame_save = ctk.CTkFrame(self)
        self.frame_save.pack(fill="x", padx=25, pady=4)
        self.btn_save = ctk.CTkButton(self.frame_save, width=220, command=self.select_save_folder)
        self.btn_save.pack(side="left", padx=10, pady=8)
        self.lbl_save = ctk.CTkLabel(self.frame_save,
                                     text=os.path.basename(self.save_folder_path) or self.save_folder_path,
                                     text_color="white", anchor="w")
        self.lbl_save.pack(side="left", fill="x", expand=True, padx=5)

        self.btn_run = ctk.CTkButton(self, text="", font=ctk.CTkFont(size=15, weight="bold"), height=45,
                                     fg_color="#2b7a4b", hover_color="#23643d", command=self.start_processing)
        self.btn_run.pack(padx=25, pady=(15, 10), fill="x")

        # Карточки
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=25, pady=5)

        self.card_1 = ctk.CTkFrame(self.stats_frame, fg_color="#1e293b", corner_radius=8)
        self.card_1.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=5)
        self.card_1_val = ctk.CTkLabel(self.card_1, text="0", font=ctk.CTkFont(size=24, weight="bold"),
                                       text_color="#10b981")
        self.card_1_val.pack(pady=(8, 0))
        self.card_1_lbl = ctk.CTkLabel(self.card_1, text="", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        self.card_1_lbl.pack(pady=(0, 8))

        self.card_3 = ctk.CTkFrame(self.stats_frame, fg_color="#1e293b", corner_radius=8)
        self.card_3.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        self.card_3_val = ctk.CTkLabel(self.card_3, text="0", font=ctk.CTkFont(size=24, weight="bold"),
                                       text_color="#f59e0b")
        self.card_3_val.pack(pady=(8, 0))
        self.card_3_lbl = ctk.CTkLabel(self.card_3, text="", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        self.card_3_lbl.pack(pady=(0, 8))

        self.btn_open_folder = ctk.CTkButton(self, text="", fg_color="#0284c7", hover_color="#0369a1", height=35,
                                             command=self.open_output_folder)
        self.apply_language()

    def change_language(self, lang):
        self.current_lang = lang
        self.apply_language()

    def apply_language(self):
        t = TRANSLATIONS[self.current_lang]
        self.title(t["title"])
        self.header_label.configure(text=t["header"])
        self.btn_tg.configure(text=t["btn_tg"])
        self.btn_op.configure(text=t["btn_op"])
        self.btn_kpi.configure(text=t["btn_kpi"])
        self.btn_daily_folder.configure(text=t["btn_daily_folder"])
        self.btn_daily_file.configure(text=t["btn_daily_file"])
        self.btn_save.configure(text=t["btn_save"])
        self.btn_run.configure(text=t["btn_run"])
        self.btn_open_folder.configure(text=t["btn_open_folder"])
        self.card_1_lbl.configure(text=t["card_auto"])
        self.card_3_lbl.configure(text=t["card_sverka"])

        if not self.tg_path: self.lbl_tg.configure(text=t["file_not_selected"])
        if not self.kpi_path: self.lbl_kpi.configure(text=t["file_not_selected"])
        if not self.daily_source_path: self.lbl_daily.configure(text=t["file_not_selected"])

    def select_tg_file(self):
        f = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if f:
            self.tg_path = f
            self.lbl_tg.configure(text=os.path.basename(f), text_color="white")
            # Считываем операторов
            self.available_operators = get_operators_from_tg(self.tg_path)
            if self.available_operators:
                self.btn_op.configure(state="normal", fg_color="#059669")
                self.selected_operators = self.available_operators.copy()  # Выбираем всех по умолчанию

    def open_operators_window(self):
        OperatorsWindow(self, self.available_operators, self.selected_operators, self.update_operators)

    def update_operators(self, selected):
        self.selected_operators = selected
        if len(selected) == len(self.available_operators):
            self.btn_op.configure(text="Все выбраны")
        else:
            self.btn_op.configure(text=f"Выбрано: {len(selected)}")

    def select_kpi_file(self):
        f = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if f:
            self.kpi_path = f
            self.lbl_kpi.configure(text=os.path.basename(f), text_color="white")

    def select_daily_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.daily_source_path = d
            self.lbl_daily.configure(text=f"📁 {os.path.basename(d) or d}", text_color="white")

    def select_daily_file(self):
        f = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if f:
            self.daily_source_path = f
            self.lbl_daily.configure(text=f"📄 {os.path.basename(f)}", text_color="white")

    def select_save_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.save_folder_path = d
            self.lbl_save.configure(text=os.path.basename(d) or d, text_color="white")

    def open_output_folder(self):
        if os.path.exists(self.save_folder_path):
            if sys.platform == "win32":
                os.startfile(self.save_folder_path)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", self.save_folder_path])

    def start_processing(self):
        t = TRANSLATIONS[self.current_lang]
        if not self.tg_path or not self.daily_source_path:
            messagebox.showwarning(t["warn_title"], t["warn_text"])
            return

        self.btn_run.configure(state="disabled", text=t["processing"])
        threading.Thread(target=self._run_logic, daemon=True).start()

    def _run_logic(self):
        t = TRANSLATIONS[self.current_lang]
        try:
            stats = process_sales_data(
                self.tg_path,
                self.kpi_path,
                self.daily_source_path,
                self.save_folder_path,
                self.selected_operators
            )

            self.card_1_val.configure(text=str(stats['auto_found']))
            self.card_3_val.configure(text=str(stats['sverka_total']))
            self.btn_open_folder.pack(padx=25, pady=(5, 10), fill="x")

            messagebox.showinfo(t["success_title"], t["success_text"].format(
                auto=stats['auto_found'],
                sverka=stats['sverka_total']
            ))

        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
        finally:
            self.btn_run.configure(state="normal", text=t["btn_run"])


if __name__ == "__main__":
    app = SalesCheckerApp()
    app.mainloop()