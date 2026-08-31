import os
import subprocess
import sys
import tempfile
import threading
import webbrowser
from tkinter import filedialog, messagebox
import customtkinter as ctk

from core_logic import process_sales_data

# Инструкции
MANUAL_HTML_UZ = """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<title>Dasturdan foydalanish bo'yicha qo'llanma</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #2d3748; background: #f7fafc; margin: 0; padding: 25px; }
  .container { max-width: 860px; margin: 0 auto; background: #ffffff; padding: 35px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
  h1 { color: #1a365d; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; font-size: 24px; }
  .step-box { background: #edf2f7; border-left: 5px solid #3182ce; padding: 16px 20px; margin: 15px 0; border-radius: 4px; }
  .step-title { font-weight: bold; font-size: 16px; color: #2d3748; margin-bottom: 6px; }
  .badge { background: #3182ce; color: white; padding: 2px 8px; border-radius: 4px; font-size: 13px; font-weight: bold; }
  ol { padding-left: 20px; }
  li { margin-bottom: 6px; }
</style>
</head>
<body>
<div class="container">
  <h1>ASKO: Sotuvlarni tekshirish dasturi bo'yicha qo'llanma</h1>

  <div class="step-box">
    <div class="step-title"><span class="badge">1-QADAM</span> Telegram kanalidan fayl olish</div>
    <ol>
      <li>Telegram Desktop ➔ Sotuv kanalingiz ➔ 3 ta nuqta ➔ <b>"Export chat history"</b>.</li>
      <li>Barcha media fayllardan galochkalarni olib tashlang, formatni <b>"JSON"</b> qilib eksport qiling.</li>
      <li>Dasturning 1-tugmasiga o'sha <b>result.json</b> yoki <b>.xlsx</b> faylini yuklang.</li>
    </ol>
  </div>

  <div class="step-box">
    <div class="step-title"><span class="badge">2-QADAM</span> KPI faylini yuklash</div>
    <p>Oylik tasdiqlangan rasmiy KPI faylini 2-tugma orqali yuklang.</p>
  </div>

  <div class="step-box">
    <div class="step-title"><span class="badge">3-QADAM</span> Kunlik sotuvlar papkasi</div>
    <p>Oyning barcha kunlik sotuv fayllarini bitta papkaga yig'ing va 3-tugma orqali ko'rsating.</p>
  </div>

  <div class="step-box">
    <div class="step-title"><span class="badge">4-QADAM</span> Saqlash joyi va Natija</div>
    <p>Fayllar saqlanadigan papkani tanlang va yashil tugmani bosing. Dastur tayyor bo'lgach, papkani avtomatik ochish imkoniyatini beradi.</p>
  </div>
</div>
</body>
</html>
"""

