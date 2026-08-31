import json
import re
import pandas as pd

# Загрузка экспортированного JSON
with open('result.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

messages = data.get('messages', [])
rows = []

for msg in messages:
    if msg.get('type') != 'message':
        continue

    text_content = msg.get('text')

    # Telegram иногда сохраняет форматированный текст как список словарей
    if isinstance(text_content, list):
        full_text = "".join([part['text'] if isinstance(part, dict) else part for part in text_content])
    elif isinstance(text_content, str):
        full_text = text_content
    else:
        continue

    lines = [line.strip() for line in full_text.split('\n') if line.strip()]
    if not lines:
        continue

    # 1. Извлечение номера телефона (ищет 9 цифр подряд, например 977500675)
    phone_match = re.search(r'\b\d{9}\b', lines[0])
    if not phone_match:
        # Проверяем на случай, если номер записан с +998 или разделителями
        phone_match = re.search(r'(\+?998\s?)?(\d{2})[\s\-]?(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})', lines[0])
        phone = phone_match.group(0) if phone_match else None
    else:
        phone = phone_match.group(0)

    if not phone:
        continue

    # 2. Извлечение имени клиента (все слова в первой строке после/до номера)
    first_line_clean = lines[0].replace(phone, '').strip()
    client_name = first_line_clean if first_line_clean else "—"

    # 3. Извлечение товара / параметров (вторая строка, убираем тег сотрудника)
    details = ""
    if len(lines) > 1:
        details = re.sub(r'#\w+', '', lines[1]).strip()

    rows.append({
        'Дата': msg.get('date', '').split('T')[0],
        'Номер телефона': phone,
        'Имя': client_name,
        'Товар / Размер': details
    })

# Создание DataFrame и сохранение в Excel
df = pd.DataFrame(rows)

# Удаление дубликатов по номеру телефона (если нужно оставить только уникальные лиды)
# df = df.drop_duplicates(subset=['Номер телефона'])

output_file = 'клиенты_соту.xlsx'
df.to_excel(output_file, index=False)
print(f"Готово! Обработано записей: {len(df)}. Файл сохранён как {output_file}")