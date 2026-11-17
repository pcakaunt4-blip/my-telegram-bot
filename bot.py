import os
import json
import random
import string
import threading
from datetime import datetime
from flask import Flask
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = '9060513665:AAFIsr_Ef0R1AY55f4I3O5s0tT110TGztOE'
ADMIN_ID = 7623353420

bot = TeleBot(TOKEN)
app = Flask(__name__)

DB_FILE = 'passwords.json'
USERS_FILE = 'users.json'
LOG_FILE = 'bot_logs.json'
last_generated = {}

def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def log_action(user_id, action):
    logs = load_json(LOG_FILE)
    uid = str(user_id)
    if uid not in logs: logs[uid] = []
    logs[uid].append(f"[{datetime.now():%H:%M}] {action}")
    logs[uid] = logs[uid][-50:]
    save_json(LOG_FILE, logs)

def register_user(user_id, username, first_name):
    users = load_json(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": username or "NoUsername",
            "first_name": first_name,
            "joined": datetime.now().strftime("%Y-%m-%d")
        }
        save_json(USERS_FILE, users)
        log_action(user_id, "Start")

def generate_password(length=12):
    chars = string.ascii_letters + string.digits + '!@#$%^&*()'
    pwd = [random.choice(c) for c in [string.ascii_lowercase, string.ascii_uppercase, string.digits, '!@#$%^&*()']]
    pwd += [random.choice(chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return ''.join(pwd)

def check_strength(password):
    score, tips = 0, []
    if len(password) >= 12: score += 2
    elif len(password) >= 8: score += 1
    else: tips.append("❌ Мін. 8 символів")
    if any(c.isupper() for c in password): score += 1
    else: tips.append("❌ Додай велику літеру")
    if any(c.isdigit() for c in password): score += 1
    else: tips.append("❌ Додай цифру")
    if any(c in '!@#$%^&*()' for c in password): score += 1
    else: tips.append("❌ Додай спецсимвол")
    return score, tips

def get_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔐 12 символів", callback_data="gen_12"),
        InlineKeyboardButton("🔐 16 символів", callback_data="gen_16")
    )
    markup.add(
        InlineKeyboardButton("📚 Бібліотека", callback_data="my_lib"),
        InlineKeyboardButton("🛡️ Перевірка", callback_data="check_info")
    )
    return markup

@bot.message_handler(commands=['start'])
def cmd_start(message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    bot.send_message(message.chat.id, "👋 Привіт! Обери дію:", reply_markup=get_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    bot.answer_callback_query(call.id)
    uid = str(call.from_user.id)
    
    if call.data.startswith('gen_'):
        length = int(call.data.split('_')[1])
        pwd = generate_password(length)
        last_generated[uid] = pwd
        log_action(uid, f"Gen {length}")
        bot.send_message(call.message.chat.id, f"🔐 Пароль:\n`{pwd}`\n\nЗберегти: `/save Назва`", parse_mode='Markdown')
            
    elif call.data == 'my_lib':
        db = load_json(DB_FILE)
        user_db = db.get(uid, {})
        if not user_db:
            bot.send_message(call.message.chat.id, "📭 Пусто.")
        else:
            text = "📚 **Паролі:**\n\n" + "\n".join(f"🔹 **{k}**: `{v}`" for k, v in user_db.items())
            bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
            
    elif call.data == 'check_info':
        bot.send_message(call.message.chat.id, "🛡️ Надішли пароль!")

@bot.message_handler(commands=['save'])
def cmd_save(message):
    uid = str(message.from_user.id)
    if uid not in last_generated:
        return bot.send_message(message.chat.id, "❌ Спочатку згенеруй!")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "❌ `/save Назва`", parse_mode='Markdown')
    title = parts[1]
    db = load_json(DB_FILE)
    db.setdefault(uid, {})[title] = last_generated[uid]
    save_json(DB_FILE, db)
    log_action(uid, f"Save {title}")
    bot.send_message(message.chat.id, f"✅ Збережено: **{title}**", parse_mode='Markdown')

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'): return
    score, tips = check_strength(message.text)
    level = "🟢 НАДІЙНИЙ" if score >= 4 else ("🟡 СЕРЕДНІЙ" if score >= 2 else "🔴 СЛАБКИЙ")
    response = f"{level}\n\n" + ("\n".join(tips) if tips else "Все ок!")
    bot.send_message(message.chat.id, response, parse_mode='Markdown')
    log_action(message.from_user.id, f"Check {score}")

# АДМІНКА
@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    users = load_json(USERS_FILE)
    db = load_json(DB_FILE)
    text = f"👑 Адмінка\n👥 Юзерів: {len(users)}\n📚 Паролів: {sum(len(v) for v in db.values())}\n\n/admin_users\n/admin_libs\n/admin_stats"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['admin_users'])
def admin_users(message):
    if message.from_user.id != ADMIN_ID: return
    users = load_json(USERS_FILE)
    if not users:
        return bot.send_message(message.chat.id, "📭 Немає")
    text = "👥 Юзери:\n" + "\n".join(f"`{u}` - {d['first_name']}" for u, d in users.items())
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['admin_libs'])
def admin_libs(message):
    if message.from_user.id != ADMIN_ID: return
    db = load_json(DB_FILE)
    if not db:
        return bot.send_message(message.chat.id, "📭 Порожньо")
    text = "📚 Паролі:\n"
    for u, p in db.items():
        text += f"👤 {u}:\n" + "\n".join(f"  {k}: {v}" for k, v in p.items()) + "\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['admin_stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID: return
    logs = load_json(LOG_FILE)
    total = sum(len(v) for v in logs.values())
    bot.send_message(message.chat.id, f"📊 Всього дій: {total}")

@app.route('/')
def home():
    return "Bot is alive!"

def run_bot():
    print("🤖 Starting...")
    bot.remove_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
