import telebot
import random
import string
import json
import os
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading

TOKEN = os.environ.get('TOKEN')
ADMIN_ID = 7623353420 

bot = telebot.TeleBot(TOKEN)

# --- БАЗА ДАНИХ (ЗБЕРІГАЄТЬСЯ У ФАЙЛАХ) ---
DB_FILE = 'passwords.json'
USERS_FILE = 'users.json'
LOG_FILE = 'bot_logs.json'
last_generated = {}

def load_db(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_db(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def log_action(user_id, action):
    logs = load_db(LOG_FILE)
    uid = str(user_id)
    if uid not in logs: logs[uid] = []
    logs[uid].append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {action}")
    logs[uid] = logs[uid][-50:]
    save_db(LOG_FILE, logs)

def register_user(user_id, username, first_name):
    users = load_db(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {"username": username, "first_name": first_name, "joined": datetime.now().strftime("%Y-%m-%d %H:%M")}
        save_db(USERS_FILE, users)
        log_action(user_id, "Зареєструвався")

# --- ГЕНЕРАТОРИ ---
def generate_password(length=12, use_symbols=True):
    chars = string.ascii_letters + string.digits
    if use_symbols: chars += '!@#$%^&*()'
    pwd = [random.choice(string.ascii_lowercase), random.choice(string.ascii_uppercase), random.choice(string.digits)]
    pwd += [random.choice(chars) for _ in range(length - 3)]
    random.shuffle(pwd)
    return ''.join(pwd)

def generate_passphrase():
    words = ["apple", "horse", "sunset", "river", "cloud", "tiger", "stone", "green", 
             "light", "house", "music", "water", "fire", "wind", "star", "moon", 
             "dream", "code", "smart", "happy", "quick", "brown", "fox", "jump"]
    return "-".join(random.sample(words, 4))

# --- МЕНЮ ---
def get_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("🔐 8 символів", callback_data="gen_8"), InlineKeyboardButton("🔐 12 символів", callback_data="gen_12"))
    markup.add(InlineKeyboardButton("🔐 16 символів", callback_data="gen_16"), InlineKeyboardButton("🔐 20 символів", callback_data="gen_20"))
    markup.add(InlineKeyboardButton("🔤 Без символів", callback_data="gen_simple"), InlineKeyboardButton("🧠 Пароль-фраза", callback_data="gen_words"))
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
        if call.data == 'gen_simple':
            pwd = generate_password(12, use_symbols=False)
        elif call.data == 'gen_words':
            pwd = generate_passphrase()
        else:
            pwd = generate_password(int(call.data.split('_')[1]))
        
        last_generated[user_id] = pwd
        log_action(user_id, "Згенерував пароль")
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔄 Ще один", callback_data=call.data))
        bot.send_message(call.message.chat.id, f"🔐 Твій пароль:\n`{pwd}`\n\n💾 Зберегти: `/save Назва`", parse_mode='Markdown', reply_markup=markup)
    
    elif call.data == 'my_lib':
        db = load_db(DB_FILE)
        if user_id not in db or not db[user_id]:
            bot.send_message(call.message.chat.id, "📭 Твоя бібліотека порожня.")
        else:
            text = "📚 **Твої збережені паролі:**\n\n"
            markup = InlineKeyboardMarkup()
            for title, pwd in db[user_id].items():
                text += f"🔹 **{title}**: `{pwd}`\n"
                markup.add(InlineKeyboardButton(f"🗑 Видалити '{title}'", callback_data=f"del_{title}"))
            bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=markup)
            
    elif call.data.startswith('del_'):
        title = call.data.split('_', 1)[1]
        db = load_db(DB_FILE)
        if user_id in db and title in db[user_id]:
            del db[user_id][title]
            save_db(DB_FILE, db)
            bot.send_message(call.message.chat.id, f"🗑 Пароль для **{title}** видалено!", parse_mode='Markdown')
            log_action(user_id, f"Видалив '{title}'")

    elif call.data == 'check_info':
        bot.send_message(call.message.chat.id, "🛡️ Просто надішли мені будь-який текст (пароль), і я скажу, наскільки він надійний!")

@bot.message_handler(commands=['save'])
def save_password(message):
    user_id = str(message.from_user.id)
    if user_id not in last_generated:
        return bot.send_message(message.chat.id, "❌ Спочатку згенеруй пароль кнопкою!")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return bot.send_message(message.chat.id, "❌ Вкажи назву! Наприклад: `/save Пошта`")
    
    db = load_db(DB_FILE)
    if user_id not in db: db[user_id] = {}
    db[user_id][parts[1]] = last_generated[user_id]
    save_db(DB_FILE, db)
    log_action(user_id, f"Зберіг '{parts[1]}'")
    bot.send_message(message.chat.id, f"✅ Пароль для **{parts[1]}** збережено!", parse_mode='Markdown')

@bot.message_handler(content_types=['text'])
def text_handler(message):
    if message.text.startswith('/'): return
    pwd = message.text
    score = 0
    tips = []
    if len(pwd) >= 12: score += 2
    elif len(pwd) >= 8: score += 1
    else: tips.append("❌ Зроби довшим (мінімум 8).")
    if any(c.isupper() for c in pwd): score += 1
    else: tips.append("❌ Додай ВЕЛИКУ літеру.")
    if any(c.islower() for c in pwd): score += 1
    else: tips.append("❌ Додай малу літеру.")
    if any(c.isdigit() for c in pwd): score += 1
    else: tips.append("❌ Додай цифру.")
    if any(c in '!@#$%^&*()' for c in pwd): score += 1
    else: tips.append("❌ Додай спецсимвол.")

    if score >= 6: bot.send_message(message.chat.id, "🟢 **НАДІЙНИЙ ПАРОЛЬ!**")
    else: bot.send_message(message.chat.id, f"🔴 **СЛАБКИЙ ПАРОЛЬ.**\n" + "\n".join(tips), parse_mode='Markdown')
    log_action(message.from_user.id, "Перевірив пароль")

# --- АДМІН-ПАНЕЛЬ ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    users = load_db(USERS_FILE)
    db = load_db(DB_FILE)
    text = f"👑 **Адмін-панель**\n\n👥 Юзерів: {len(users)}\n💾 Паролів: {sum(len(p) for p in db.values
