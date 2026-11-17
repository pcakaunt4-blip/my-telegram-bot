import telebot
import random
import string
import json
import os
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
from flask import Flask, request

# --- КОНФІГУРАЦІЯ ---
TOKEN = '9060513665:AAFIsr_Ef0R1AY55f4I3O5s0tT110TGztOE'
ADMIN_ID = 7623353420 

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DB_FILE = 'passwords.json'
USERS_FILE = 'users.json'
LOG_FILE = 'bot_logs.json'
last_generated = {}

# --- РОБОТА З ДАНИМИ ---
def load_db(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_db(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def log_action(user_id, action):
    logs = load_db(LOG_FILE)
    uid = str(user_id)
    if uid not in logs: 
        logs[uid] = []
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logs[uid].append(f"[{time_now}] {action}")
    logs[uid] = logs[uid][-50:] # Зберігаємо тільки останні 50 дій
    save_db(LOG_FILE, logs)

def register_user(user_id, username, first_name):
    users = load_db(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": username or "NoUsername", 
            "first_name": first_name, 
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_db(USERS_FILE, users)
        log_action(user_id, "Зареєструвався в боті")

# --- ГЕНЕРАЦІЯ ТА ПЕРЕВІРКА ---
def generate_password(length=12):
    chars = string.ascii_letters + string.digits + '!@#$%^&*()'
    pwd = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.digits),
        random.choice('!@#$%^&*()')
    ]
    pwd += [random.choice(chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return ''.join(pwd)

def check_password_strength(password):
    score = 0
    tips = []
    
    if len(password) >= 12: score += 2
    elif len(password) >= 8: score += 1
    else: tips.append("❌ Зроби довшим (мінімум 8 символів).")
    
    if any(c.isupper() for c in password): score += 1
    else: tips.append("❌ Додай ВЕЛИКУ літеру.")
    
    if any(c.islower() for c in password): score += 1
    else: tips.append("❌ Додай малу літеру.")
    
    if any(c.isdigit() for c in password): score += 1
    else: tips.append("❌ Додай цифру.")
    
    if any(c in '!@#$%^&*()' for c in password): score += 1
    else: tips.append("❌ Додай спецсимвол (@, #, $).")

    return score, tips

# --- КЛАВІАТУРИ ---
def get_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    btn1 = InlineKeyboardButton("🔐 Пароль 12", callback_data="gen_12")
    btn2 = InlineKeyboardButton("🔐 Пароль 16", callback_data="gen_16")
    btn3 = InlineKeyboardButton("📚 Моя бібліотека", callback_data="my_lib")
    btn4 = InlineKeyboardButton("🛡️ Перевірити пароль", callback_data="check_info")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    return markup

# --- ХЕНДЛЕРИ БОТА ---
@bot.message_handler(commands=['start', 'help'])
def start(message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    text = "👋 Привіт! Я твій розумний генератор паролів.\nОбери дію на кнопках нижче:"
    bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    user_id = str(call.from_user.id)

    if call.data.startswith('gen_'):
        length = int(call.data.split('_')[1])
        pwd = generate_password(length)
        last_generated[user_id] = pwd
        log_action(user_id, f"Згенерував пароль довжиною {length}")
        
        msg_text = f"🔐 Твій новий пароль:\n`{pwd}`\n\n💾 Щоб зберегти його в бібліотеку, напиши:\n`/save НазваСервісу`"
        bot.send_message(call.message.chat.id, msg_text, parse_mode='Markdown')
    
    elif call.data == 'my_lib':
        db = load_db(DB_FILE)
        if user_id not in db or not db[user_id]:
            bot.send_message(call.message.chat.id, "📭 Твоя бібліотека поки що порожня. Згенеруй і збережи перший пароль!")
        else:
            text = "📚 **Твої збережені паролі:**\n\n"
            for title, pwd in db[user_id].items():
                text += f"🔹 **{title}**: `{pwd}`\n"
            bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
            log_action(user_id, "Переглянув бібліотеку")
            
    elif call.data == 'check_info':
        bot.send_message(call.message.chat.id, "🛡️ Режим перевірки активований!\nПросто надішли мені будь-який текст (пароль), і я оціню його надійність.")

@bot.message_handler(commands=['save'])
def save_password(message):
    user_id = str(message.from_user.id)
    if user_id not in last_generated:
        bot.send_message(message.chat.id, "❌ Спочатку згенеруй пароль за допомогою кнопок!")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Вкажи назву сервісу! Наприклад: `/save Instagram`", parse_mode='Markdown')
        return
    
    title = parts[1]
    db = load_db(DB_FILE)
    if user_id not in db: 
        db[user_id] = {}
    
    db[user_id][title] = last_generated[user_id]
    save_db(DB_FILE, db)
    log_action(user_id, f"Зберіг пароль для '{title}'")
    bot.send_message(message.chat.id, f"✅ Пароль для **{title}** успішно збережено!", parse_mode='Markdown')

@bot.message_handler(content_types=['text'])
def text_handler(message):
    if message.text.startswith('/'):
        return
    
    password = message.text
    score, tips = check_password_strength(password)
    
    if score >= 5:
        result = "🟢 **НАДІЙНИЙ ПАРОЛЬ!**\nМожна використовувати."
    elif score >= 3:
        result = "🟡 **СЕРЕДНІЙ РІВЕНЬ.**\nКраще посилити."
    else:
        result = "🔴 **СЛАБКИЙ ПАРОЛЬ.**"
        
    response = f"{result}\n\n"
    if tips:
        response += "Поради:\n" + "\n".join(tips)
        
    bot.send_message(message.chat.id, response, parse_mode='Markdown')
    log_action(message.from_user.id, f"Перевірив пароль (Оцінка: {score})")

# --- АДМІН ПАНЕЛЬ ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: 
        return
    text = "👑 **Адмін-панель**\n\n/admin_users - Список юзерів\n/admin_libs - Всі паролі\n/admin_logs - Логи дій"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['admin_users'])
def admin_users(message):
    if message.from_user.id != ADMIN_ID: return
    users = load_db(USERS_FILE)
    text = "👥 **Юзери бота:**\n\n"
    for uid, info in users.items():
        text += f"ID: `{uid}` | {info.get('first_name')} (@{info.get('username')})\n"
    bot.send_message(message.chat.id, text,