MANUAL_HTML_RU = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Инструкция по использованию</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #2d3748; background: #f7fafc; margin: 0; padding: 25px; }
  .container { max-width: 860px; margin: 0 auto; background: #ffffff; padding: 35px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
  h1 { color: #1a365d; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; font-size: 24px; }
  .step-box { background: #edf2f7; border-left: 5px solid #3182ce; padding: 16px 20px; margin: 15px 0; border-radius: 4px; }
  .step-title { font-weight: bold; font-size: 16px; color: #2d3748; margin-bottom: 6px; }
  .badge { background: #3182ce; color: white; padding: 2px 8px; border-radius: 4px; font-size: 13px; font-weight: bold; }
  ol { padding-left: 20px; }
  li { margin-bottom: 6px; }
</style>
</head>
<body>
<div class="container">
  <h1>ASKO: Инструкция по поиску неучтенных продаж</h1>

  <div class="step-box">
    <div class="step-title"><span class="badge">ШАГ 1</span> Выгрузка из Telegram</div>
    <ol>
      <li>Telegram Desktop ➔ Канал продаж ➔ 3 точки ➔ <b>"Экспорт истории чата"</b>.</li>
      <li>Снимите галочки с фото/видео, формат <b>"JSON"</b> ➔ Экспортировать.</li>
      <li>Загрузите <b>result.json</b> или <b>.xlsx</b> в первую кнопку программы.</li>
    </ol>
  </div>

  <div class="step-box">
    <div class="step-title"><span class="badge">ШАГ 2</span> Файл утвержденного KPI</div>
    <p>Укажите утвержденный файл KPI за месяц через вторую кнопку.</p>
  </div>

  <div class="step-box">
    <div class="step-title"><span class="badge">ШАГ 3</span> Папка с отчетами филиалов</div>
    <p>Соберите дневные файлы (01.08, 02.08 и т.д.) в папку и выберите её через третью кнопку.</p>
  </div>

  <div class="step-box">
    <div class="step-title"><span class="badge">ШАГ 4</span> Папка сохранения и расчет</div>
    <p>Выберите, куда сохранить готовые отчеты, и нажмите зеленую кнопку. После проверки вы сможете сразу открыть папку с файлами в 1 клик.</p>
  </div>
</div>
</body>
</html>
"""

TRANSLATIONS = {
    "UZ": {
        "title": "Sotuvlarni nazorat qilish | ASKO",
        "header": "Sotuvlarni tekshirish va qidirish",
        "btn_tg": "1. Telegram fayli (JSON / Excel)",
        "btn_kpi": "2. Tasdiqlangan KPI fayli",
        "btn_daily": "3. Kunlik hisobotlar papkasi",
        "btn_save": "4. Saqlash joyi (Papka)",
        "btn_run": "🔍 YO'QOTILGAN SOTUVLARNI QIDIRISH",
        "btn_open_folder": "📁 Natijalar papkasini ochish",
        "btn_manual": "📖 Qo'llanma / Yo'riqnoma",
        "processing": "Tekshirilmoqda, kuting...",
        "file_not_selected": "Tanlanmagan",
        "folder_not_selected": "Tanlanmagan",
        "warn_title": "Diqqat",
        "warn_text": "Iltimos, barcha fayllarni va papkalarni tanlang!",
        "card_auto": "100% Topilgan sotuvlar",
        "card_manual": "Rahbarga tekshiruvga",
        "card_total": "Kompaniya bazasi",
        "success_title": "Muvaffaqiyatli!",
        "success_text": "Tekshiruv yakunlandi!\n\nTopilgan sotuvlar: {auto} ta\nTekshiruvga nomzodlar: {manual} ta"
    },
    "RU": {
        "title": "Контроль продаж | ASKO",
        "header": "Сверка и поиск пропущенных продаж",
        "btn_tg": "1. Файл Telegram (JSON / Excel)",
        "btn_kpi": "2. Файл утвержденного KPI",
        "btn_daily": "3. Папка отчетов компании",
        "btn_save": "4. Папка для сохранения",
        "btn_run": "🔍 НАЙТИ ПОТЕРЯННЫЕ ПРОДАЖИ",
        "btn_open_folder": "📁 Открыть папку с результатами",
        "btn_manual": "📖 Инструкция по использованию",
        "processing": "Идет обработка...",
        "file_not_selected": "Не выбран",
        "folder_not_selected": "Не выбрана",
        "warn_title": "Внимание",
        "warn_text": "Пожалуйста, укажите все файлы и папки!",
        "card_auto": "100% Подтверждено",
        "card_manual": "Кандидатов РОПу",
        "card_total": "Продаж в базе",
        "success_title": "Успешно!",
        "success_text": "Сверка завершена!\n\nНайдено потерь: {auto}\nКандидатов на проверку: {manual}"
    }
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class SalesCheckerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.current_lang = "UZ"
        self.geometry("640x700")
        self.resizable(False, False)

        self.tg_path = ""
        self.kpi_path = ""
        self.daily_folder_path = ""
        # По умолчанию ставим Рабочий стол пользователя
        self.save_folder_path = os.path.join(os.path.expanduser("~"), "Desktop")

        # Переключатель языка
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=25, pady=(12, 0))

        self.lang_menu = ctk.CTkSegmentedButton(
            self.top_frame,
            values=["UZ", "RU"],
            command=self.change_language
        )
        self.lang_menu.set("UZ")
        self.lang_menu.pack(side="right")

        # Заголовок
        self.header_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.header_label.pack(pady=(5, 12))

        # 1. Telegram
        self.frame_tg = ctk.CTkFrame(self)
        self.frame_tg.pack(fill="x", padx=25, pady=4)
        self.btn_tg = ctk.CTkButton(self.frame_tg, width=220, command=self.select_tg_file)
        self.btn_tg.pack(side="left", padx=10, pady=8)
        self.lbl_tg = ctk.CTkLabel(self.frame_tg, text="", text_color="gray", anchor="w")
        self.lbl_tg.pack(side="left", fill="x", expand=True, padx=5)

        # 2. KPI
        self.frame_kpi = ctk.CTkFrame(self)
        self.frame_kpi.pack(fill="x", padx=25, pady=4)
        self.btn_kpi = ctk.CTkButton(self.frame_kpi, width=220, command=self.select_kpi_file)
        self.btn_kpi.pack(side="left", padx=10, pady=8)
        self.lbl_kpi = ctk.CTkLabel(self.frame_kpi, text="", text_color="gray", anchor="w")
        self.lbl_kpi.pack(side="left", fill="x", expand=True, padx=5)

        # 3. Ежедневные отчеты
        self.frame_daily = ctk.CTkFrame(self)
        self.frame_daily.pack(fill="x", padx=25, pady=4)
        self.btn_daily = ctk.CTkButton(self.frame_daily, width=220, command=self.select_daily_folder)
        self.btn_daily.pack(side="left", padx=10, pady=8)
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

        # Кнопка Запуска
        self.btn_run = ctk.CTkButton(
            self,
            text="",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=45,
            fg_color="#2b7a4b",
            hover_color="#23643d",
            command=self.start_processing
        )
        self.btn_run.pack(padx=25, pady=(15, 10), fill="x")

        # Блок карточек статистики (вместо терминала)
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=25, pady=5)

        # Карточка 1: Авто
        self.card_1 = ctk.CTkFrame(self.stats_frame, fg_color="#1e293b", corner_radius=8)
        self.card_1.pack(side="left", fill="both", expand=True, padx=(0, 4), pady=5)
        self.card_1_val = ctk.CTkLabel(self.card_1, text="0", font=ctk.CTkFont(size=24, weight="bold"),
                                       text_color="#10b981")
        self.card_1_val.pack(pady=(8, 0))
        self.card_1_lbl = ctk.CTkLabel(self.card_1, text="", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        self.card_1_lbl.pack(pady=(0, 8))

        # Карточка 2: Кандидаты
        self.card_2 = ctk.CTkFrame(self.stats_frame, fg_color="#1e293b", corner_radius=8)
        self.card_2.pack(side="left", fill="both", expand=True, padx=4, pady=5)
        self.card_2_val = ctk.CTkLabel(self.card_2, text="0", font=ctk.CTkFont(size=24, weight="bold"),
                                       text_color="#f59e0b")
        self.card_2_val.pack(pady=(8, 0))
        self.card_2_lbl = ctk.CTkLabel(self.card_2, text="", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        self.card_2_lbl.pack(pady=(0, 8))

        # Карточка 3: Всего в базе
        self.card_3 = ctk.CTkFrame(self.stats_frame, fg_color="#1e293b", corner_radius=8)
        self.card_3.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=5)
        self.card_3_val = ctk.CTkLabel(self.card_3, text="0", font=ctk.CTkFont(size=24, weight="bold"),
                                       text_color="#38bdf8")
        self.card_3_val.pack(pady=(8, 0))
        self.card_3_lbl = ctk.CTkLabel(self.card_3, text="", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        self.card_3_lbl.pack(pady=(0, 8))

        # Кнопка "Открыть папку с результатами" (скрыта до завершения)
        self.btn_open_folder = ctk.CTkButton(
            self,
            text="",
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=35,
            command=self.open_output_folder
        )

        # Нижняя кнопка инструкции
        self.btn_manual = ctk.CTkButton(
            self,
            text="",
            fg_color="#334155",
            hover_color="#1e293b",
            height=35,
            command=self.open_manual
        )
        self.btn_manual.pack(padx=25, pady=(10, 15), fill="x")

        self.apply_language()

    def change_language(self, lang):
        self.current_lang = lang
        self.apply_language()

    def apply_language(self):
        t = TRANSLATIONS[self.current_lang]
        self.title(t["title"])
        self.header_label.configure(text=t["header"])
        self.btn_tg.configure(text=t["btn_tg"])
        self.btn_kpi.configure(text=t["btn_kpi"])
        self.btn_daily.configure(text=t["btn_daily"])
        self.btn_save.configure(text=t["btn_save"])
        self.btn_run.configure(text=t["btn_run"])
        self.btn_open_folder.configure(text=t["btn_open_folder"])
        self.btn_manual.configure(text=t["btn_manual"])

        self.card_1_lbl.configure(text=t["card_auto"])
        self.card_2_lbl.configure(text=t["card_manual"])
        self.card_3_lbl.configure(text=t["card_total"])

        if not self.tg_path:
            self.lbl_tg.configure(text=t["file_not_selected"])
        if not self.kpi_path:
            self.lbl_kpi.configure(text=t["file_not_selected"])
        if not self.daily_folder_path:
            self.lbl_daily.configure(text=t["folder_not_selected"])

    def open_manual(self):
        html_content = MANUAL_HTML_UZ if self.current_lang == "UZ" else MANUAL_HTML_RU
        temp_dir = tempfile.gettempdir()
        manual_path = os.path.join(temp_dir, f"asko_manual_{self.current_lang.lower()}.html")

        with open(manual_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        webbrowser.open(f"file://{manual_path}")

    def select_tg_file(self):
        f = filedialog.askopenfilename(filetypes=[("Telegram Data", "*.json *.xlsx *.xls")])
        if f:
            self.tg_path = f
            self.lbl_tg.configure(text=os.path.basename(f), text_color="white")

    def select_kpi_file(self):
        f = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx *.xls")])
        if f:
            self.kpi_path = f
            self.lbl_kpi.configure(text=os.path.basename(f), text_color="white")

    def select_daily_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.daily_folder_path = d
            self.lbl_daily.configure(text=os.path.basename(d) or d, text_color="white")

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
        if not self.tg_path or not self.kpi_path or not self.daily_folder_path:
            messagebox.showwarning(t["warn_title"], t["warn_text"])
            return

        self.btn_run.configure(state="disabled", text=t["processing"])
        threading.Thread(target=self._run_logic, daemon=True).start()

    def _run_logic(self):
        t = TRANSLATIONS[self.current_lang]
        try:
            stats = process_sales_data(
                tg_file=self.tg_path,
                kpi_file=self.kpi_path,
                daily_folder=self.daily_folder_path,
                output_dir=self.save_folder_path
            )

            # Обновляем виджеты карточек с анимацией значений
            self.card_1_val.configure(text=str(stats['auto_found']))
            self.card_2_val.configure(text=str(stats['manual_candidates']))
            self.card_3_val.configure(text=str(stats['mega_base_total']))

            # Показываем кнопку открытия папки
            self.btn_open_folder.pack(padx=25, pady=(0, 10), fill="x", before=self.btn_manual)

            messagebox.showinfo(
                t["success_title"],
                t["success_text"].format(auto=stats['auto_found'], manual=stats['manual_candidates'])
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.btn_run.configure(state="normal", text=t["btn_run"])


if __name__ == "__main__":
    app = SalesCheckerApp()
    app.mainloop()