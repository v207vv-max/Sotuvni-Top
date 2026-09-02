import json
import os
import re
import pandas as pd


def normalize_phone(val):
    if pd.isna(val):
        return None
    if isinstance(val, float):
        val = f"{int(val)}"
    digits = re.sub(r'\D', '', str(val))
    if len(digits) >= 9:
        return digits[-9:]
    return None


def get_operators_from_tg(json_path):
    """Считывает всех операторов по хэштегам из Telegram JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        operators = set()
        for msg in data.get('messages', []):
            if msg.get('type') != 'message': continue
            for ent in msg.get('text_entities', []):
                if ent.get('type') == 'hashtag':
                    op_name = ent.get('text', '').replace('#', '').strip()
                    if op_name:
                        operators.add(op_name)
        return sorted(list(operators))
    except Exception as e:
        print(f"Ошибка чтения операторов: {e}")
        return []


def parse_tg_json_data(json_path, selected_operators=None):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    messages = data.get('messages', [])
    rows = []

    for msg in messages:
        if msg.get('type') != 'message':
            continue

        msg_operator = "Неизвестно"
        for ent in msg.get('text_entities', []):
            if ent.get('type') == 'hashtag':
                msg_operator = ent.get('text', '').replace('#', '').strip()
                break

        if selected_operators and msg_operator not in selected_operators:
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
            'Товар_ТГ': details,
            'Оператор_ТГ': msg_operator
        })

    return pd.DataFrame(rows)


def extract_standard_fields(df, filename):
    cols = df.columns.tolist()

    phone_col = next(
        (c for c in cols if any(k in str(c).lower() for k in ['number', 'телефон', 'phone', 'nomer', 'tel', 'raqam'])),
        None)
    date_col = next((c for c in cols if any(k in str(c).lower() for k in ['day', 'дата', 'date', 'kun'])), None)
    client_col = next(
        (c for c in cols if any(k in str(c).lower() for k in ['kliyent', 'клиент', 'client', 'haridor', 'ism'])), None)
    product_col = next(
        (c for c in cols if any(k in str(c).lower() for k in ['tovar', 'товар', 'product', 'продукт', 'mahsulot'])),
        None)
    qty_col = next(
        (c for c in cols if any(k in str(c).lower() for k in ['count', 'количество', 'k-bo', 'кол-во', 'qty', 'soni'])),
        None)
    op_col = next((c for c in cols if any(k in str(c).lower() for k in ['opirator', 'operator', 'оператор'])), None)
    warehouse_col = next((c for c in cols if any(k in str(c).lower() for k in ['filial', 'филиал', 'склад', 'sklad'])),
                         None)
    contract_col = next((c for c in cols if any(k in str(c).lower() for k in ['договор', 'shartnoma', 'dogovor'])),
                        None)

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


def process_sales_data(tg_file, kpi_file, daily_source, output_dir, selected_operators=None):
    # 1. Читаем Telegram
    if tg_file.endswith('.json'):
        df_tg = parse_tg_json_data(tg_file, selected_operators)
        df_tg['phone_clean'] = df_tg['Номер_ТГ'].apply(normalize_phone)
    else:
        df_tg = pd.read_excel(tg_file)
        phone_col = next(
            (c for c in df_tg.columns if any(k in str(c).lower() for k in ['number', 'номер', 'телефон', 'phone'])),
            df_tg.columns[1])
        df_tg['phone_clean'] = df_tg[phone_col].apply(normalize_phone)
        date_col = next((c for c in df_tg.columns if any(k in str(c).lower() for k in ['day', 'дата', 'date'])),
                        df_tg.columns[0])
        df_tg['Дата_ТГ'] = df_tg[date_col]
        df_tg['Имя_ТГ'] = next(
            (df_tg[c] for c in df_tg.columns if any(k in str(c).lower() for k in ['kliyent', 'имя', 'клиент'])), "—")
        df_tg['Товар_ТГ'] = next(
            (df_tg[c] for c in df_tg.columns if any(k in str(c).lower() for k in ['tovar', 'товар', 'product'])), "—")
        df_tg['Оператор_ТГ'] = "Все"

    df_tg = df_tg.dropna(subset=['phone_clean']).drop_duplicates(subset=['phone_clean'])

    # 2. Читаем KPI (Опционально)
    kpi_phones = set()
    if kpi_file and os.path.exists(kpi_file):
        df_kpi_raw = pd.read_excel(kpi_file, header=None)
        for col in df_kpi_raw.columns:
            kpi_phones.update(df_kpi_raw[col].apply(normalize_phone).dropna().tolist())

    # 3. Собираем базу из папки или файла
    all_daily_rows = []
    if os.path.isdir(daily_source):
        for file in sorted(os.listdir(daily_source)):
            if (file.endswith('.xlsx') or file.endswith('.xls')) and not file.startswith('~$'):
                try:
                    temp_df = pd.read_excel(os.path.join(daily_source, file))
                    all_daily_rows.append(extract_standard_fields(temp_df, file))
                except Exception as e:
                    print(f"Ошибка в файле {file}: {e}")
    elif os.path.isfile(daily_source):
        try:
            temp_df = pd.read_excel(daily_source)
            all_daily_rows.append(extract_standard_fields(temp_df, os.path.basename(daily_source)))
        except Exception as e:
            print(f"Ошибка в файле {daily_source}: {e}")

    if not all_daily_rows:
        raise ValueError("Нет данных в Базе для анализа!")

    df_mega_base = pd.concat(all_daily_rows, ignore_index=True).drop_duplicates(subset=['phone_clean'])

    # === РАЗДЕЛЕНИЕ НА СВЕРКУ И ПОТЕРИ ===

    # А. СВЕРКА: Клиенты из ТГ, которых вообще нет в базе продаж (еще не купили)
    sverka_raw = df_tg[~df_tg['phone_clean'].isin(df_mega_base['phone_clean'])].copy()
    sverka_final = pd.DataFrame()
    if not sverka_raw.empty:
        sverka_final['Дата'] = sverka_raw['Дата_ТГ']
        sverka_final['Продукт'] = sverka_raw['Товар_ТГ']
        sverka_final['Имя'] = sverka_raw['Имя_ТГ']
        sverka_final['Номер'] = "+998" + sverka_raw['phone_clean']
        sverka_final['Оператор (ТГ)'] = sverka_raw['Оператор_ТГ']
        sverka_final = sverka_final.sort_values(by='Дата')

    # Б. ПОТЕРЯННЫЕ ПРОДАЖИ: Есть в базе, но не зачтены
    found_in_base = pd.merge(df_tg, df_mega_base, on='phone_clean', how='inner')

    if kpi_phones:
        # Если загружен KPI — исключаем номера из KPI
        lost_auto = found_in_base[~found_in_base['phone_clean'].isin(kpi_phones)].copy()
    else:
        # Если KPI НЕТ — исключаем тех, кто в базе уже записан на выбранного оператора!
        # Сравниваем имя оператора из ТГ и имя оператора в базе (без учета регистра)
        op_tg_clean = found_in_base['Оператор_ТГ'].astype(str).str.strip().str.upper()
        op_base_clean = found_in_base['Оператор_в_отчете'].fillna('').astype(str).str.strip().str.upper()

        # Потеря = когда в базе записан ДРУГОЙ человек или не записан вовсе
        lost_auto = found_in_base[op_tg_clean != op_base_clean].copy()

    final_auto = pd.DataFrame()
    if not lost_auto.empty:
        final_auto['Когда купил'] = lost_auto['Дата_покупки']
        final_auto['Кто купил'] = lost_auto['Клиент_База']
        final_auto['На какой номер'] = "+998" + lost_auto['phone_clean']
        final_auto['Что купил'] = lost_auto['Товар_База']
        final_auto['Сколько купил'] = lost_auto['Количество']
        final_auto['Какой оператор записан (В базе)'] = lost_auto['Оператор_в_отчете'].fillna("—")
        final_auto['Оператор (ТГ)'] = lost_auto['Оператор_ТГ']
        final_auto['Файл отчета'] = lost_auto['Файл_отчета']

    # 4. Сохранение в два отдельных файла
    lost_file_path = os.path.join(output_dir, "Yoqolgan_sotuvlar.xlsx")
    sverka_file_path = os.path.join(output_dir, "Sverka.xlsx")

    if not final_auto.empty:
        final_auto.to_excel(lost_file_path, index=False)
    else:
        pd.DataFrame({'Статус': ['Нет найденных потерь']}).to_excel(lost_file_path, index=False)

    if not sverka_final.empty:
        sverka_final.to_excel(sverka_file_path, index=False)
    else:
        pd.DataFrame({'Статус': ['Все клиенты совершили покупку']}).to_excel(sverka_file_path, index=False)

    return {
        'tg_total': len(df_tg),
        'auto_found': len(final_auto),
        'sverka_total': len(sverka_final)
    }
