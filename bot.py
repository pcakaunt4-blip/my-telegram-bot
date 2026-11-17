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
user_settings = {}

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

def generate_password(length=12, use_upper=True, use_digits=True, use_special=True, exclude_similar=False):
    chars = string.ascii_lowercase
    if use_upper: chars += string.ascii_uppercase
    if use_digits: chars += string.digits
    if use_special: chars += '!@#$%^&*()'
    
    if exclude_similar:
        for c in 'l1IoO0':
            chars = chars.replace(c, '')
            
    pwd = []
    if use_upper: pwd.append(random.choice(string.ascii_uppercase))
    if use_digits: pwd.append(random.choice(string.digits))
    if use_special: pwd.append(random.choice('!@#$%^&*()'))
    
    pwd += [random.choice(chars) for _ in range(length - len(pwd))]
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

def get_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⚡ Швидка генерація", callback_data="quick_gen"),
        InlineKeyboardButton("🎛️ Налаштувати", callback_data="custom_gen")
    )
    markup.add(
        InlineKeyboardButton("📚 Бібліотека", callback_data="my_lib"),
        InlineKeyboardButton("🛡️ Перевірка", callback_data="check_info")
    )
    markup.add(InlineKeyboardButton("📤 Експорт", callback_data="export_lib"))
    return markup

def get_custom_gen_keyboard(settings):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(f"Довжина: {settings.get('len', 12)}", callback_data="set_len"),
        InlineKeyboardButton(f"Великі: {'✅' if settings.get('upper', True) else '❌'}", callback_data="toggle_upper")
    )
    markup.add(
        InlineKeyboardButton(f"Цифри: {'✅' if settings.get('digits', True) else '❌'}", callback_data="toggle_digits"),
        InlineKeyboardButton(f"Спецсимв: {'✅' if settings.get('special', True) else '❌'}", callback_data="toggle_special")
    )
    markup.add(InlineKeyboardButton(f"Без схожих: {'✅' if settings.get('no_similar', False) else '❌'}", callback_data="toggle_similar"))
    markup.add(InlineKeyboardButton("🔐 Згенерувати!", callback_data="do_generate"))
    return markup

@bot.message_handler(commands=['start'])
def cmd_start(message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    bot.send_message(message.chat.id, "👋 Привіт! Я твій розумний генератор паролів.\nОбери дію:", reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    bot.answer_callback_query(call.id)
    uid = str(call.from_user.id)
    data = call.data
    
    if data == 'quick_gen':
        pwd = generate_password(16)
        last_generated[uid] = pwd
        log_action(uid, "Quick Gen 16")
        
        copy_kb = InlineKeyboardMarkup()
        copy_kb.add(InlineKeyboardButton("📋 Скопіювати", callback_data=f"copy_{pwd}"))
        
        bot.send_message(call.message.chat.id, f"🔐 Пароль:\n`{pwd}`\n\nЗберегти: `/save Назва`", 
                         reply_markup=copy_kb, parse_mode='Markdown')

    elif data == 'custom_gen':
        if uid not in user_settings:
            user_settings[uid] = {'len': 12, 'upper': True, 'digits': True, 'special': True, 'no_similar': False}
        bot.edit_message_text("🎛️ **Налаштування генерації:**", call.message.chat.id, call.message.message_id, 
                              reply_markup=get_custom_gen_keyboard(user_settings[uid]), parse_mode='Markdown')
                              
    elif data.startswith('toggle_'):
        key = data.replace('toggle_', '')
        user_settings.setdefault(uid, {})
        user_settings[uid][key] = not user_settings[uid].get(key, True if key != 'no_similar' else False)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, 
                                      reply_markup=get_custom_gen_keyboard(user_settings[uid]))
                                      
    elif data == 'set_len':
        bot.send_message(call.message.chat.id, "Напишіть бажану довжину пароля (4-64):")
        
    elif data == 'do_generate':
        s = user_settings.get(uid, {})
        pwd = generate_password(
            length=s.get('len', 12),
            use_upper=s.get('upper', True),
            use_digits=s.get('digits', True),
            use_special=s.get('special', True),
            exclude_similar=s.get('no_similar', False)
        )
        last_generated[uid] = pwd
        log_action(uid, f"Custom Gen ({s.get('len', 12)})")
        
        copy_kb = InlineKeyboardMarkup()
        copy_kb.add(InlineKeyboardButton("📋 Скопіювати", callback_data=f"copy_{pwd}"))
        bot.send_message(call.message.chat.id, f"🔐 Твій пароль:\n`{pwd}`\n\nЗберегти: `/save Назва`", 
                         reply_markup=copy_kb, parse_mode='Markdown')

    elif data.startswith('copy_'):
        bot.answer_callback_query(call.id, text="✅ Скопійовано!", show_alert=False)

    elif data == 'my_lib':
        db = load_json(DB_FILE)
        user_db = db.get(uid, {})
        if not user_db:
            bot.send_message(call.message.chat.id, "📭 Бібліотека порожня.")
        else:
            text = "📚 **Твої паролі:**\n\n" + "\n".join(f"🔹 **{k}**: `{v}`" for k, v in user_db.items())
            bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

    elif data == 'check_info':
        bot.send_message(call.message.chat.id, "🛡️ Надішли мені пароль текстом, і я перевірю його силу!")

    elif data == 'export_lib':
        db = load_json(DB_FILE)
        user_db = db.get(uid, {})
        if not user_db:
            return bot.send_message(call.message.chat.id, "📭 Немає що експортувати")
        
        content = "МОЇ ПАРОЛІ\n" + "="*30 + "\n\n"
        for title, pwd in user_db.items():
            content += f"{title}: {pwd}\n"
            
        filename = f"passwords_{uid}_{datetime.now():%Y%m%d}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
            
        with open(filename, 'rb') as f:
            bot.send_document(call.message.chat.id, f, caption="📥 Ось твій експорт паролів")
        
        os.remove(filename)
        log_action(uid, "Export")

@bot.message_handler(commands=['save'])
def cmd_save(message):
    uid = str(message.from_user.id)
    if uid not in last_generated:
        return bot.send_message(message.chat.id, "❌ Спочатку згенеруй пароль!")
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "❌ `/save НазваСервісу`", parse_mode='Markdown')
        
    title = parts[1]
    db = load_json(DB_FILE)
    db.setdefault(uid, {})[title] = last_generated[uid]
    save_json(DB_FILE, db)
    log_action(uid, f"Save {title}")
    bot.send_message(message.chat.id, f"✅ Збережено: **{title}**", parse_mode='Markdown')

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text.startswith('/'): return
    
    password = message.text
    score, tips = check_strength(password)
    level = "🟢 НАДІЙНИЙ" if score >= 4 else ("🟡 СЕРЕДНІЙ" if score >= 2 else "🔴 СЛАБКИЙ")
    
    response = f"{level}\n\n" + ("\n".join(tips) if tips else "Все ок!")
    bot.send_message(message.chat.id, response, parse_mode='Markdown')
    log_action(message.from_user.id, f"Check {score}")

