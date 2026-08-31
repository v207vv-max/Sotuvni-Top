import json
import os
import re
import pandas as pd


def normalize_phone(val):
    """Приводит номер к 9 цифрам."""
    if pd.isna(val):
        return None
    if isinstance(val, float):
        val = f"{int(val)}"
    digits = re.sub(r'\D', '', str(val))
    if len(digits) >= 9:
        return digits[-9:]
    return None


def parse_tg_json_data(json_path):
    """Парсит Telegram JSON напрямую в DataFrame."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    messages = data.get('messages', [])
    rows = []

    for msg in messages:
        if msg.get('type') != 'message':
            continue

        text_content = msg.get('text')
        if isinstance(text_content, list):
            full_text = "".join([part['text'] if isinstance(part, dict) else str(part) for part in text_content])
        elif isinstance(text_content, str):
            full_text = text_content
        else:
            continue

        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        if not lines:
            continue

        # Поиск номера
        phone_match = re.search(r'\b\d{9}\b', lines[0])
        if not phone_match:
            phone_match = re.search(r'(\+?998\s?)?(\d{2})[\s\-]?(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})', lines[0])
            phone = phone_match.group(0) if phone_match else None
        else:
            phone = phone_match.group(0)

        if not phone:
            continue

        first_line_clean = lines[0].replace(phone, '').strip()
        client_name = first_line_clean if first_line_clean else "—"

        details = ""
        if len(lines) > 1:
            details = re.sub(r'#\w+', '', lines[1]).strip()

        rows.append({
            'Дата_ТГ': msg.get('date', '').split('T')[0],
            'Номер_ТГ': phone,
            'Имя_ТГ': client_name,
            'Товар_ТГ': details
        })

    return pd.DataFrame(rows)


def extract_standard_fields(df, filename):
    """Нормализует разные форматы столбцов ежедневных отчетов."""
    cols = df.columns.tolist()

    phone_col = next((c for c in cols if any(k in str(c).lower() for k in ['телефон', 'phone', 'nomer'])), None)
    if not phone_col and len(cols) > 4:
        phone_col = cols[4]

    date_col = next((c for c in cols if any(k in str(c).lower() for k in ['дата', 'date'])), None)
    if not date_col and len(cols) > 0:
        date_col = cols[0]

    client_col = next((c for c in cols if any(k in str(c).lower() for k in ['клиент', 'client'])), None)
    if not client_col and len(cols) > 3:
        client_col = cols[3]

    product_col = next((c for c in cols if any(k in str(c).lower() for k in ['продукт', 'товар', 'product'])), None)
    if not product_col and len(cols) > 5:
        product_col = cols[5]

    qty_col = next((c for c in cols if any(k in str(c).lower() for k in ['количество', 'k-bo', 'кол-во', 'qty'])), None)
    if not qty_col and len(cols) > 7:
        qty_col = cols[7]

    op_col = next((c for c in cols if any(k in str(c).lower() for k in ['operator', 'оператор'])), None)
    if not op_col and len(cols) > 8:
        op_col = cols[8]

    contract_col = next((c for c in cols if 'договор' in str(c).lower()), cols[1] if len(cols) > 1 else None)
    warehouse_col = next((c for c in cols if 'склад' in str(c).lower()), cols[2] if len(cols) > 2 else None)

    standard_df = pd.DataFrame()
    standard_df['Дата_покупки'] = df[date_col] if date_col in df else ""
    standard_df['Договор'] = df[contract_col] if contract_col in df else ""
    standard_df['Склад'] = df[warehouse_col] if warehouse_col in df else ""
    standard_df['Клиент_База'] = df[client_col] if client_col in df else ""
    standard_df['Телефон_raw'] = df[phone_col] if phone_col in df else ""
    standard_df['Товар_База'] = df[product_col] if product_col in df else ""
    standard_df['Количество'] = df[qty_col] if qty_col in df else 1
    standard_df['Оператор_в_отчете'] = df[op_col] if op_col in df else "—"
    standard_df['Файл_отчета'] = filename

    standard_df['phone_clean'] = standard_df['Телефон_raw'].apply(normalize_phone)
    return standard_df.dropna(subset=['phone_clean'])


def process_sales_data(tg_file, kpi_file, daily_folder, output_dir):
    """Сверяет данные и формирует только один файл Yoqolgan_sotuvlar.xlsx"""
    # 1. Читаем Telegram
    if tg_file.endswith('.json'):
        df_tg = parse_tg_json_data(tg_file)
        df_tg['phone_clean'] = df_tg['Номер_ТГ'].apply(normalize_phone)
    else:
        df_tg = pd.read_excel(tg_file)
        phone_col = next((c for c in df_tg.columns if any(k in str(c).lower() for k in ['номер', 'телефон', 'phone'])),
                         df_tg.columns[1])
        df_tg['phone_clean'] = df_tg[phone_col].apply(normalize_phone)
        date_col = next((c for c in df_tg.columns if 'дата' in str(c).lower()), df_tg.columns[0])
        client_col = next((c for c in df_tg.columns if 'имя' in str(c).lower()), '—')
        product_col = next((c for c in df_tg.columns if 'товар' in str(c).lower()), '—')
        df_tg['Дата_ТГ'] = df_tg[date_col]
        df_tg['Имя_ТГ'] = df_tg[client_col] if client_col in df_tg else "—"
        df_tg['Товар_ТГ'] = df_tg[product_col] if product_col in df_tg else "—"

    df_tg = df_tg.dropna(subset=['phone_clean']).drop_duplicates(subset=['phone_clean'])

    # 2. Читаем KPI
    df_kpi_raw = pd.read_excel(kpi_file, header=None)
    kpi_phones = set()
    for col in df_kpi_raw.columns:
        kpi_phones.update(df_kpi_raw[col].apply(normalize_phone).dropna().tolist())

    # 3. Собираем базу из ежедневных отчетов
    all_daily_rows = []
    for file in sorted(os.listdir(daily_folder)):
        if (file.endswith('.xlsx') or file.endswith('.xls')) and not file.startswith('~$'):
            file_path = os.path.join(daily_folder, file)
            try:
                temp_df = pd.read_excel(file_path)
                std_df = extract_standard_fields(temp_df, file)
                all_daily_rows.append(std_df)
            except Exception as e:
                print(f"Ошибка в файле {file}: {e}")

    if not all_daily_rows:
        raise ValueError("В указанной папке нет файлов отчетов!")

    df_mega_base = pd.concat(all_daily_rows, ignore_index=True)
    df_mega_base = df_mega_base.drop_duplicates(subset=['phone_clean'])

    # 4. Выделяем лиды оператора, которых нет в KPI
    uncredited_tg = df_tg[~df_tg['phone_clean'].isin(kpi_phones)].copy()
    lost_auto = pd.merge(uncredited_tg, df_mega_base, on='phone_clean', how='inner')

    final_auto = pd.DataFrame()
    if not lost_auto.empty:
        final_auto['Когда купил'] = lost_auto['Дата_покупки']
        final_auto['Кто купил'] = lost_auto['Клиент_База']
        final_auto['На какой номер'] = "+998" + lost_auto['phone_clean']
        final_auto['Что купил'] = lost_auto['Товар_База']
        final_auto['Сколько купил'] = lost_auto['Количество']
        final_auto['Какой оператор записан'] = lost_auto['Оператор_в_отчете'].fillna("—")
        final_auto['Договор'] = lost_auto['Договор']
        final_auto['Склад'] = lost_auto['Склад']
        final_auto['Файл отчета'] = lost_auto['Файл_отчета']

    # 5. Сохраняем ТОЛЬКО файл Yoqolgan_sotuvlar.xlsx
    auto_file_path = os.path.join(output_dir, "Yoqolgan_sotuvlar.xlsx")
    final_auto.to_excel(auto_file_path, index=False)

    return {
        'tg_total': len(df_tg),
        'kpi_total': len(kpi_phones),
        'mega_base_total': len(df_mega_base),
        'auto_found': len(final_auto)
    }