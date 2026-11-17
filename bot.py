import telebot
import random
import string
import json
import os
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading

TOKEN = '9060513665:AAFIsr_Ef0R1AY55f4I3O5s0tT110TGztOE'
ADMIN_ID = 7623353420 

bot = telebot.TeleBot(TOKEN)
DB_FILE = 'passwords.json'
USERS_FILE = 'users.json'
LOG_FILE = 'bot_logs.json'
last_generated = {}

def load_db(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_db(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def log_action(user_id, action):
    logs = load_db(LOG_FILE)
    uid = str(user_id)
    if uid not in logs: logs[uid] = []
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logs[uid].append(f"[{time_now}] {action}")
    logs[uid] = logs[uid][-50:]
    save_db(LOG_FILE, logs)

def register_user(user_id, username, first_name):
    users = load_db(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {"username": username, "first_name": first_name, "joined": datetime.now().strftime("%Y-%m-%d %H:%M")}
        save_db(USERS_FILE, users)
        log_action(user_id, "Зареєструвався")

def generate_password(length=12):
    chars = string.ascii_letters + string.digits + '!@#$%^&*()'
    pwd = [random.choice(string.ascii_lowercase), random.choice(string.ascii_uppercase), random.choice(string.digits)]
    pwd += [random.choice(chars) for _ in range(length - 3)]
    random.shuffle(pwd)
    return ''.join(pwd)

def get_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔐 Пароль 12", callback_data="gen_12"), InlineKeyboardButton("🔐 Пароль 16", callback_data="gen_16"))
    markup.add(InlineKeyboardButton("📚 Моя бібліотека", callback_data="my_lib"))
    markup.add(InlineKeyboardButton("🛡️ Перевірити пароль", callback_data="check_info"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def start(message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    bot.send_message(message.chat.id, "👋 Привіт! Обери дію:", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    user_id = str(call.from_user.id)
    if call.data.startswith('gen_'):
        pwd = generate_password(int(call.data.split('_')[1]))
        last_generated[user_id] = pwd
        bot.send_message(call.message.chat.id, f"🔐 Пароль:\n`{pwd}`\n\n💾 Зберегти: `/save Назва`", parse_mode='Markdown')
    elif call.data == 'my_lib':
        db = load_db(DB_FILE)
        if user_id not in db or not db[user_id]: bot.send_message(call.message.chat.id, "📭 Порожньо.")
        else:
            text = "📚 **Твої паролі:**\n\n"
            for title, pwd in db[user_id].items(): text += f"🔹 **{title}**: `{pwd}`\n"
            bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
    elif call.data == 'check_info':
        bot.send_message(call.message.chat.id, "🛡️ Надішли мені пароль, і я перевірю!")

@bot.message_handler(commands=['save'])
def save_password(message):
    user_id = str(message.from_user.id)
    if user_id not in last_generated: return bot.send_message(message.chat.id, "❌ Спочатку згенеруй пароль!")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return
    db = load_db(DB_FILE)
    if user_id not in db: db[user_id] = {}
    db[user_id][parts[1]] = last_generated[user_id]
    save_db(DB_FILE, db)
    bot.send_message(message.chat.id, f"✅ Збережено: {parts[1]}")

@bot.message_handler(content_types=['text'])
def text_handler(message):
    if message.text.startswith('/'): return
    pwd = message.text
    score = (2 if len(pwd)>=12 else 1 if len(pwd)>=8 else 0) + (1 if any(c.isupper() for c in pwd) else 0) + (1 if any(c.islower() for c in pwd) else 0) + (1 if any(c.isdigit() for c in pwd) else 0) + (1 if any(c in '!@#$%^&*()' for c in pwd) else 0)
    if score >= 6: bot.send_message(message.chat.id, "🟢 **НАДІЙНИЙ!**")
    else: bot.send_message(message.chat.id, "🔴 **СЛАБКИЙ!**")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    bot.send_message(message.chat.id, "👑 Адмінка працює!")

app = Flask(__name__)
@app.route('/')
def index(): return "Bot is running"

def run_bot(): bot.polling(none_stop=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))