@bot.message_handler(commands=['admin'])
def admin_handler(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ Доступ заборонено!")
    
    users = load_json(USERS_FILE)
    db = load_json(DB_FILE)
    total_pwds = sum(len(v) for v in db.values())
    
    text = (
        "👑 **АДМІН-ПАНЕЛЬ**\n\n"
        f"👥 Юзерів: {len(users)}\n"
        f"📚 Паролів: {total_pwds}\n\n"
        "/admin_users — Список юзерів\n"
        "/admin_libs — Всі паролі\n"
        "/admin_stats — Статистика\n"
        "/admin_broadcast — Розсилка"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['admin_users'])
def admin_users(message):
    if message.from_user.id != ADMIN_ID: return
    users = load_json(USERS_FILE)
    if not users: return bot.send_message(message.chat.id, "📭 Юзерів немає")
    
    text = "👥 **Юзери:**\n\n"
    for uid, data in users.items():
        name = data.get('first_name', '?')
        joined = data.get('joined', '?')
        text += f"`{uid}` | {name} | {joined}\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['admin_libs'])
def admin_libs(message):
    if message.from_user.id != ADMIN_ID: return
    db = load_json(DB_FILE)
    if not db: return bot.send_message(message.chat.id, "📭 Порожньо")
    
    text = "📚 **Всі паролі:**\n\n"
    for uid, passwords in db.items():
        text += f"👤 `{uid}`:\n"
        for title, pwd in passwords.items():
            text += f"  🔹 {title}: `{pwd}`\n"
        text += "\n"
        
    if len(text) > 4000: text = text[:3900] + "\n\n...обрізано"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['admin_stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID: return
    logs = load_json(LOG_FILE)
    total_users = len(load_json(USERS_FILE))
    total_actions = sum(len(ul) for ul in logs.values())
    
    text = (
        "📊 **СТАТИСТИКА**\n\n"
        f"👥 Всього юзерів: {total_users}\n"
        f"⚡ Всього дій: {total_actions}\n\n"
        "🔝 **Топ активних:**\n"
    )
    
    sorted_users = sorted(logs.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    for uid, ul in sorted_users:
        text += f"  🥇 `{uid}` — {len(ul)} дій\n"
        
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['admin_broadcast'])
def admin_broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "❌ `/admin_broadcast Текст`", parse_mode='Markdown')
    
    users = load_json(USERS_FILE)
    sent, failed = 0, 0
    status = bot.send_message(message.chat.id, "📤 Відправляю...")
    
    for uid in users.keys():
        try:
            bot.send_message(int(uid), f"📢 **Оголошення:**\n\n{parts[1]}", parse_mode='Markdown')
            sent += 1
        except: failed += 1
            
    bot.edit_message_text(f"✅ Готово!\n📤 Надіслано: {sent}\n❌ Помилки: {failed}", message.chat.id, status.message_id)

@app.route('/')
def home():
    return "Bot is alive!"

def run_bot():
    print("🤖 Long Polling started...")
    bot.remove_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Server on port {port}")
    app.run(host="0.0.0.0", port=port)
