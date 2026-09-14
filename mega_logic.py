import json
import os
import re
import pandas as pd
import html
from datetime import datetime


# ==========================================
# ОБЩИЕ ФУНКЦИИ
# ==========================================

def safe_load_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return json.load(f)
    except Exception:
        with open(file_path, 'r', encoding='cp1251', errors='replace') as f:
            return json.load(f)


def normalize_phone(val):
    if pd.isna(val): return None
    if isinstance(val, float): val = f"{int(val)}"
    digits = re.sub(r'\D', '', str(val))
    if len(digits) >= 9: return digits[-9:]
    return None


def extract_full_text(msg):
    raw_text = msg.get('text', '')
    if isinstance(raw_text, str):
        return raw_text
    elif isinstance(raw_text, list):
        return ''.join([item if isinstance(item, str) else item.get('text', '') for item in raw_text])
    return ''


def parse_sale_details(text):
    phone_match = re.search(r'(?:\+?998[\s\-]?)?(?:\(?\d{2}\)?[\s\-]?)?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b', text)
    phone = phone_match.group(0).strip() if phone_match else 'Не указан'
    text_lower = text.lower()
    payment_type = 'Обычный'
    if 'muddatli' in text_lower or 'mudatli' in text_lower:
        payment_type = 'Muddatli (Рассрочка)'
    elif 'naqd' in text_lower or 'naxt' in text_lower:
        payment_type = 'Naqd (Наличные)'
    return {'phone': phone, 'payment_type': payment_type}


