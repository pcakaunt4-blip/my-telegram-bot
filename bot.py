import os
import json
import random
import string
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from telebot import TeleBot
from telebot.types import Update, InlineKeyboardMarkup, InlineKeyboardButton

# --- НАЛАШТУВАННЯ ---
TOKEN = '9060513665:AAFIsr_Ef0R1AY55f4I3O5s0tT110TGztOE'
ADMIN_ID = 7623353420
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '') # Важливо: задай це в Render!

# Ініціалізація
bot = TeleBot(TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Шляхи до файлів
DB_FILE = 'passwords.json'
USERS_FILE = 'users.json'
LOG_FILE = 'bot_logs.json'
last_generated = {}

# --- БАЗА ДАНИХ (JSON) ---
def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def log_action(user_id, action):
    logs = load_json(LOG_FILE)
    uid = str(user_id)
    if uid not in logs: logs[uid] = []
    logs[uid].append(f"[{datetime.now():%Y-%m-%d %H:%M}] {action}")
    logs[uid] = logs[uid][-50:]
    save_json(LOG_FILE, logs)

def register_user(user_id, username, first_name):
    users = load_json(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": username or "NoUsername",
            "first_name": first_name,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_json(USERS_FILE, users)
        log_action(user_id, "Зареєструвався")

# --- ЛОГІКА ПАРОЛІВ ---
def generate_password(length=12):
    chars = string.ascii_letters + string.digits + '!@#$%^&*()'
    pwd = [random.choice(c) for c in [string.ascii_lowercase, string.ascii_uppercase, string.digits, '!@#$%^&*()']]
    pwd += [random.choice(chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return ''.join(pwd)

def check_strength(password):
    score, tips = 0, []
    checks = [
        (len(password) >= 12, 2, "❌ Зроби довшим (мін. 8 символів)."),
        (len(password) >= 8, 1, "❌ Зроби довшим (мін. 8 символів)."),
        (any(c.isupper() for c in password), 1, "❌ Додай ВЕЛИКУ літеру."),
        (any(c.islower() for c in password), 1, "❌ Додай малу літеру."),
        (any(c.isdigit() for c in password), 1, "❌ Додай цифру."),
        (any(c in '!@#$%^&*()' for c in password), 1, "❌ Додай спецсимвол.")
    ]
    
    # Обробка довжини окремо, щоб не дублювати поради
    if len(password) >= 12: score += 2
    elif len(password) >= 8: score += 1
    else: tips.append("❌ Зроби довшим (мін. 8 символів).")

    for condition, points, tip in checks[2:]:
        if condition: score += points
        else: tips.append(tip)
        
    return score, tips

# --- КЛАВІАТУРА ---
def get_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔐 Пароль 12", callback_data="gen_12"),
        InlineKeyboardButton("🔐 Пароль 16", callback_data="gen_16")
    )
    markup.add(
        InlineKeyboardButton("📚 Моя бібліотека", callback_data="my_lib"),
        InlineKeyboardButton("🛡️ Перевірити пароль", callback_data="check_info")
    )
    return markup

# --- ХЕНДЛЕРИ БОТА ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    bot.send_message(message.chat.id, "👋 Привіт! Я генератор надійних паролів.\nОбери дію:", reply_markup=get_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    bot.answer_callback_query(call.id)
    uid = str(call.from_user.id)
    
    if call.data.startswith('gen_'):
        length = int(call.data.split('_')[1])
        pwd = generate_password(length)
        last_generated[uid] = pwd
        log_action(uid, f"Генерація ({length})")
        bot.send_message(call.message.chat.id, 
            f"🔐 Твій пароль:\n`{pwd}`\n\n💾 Зберегти: `/save Назва`", 
            parse_mode='Markdown')
            
    elif call.data == 'my_lib':
        db = load_json(DB_FILE)
        user_db = db.get(uid, {})
        if not user_db:
            bot.send_message(call.message.chat.id, "📭 Бібліотека порожня.")
        else:
            text = "📚 **Твої паролі:**\n\n" + "\n".join(
                f"🔹 **{k}**: `{v}`" for k, v in user_db.items()
            )
            bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
            
    elif call.data == 'check_info':
        bot.send_message(call.message.chat.id, "🛡️ Надішли мені пароль для перевірки!")

@bot.message_handler(commands=['save'])
def cmd_save(message):
    uid = str(message.from_user.id)
    if uid not in last_generated:
        return bot.send_message(message.chat.id, "❌ Спочатку згенеруй пароль!")
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "❌ Формат: `/save Назва`", parse_mode='Markdown')
        
    title = parts[1]
    db = load_json(DB_FILE)
    db.setdefault(uid, {})[title] = last_generated[uid]
    save_json(DB_FILE, db)
    log_action(uid, f"Зберіг '{title}'")
    bot.send_message(message.chat.id, f"✅ Збережено: **{title}**", parse_mode='Markdown')

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'): return
    
    score, tips = check_strength(message.text)
    levels = {6: "🟢 НАДІЙНИЙ!", 3: "🟡 СЕРЕДНІЙ", 0: "🔴 СЛАБКИЙ"}
    level = next((v for k, v in levels.items() if score >= k), "🔴 СЛАБКИЙ")
    
    response = f"{level}\n\n" + ("\n".join(tips) if tips else "Все супер!")
    bot.send_message(message.chat.id, response, parse_mode='Markdown')
    log_action(message.from_user.id, f"Перевірка (Score: {score})")

# --- АДМІН ПАНЕЛЬ ---
ADMIN_CMDS = {
    'admin': "👑 **Адмінка**\n/admin_users\n/admin_libs\n/admin_logs",
    'admin_users': lambda: "👥 **Юзери:**\n" + "\n".join(
        f"ID: `{u}` | {d['first_name']}" for u, d in load_json(USERS_FILE).items()
    ),
    'admin_libs': lambda: "📚 **Паролі:**\n" + "\n".join(
        f"👤 `{u}`:\n" + "\n".join(f"  - {k}: `{v}`" for k, v in p.items()) 
        for u, p in load_json(DB_FILE).items()
    ),
    'admin_logs': lambda: "📝 **Логи:**\n" + "\n".join(
        f"👤 `{u}`:\n" + "\n".join(f"  {a}" for a in acts[-3:]) 
        for u, acts in load_json(LOG_FILE).items()
    )
}

@bot.message_handler(commands=list(ADMIN_CMDS.keys()))
def admin_handler(message):
    if message.from_user.id != ADMIN_ID: return
    cmd = message.text.split()[0][1:] # Видаляємо /
    text = ADMIN_CMDS[cmd]() if callable(ADMIN_CMDS[cmd]) else ADMIN_CMDS[cmd]
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# --- FLASK WEBHOOK (САМЕ ТУТ МАГІЯ ДЛЯ RENDER) ---
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# --- ЗАПУСК ---
if __name__ == "__main__":
    # ⚡ КРИТИЧНО ВАЖЛИВО ДЛЯ RENDER:
    # 1. Видаляємо старий вебхук (щоб не було дублів)
    # 2. drop_pending_updates=True скидає всі повідомлення, що прийшли поки бот спав
    bot.remove_webhook(drop_pending_updates=True)
    
    if WEBHOOK_URL:
        bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
        logging.info(f"✅ Webhook set: {WEBHOOK_URL}")
    else:
        logging.warning("⚠️ WEBHOOK_URL не знайдено! Бот не буде отримувати повідомлення.")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