def generate_html_report(sales_data, output_html_path):
    rows = ''
    for item in sales_data:
        pay_class = 'tag-muddatli' if 'Muddatli' in item['payment_type'] else (
            'tag-naqd' if 'Naqd' in item['payment_type'] else 'tag-default')
        safe_text = html.escape(item['raw_text'])
        safe_phone = html.escape(item['phone'])
        safe_reactions = html.escape(item['reactions'] or '—')
        rows += f"""<tr><td>#{item['id']}</td><td>{item['date']}</td><td><span class="phone">{safe_phone}</span></td>
            <td><span class="{pay_class}">{item['payment_type']}</span></td><td style="white-space: pre-wrap;">{safe_text}</td><td>{safe_reactions}</td></tr>"""

    html_content = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Отчет продаж</title><style>
        body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; }}
        input {{ width: 100%; padding: 12px; margin-bottom: 20px; border-radius: 8px; border: 1px solid #334155; background: #1e293b; color: #fff; }}
        table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 12px; overflow: hidden; }}
        th, td {{ padding: 14px; text-align: left; border-bottom: 1px solid #334155; }} th {{ background: #111827; color: #94a3b8; font-size: 13px; }}
        .phone {{ font-family: monospace; color: #38bdf8; background: rgba(56,189,248,0.1); padding: 3px 6px; border-radius: 4px; }}
        .tag-muddatli {{ color: #fbbf24; background: rgba(251,191,36,0.1); padding: 3px 6px; border-radius: 4px; font-weight: 600; font-size: 12px; }}
        .tag-naqd {{ color: #34d399; background: rgba(52,211,153,0.1); padding: 3px 6px; border-radius: 4px; font-weight: 600; font-size: 12px; }}
        .tag-default {{ color: #94a3b8; background: rgba(148,163,184,0.1); padding: 3px 6px; border-radius: 4px; font-weight: 600; font-size: 12px; }}
        </style></head><body><h2>📊 Отчет продаж (Найдено: <span id="count">{len(sales_data)}</span>)</h2>
        <input type="text" id="search" placeholder="Поиск..." onkeyup="filter()">
        <table id="tbl"><thead><tr><th>ID</th><th>Дата</th><th>Телефон</th><th>Тип</th><th>Текст заявки</th><th>Реакции</th></tr></thead><tbody>{rows}</tbody></table>
        <script>function filter() {{ let val = document.getElementById('search').value.toLowerCase(); let rows = document.querySelectorAll('#tbl tbody tr'); let cnt = 0;
            rows.forEach(r => {{ let show = r.innerText.toLowerCase().includes(val); r.style.display = show ? '' : 'none'; if(show) cnt++; }});
            document.getElementById('count').innerText = cnt; }}</script></body></html>"""
    with open(output_html_path, 'w', encoding='utf-8') as f: f.write(html_content)


# ==========================================
# ЧАСТЬ 1: ОЧИСТКА TELEGRAM
# ==========================================

def scan_authors_from_json(file_path):
    data = safe_load_json(file_path)
    messages = []
    if isinstance(data, dict):
        if 'messages' in data:
            messages = data['messages']
        elif 'chats' in data and 'list' in data['chats']:
            for ch in data['chats']['list']: messages.extend(ch.get('messages', []))
    elif isinstance(data, list):
        messages = data

    author_counts = {}
    for msg in messages:
        if isinstance(msg, dict) and msg.get('type') == 'message':
            author = msg.get('from')
            if author: author_counts[author] = author_counts.get(author, 0) + 1
    return author_counts


def clean_telegram_data(in_file, out_file, mode_filter='tags', filter_val=None, save_mode='only_clean', base_file=None):
    src_data = safe_load_json(in_file)
    src_messages = []
    if isinstance(src_data, dict):
        if 'messages' in src_data:
            src_messages = src_data['messages']
        elif 'chats' in src_data and 'list' in src_data['chats']:
            for ch in src_data['chats']['list']: src_messages.extend(ch.get('messages', []))
    elif isinstance(src_data, list):
        src_messages = src_data

    if mode_filter == 'tags': targets = [t.strip().lower() for t in filter_val.split(',') if t.strip()]

    filtered_messages, html_rows, seen_ids = [], [], set()

    for msg in src_messages:
        if not isinstance(msg, dict) or msg.get('type') != 'message': continue
        msg_id = msg.get('id')
        if msg_id and msg_id in seen_ids: continue

        matched = False
        full_text = extract_full_text(msg)

        if mode_filter == 'tags':
            full_text_lower = full_text.lower()
            msg_tags = set(re.findall(r'(#[\w\d_]+)', full_text_lower, flags=re.UNICODE))
            for ent in msg.get('text_entities', []):
                if isinstance(ent, dict) and ent.get('type') == 'hashtag': msg_tags.add(
                    ent.get('text', '').lower().strip())
            msg_tags = set([t.lstrip('#') for t in msg_tags] + list(msg_tags))
            matched = any(t in msg_tags for t in targets) or any(t in full_text_lower for t in targets)
        else:
            matched = (msg.get('from') == filter_val)

        if matched:
            if msg_id: seen_ids.add(msg_id)
            filtered_messages.append(msg)
            parsed = parse_sale_details(full_text)
            reactions = [f"{r.get('emoji', '')} {r.get('count', 1)}" if r.get('count', 1) > 1 else r.get('emoji', '')
                         for r in msg.get('reactions', []) if isinstance(r, dict)]
            html_rows.append({
                'id': msg_id or '—', 'date': msg.get('date', '').replace('T', ' '),
                'phone': parsed['phone'], 'payment_type': parsed['payment_type'],
                'raw_text': full_text.strip(), 'reactions': ' '.join(reactions)
            })

    if save_mode == 'only_clean':
        out_json = {'name': 'Cleaned Sales', 'type': 'saved_messages', 'id': 8793220970, 'messages': filtered_messages}
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(out_json, f, ensure_ascii=False, indent=2)
        generate_html_report(html_rows, os.path.splitext(out_file)[0] + '.html')
        return len(filtered_messages), len(filtered_messages), len(filtered_messages)

    elif save_mode == 'merge':
        base_data = safe_load_json(base_file) if base_file else {}
        merged_list = base_data.get('messages', []) if isinstance(base_data, dict) else list(base_data)
        base_wrapper = base_data if isinstance(base_data, dict) else {'name': 'Merged Sales', 'type': 'saved_messages',
                                                                      'messages': []}

        existing_ids = {m.get('id') for m in merged_list if isinstance(m, dict) and m.get('id') is not None}
        added_count = 0
        for msg in filtered_messages:
            m_id = msg.get('id')
            if m_id not in existing_ids:
                merged_list.append(msg)
                if m_id is not None: existing_ids.add(m_id)
                added_count += 1

        base_wrapper['messages'] = merged_list
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(base_wrapper, f, ensure_ascii=False, indent=2)
        return len(filtered_messages), added_count, len(merged_list)


# ==========================================
# ЧАСТЬ 2: СВЕРКА ПРОДАЖ
# ==========================================

def scan_db_operators(daily_source):
    """Сканирует Excel базу и извлекает все уникальные имена операторов."""
    all_ops = set()
    files = []
    if os.path.isdir(daily_source):
        files = [os.path.join(daily_source, f) for f in os.listdir(daily_source) if
                 f.endswith(('.xlsx', '.xls')) and not f.startswith('~$')]
    elif os.path.isfile(daily_source):
        files = [daily_source]

    for f in files:
        try:
            df = pd.read_excel(f)
            cols = df.columns.tolist()
            op_col = next((c for c in cols if any(k in str(c).lower() for k in ['opirator', 'operator', 'оператор'])),
                          None)
            if op_col:
                ops = df[op_col].dropna().astype(str).str.strip().tolist()
                all_ops.update(ops)
        except:
            pass
    return sorted(list(all_ops))


def parse_tg_for_sverka(json_path):
    data = safe_load_json(json_path)
    messages = data.get('messages', []) if isinstance(data, dict) else data
    rows = []
    for msg in messages:
        if not isinstance(msg, dict) or msg.get('type') != 'message': continue
        full_text = extract_full_text(msg)
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        if not lines: continue

        parsed = parse_sale_details(full_text)
        if parsed['phone'] == 'Не указан': continue

        first_line_clean = lines[0].replace(parsed['phone'], '').strip()
        client_name = first_line_clean if first_line_clean else "—"
        details = re.sub(r'#\w+', '', lines[1]).strip() if len(lines) > 1 else ""

        rows.append({
            'Дата_ТГ': msg.get('date', '').replace('T', ' '),
            'Номер_ТГ': parsed['phone'],
            'Имя_ТГ': client_name,
            'Товар_ТГ': details,
            'Тип_Оплаты': parsed['payment_type']
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

    standard_df = pd.DataFrame()
    standard_df['Дата_покупки'] = df[date_col] if date_col in df else ""
    standard_df['Клиент_База'] = df[client_col] if client_col in df else ""
    standard_df['Телефон_raw'] = df[phone_col] if phone_col in df else ""
    standard_df['Товар_База'] = df[product_col] if product_col in df else ""
    standard_df['Количество'] = df[qty_col] if qty_col in df else 1
    standard_df['Оператор_в_отчете'] = df[op_col] if op_col in df else "—"
    standard_df['Файл_отчета'] = filename

    standard_df['phone_clean'] = standard_df['Телефон_raw'].apply(normalize_phone)
    return standard_df.dropna(subset=['phone_clean'])


def process_sales_final(tg_file, kpi_file, daily_source, output_dir, mapped_excel_names, make_yoqolgan, make_sverka):
    df_tg = parse_tg_for_sverka(tg_file)
    if df_tg.empty: raise ValueError("JSON файл пуст или не содержит номеров телефонов.")
    df_tg['phone_clean'] = df_tg['Номер_ТГ'].apply(normalize_phone)
    df_tg = df_tg.dropna(subset=['phone_clean']).drop_duplicates(subset=['phone_clean'], keep='last')

    kpi_phones = set()
    if kpi_file and os.path.exists(kpi_file):
        df_kpi_raw = pd.read_excel(kpi_file, header=None)
        for col in df_kpi_raw.columns:
            kpi_phones.update(df_kpi_raw[col].apply(normalize_phone).dropna().tolist())

    all_daily_rows = []
    if os.path.isdir(daily_source):
        for file in sorted(os.listdir(daily_source)):
            if (file.endswith('.xlsx') or file.endswith('.xls')) and not file.startswith('~$'):
                try:
                    all_daily_rows.append(
                        extract_standard_fields(pd.read_excel(os.path.join(daily_source, file)), file))
                except Exception as e:
                    pass
    elif os.path.isfile(daily_source):
        try:
            all_daily_rows.append(extract_standard_fields(pd.read_excel(daily_source), os.path.basename(daily_source)))
        except Exception as e:
            pass

    if not all_daily_rows: raise ValueError("Нет данных в Базе для анализа!")
    df_mega_base = pd.concat(all_daily_rows, ignore_index=True).drop_duplicates(subset=['phone_clean'], keep='last')

    res_sverka_len = 0
    res_yoqolgan_len = 0

    if make_sverka:
        sverka_raw = df_tg[~df_tg['phone_clean'].isin(df_mega_base['phone_clean'])].copy()
        sverka_final = pd.DataFrame()
        if not sverka_raw.empty:
            sverka_final['Дата'] = sverka_raw['Дата_ТГ']
            sverka_final['Продукт'] = sverka_raw['Товар_ТГ']
            sverka_final['Имя'] = sverka_raw['Имя_ТГ']
            sverka_final['Тип Оплаты'] = sverka_raw['Тип_Оплаты']
            sverka_final['Номер'] = "+998" + sverka_raw['phone_clean']
            sverka_final = sverka_final.sort_values(by='Дата')

        sverka_path = os.path.join(output_dir, "Sverka.xlsx")
        if not sverka_final.empty:
            sverka_final.to_excel(sverka_path, index=False)
        else:
            pd.DataFrame({'Статус': ['Все клиенты совершили покупку']}).to_excel(sverka_path, index=False)
        res_sverka_len = len(sverka_final)

    if make_yoqolgan:
        found_in_base = pd.merge(df_tg, df_mega_base, on='phone_clean', how='inner')
        if kpi_phones:
            lost_auto = found_in_base[~found_in_base['phone_clean'].isin(kpi_phones)].copy()
        else:
            op_base_clean = found_in_base['Оператор_в_отчете'].fillna('').astype(str).str.strip().str.upper()
            mapped_upper = [x.upper().strip() for x in mapped_excel_names]
            lost_auto = found_in_base[~op_base_clean.isin(mapped_upper)].copy()

        final_auto = pd.DataFrame()
        if not lost_auto.empty:
            final_auto['Когда купил'] = lost_auto['Дата_покупки']
            final_auto['Кто купил'] = lost_auto['Клиент_База']
            final_auto['На какой номер'] = "+998" + lost_auto['phone_clean']
            final_auto['Что купил'] = lost_auto['Товар_База']
            final_auto['Сколько купил'] = lost_auto['Количество']
            final_auto['Какой оператор записан (В базе)'] = lost_auto['Оператор_в_отчете'].fillna("—")
            final_auto['Файл отчета'] = lost_auto['Файл_отчета']

        lost_path = os.path.join(output_dir, "Yoqolgan_sotuvlar.xlsx")
        if not final_auto.empty:
            final_auto.to_excel(lost_path, index=False)
        else:
            pd.DataFrame({'Статус': ['Нет найденных потерь']}).to_excel(lost_path, index=False)
        res_yoqolgan_len = len(final_auto)

    return {
        'tg_total': len(df_tg),
        'auto_found': res_yoqolgan_len,
        'sverka_total': res_sverka_len
    }