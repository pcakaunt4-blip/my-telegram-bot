# -*- coding: utf-8 -*-
import telebot
import random
import string
import json
import os
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading
import time

TOKEN = os.environ.get('TOKEN')
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
    logs[uid].append(str(datetime.now().strftime('%Y-%m-%d %H:%M')) + " - " + action)
    logs[uid] = logs[uid][-50:]
    save_db(LOG_FILE, logs)

def register_user(user_id, username, first_name):
    users = load_db(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {"username": username, "first_name": first_name, "joined": datetime.now().strftime("%Y-%m-%d %H:%M")}
        save_db(USERS_FILE, users)
        log_action(user_id, "Зареєструвався")

def generate_password(length=12, use_symbols=True):
    chars = string.ascii_letters + string.digits
    if use_symbols: chars += '!@#$%^&*()'
    pwd = [random.choice(string.ascii_lowercase), random.choice(string.ascii_uppercase), random.choice(string.digits)]
    pwd += [random.choice(chars) for _ in range(length - 3)]
    random.shuffle(pwd)
    return ''.join(pwd)

def generate_passphrase():
    words = ["apple", "horse", "sunset", "river", "cloud", "tiger", "stone", "green"]
    return "-".join(random.sample(words, 4))

def generate_nickname():
    adjectives = ["cool", "smart", "fast", "dark", "light", "brave", "crazy", "silent", "super", "mega"]
    nouns = ["tiger", "wolf", "eagle", "lion", "fox", "bear", "dragon", "ghost", "ninja", "pirate"]
    return random.choice(adjectives) + "_" + random.choice(nouns) + "_" + str(random.randint(10, 99))

def get_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("8 симв", callback_data="gen_8"), InlineKeyboardButton("12 симв", callback_data="gen_12"))
    markup.add(InlineKeyboardButton("16 симв", callback_data="gen_16"), InlineKeyboardButton("20 симв", callback_data="gen_20"))
    markup.add(InlineKeyboardButton("Без спецсимволів", callback_data="gen_simple"), InlineKeyboardButton("Фраза", callback_data="gen_words"))
    markup.add(InlineKeyboardButton("Нікнейм", callback_data="gen_nick"))
    markup.add(InlineKeyboardButton("Моя бібліотека", callback_data="my_lib"))
    markup.add(InlineKeyboardButton("Перевірити пароль", callback_data="check_info"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def start(message):
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    text = "Привіт! Обери дію:\n\nТакож я вмію нагадувати! Напиши /remind 5 хв Купити хліб"
    bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)
    user_id = str(call.from_user.id)

    if call.data.startswith('gen_'):
        if call.data == 'gen_simple':
            pwd = generate_password(12, use_symbols=False)
        elif call.data == 'gen_words':
            pwd = generate_passphrase()
        elif call.data == 'gen_nick':
            nick = generate_nickname()
            bot.send_message(call.message.chat.id, "Твій нікнейм: `" + nick + "`", parse_mode='Markdown')
            return
        else:
            pwd = generate_password(int(call.data.split('_')[1]))
        
        last_generated[user_id] = pwd
        log_action(user_id, "Згенерував пароль")
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Ще один", callback_data=call.data))
        bot.send_message(call.message.chat.id, "Твій пароль: `" + pwd + "`\n\nЗберегти: /save Назва", parse_mode='Markdown', reply_markup=markup)
    
    elif call.data == 'my_lib':
        db = load_db(DB_FILE)
        if user_id not in db or not db[user_id]:
            bot.send_message(call.message.chat.id, "Порожньо.")
        else:
            text = "Твої паролі:\n\n"
            markup = InlineKeyboardMarkup()
            for title, pwd in db[user_id].items():
                text += "- " + title + ": `" + pwd + "`\n"
                markup.add(InlineKeyboardButton("Видалити " + title, callback_data="del_" + title))
            bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=markup)
            
    elif call.data.startswith('del_'):
        title = call.data.split('_', 1)[1]
        db = load_db(DB_FILE)
        if user_id in db and title in db[user_id]:
            del db[user_id][title]
            save_db(DB_FILE, db)
            bot.send_message(call.message.chat.id, "Видалено: " + title)

    elif call.data == 'check_info':
        bot.send_message(call.message.chat.id, "Надішли мені пароль!")

@bot.message_handler(commands=['save'])
def save_password(message):
    user_id = str(message.from_user.id)
    if user_id not in last_generated:
        return bot.send_message(message.chat.id, "Спочатку згенеруй пароль!")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return
    
    db = load_db(DB_FILE)
    if user_id not in db: db[user_id] = {}
    db[user_id][parts[1]] = last_generated[user_id]
    save_db(DB_FILE, db)
    log_action(user_id, "Зберіг " + parts[1])
    bot.send_message(message.chat.id, "Збережено: " + parts[1])

# --- ФУНКЦІЯ НАГАДУВАННЯ ---
@bot.message_handler(commands=['remind'])
def set_reminder(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return bot.send_message(message.chat.id, "Формат: /remind 10 хв Текст\nАбо: /remind 1 год Подзвонити")
    
    try:
        time_val = int(parts[1])
        unit = parts[1].lower()
        text_remind = parts[2]
        
        if 'хв' in unit or 'мин' in unit or 'min' in unit:
            seconds = time_val * 60
        elif 'год' in unit or 'час' in unit or 'h' in unit:
            seconds = time_val * 3600
        else:
            return bot.send_message(message.chat.id, "Вкажи час: хв або год")
            
        bot.send_message(message.chat.id, "Добре! Нагадаю через " + str(time_val) + ".")
        
        def send_reminder():
            time.sleep(seconds)
            bot.send_message(message.chat.id, "НАГАДУВАННЯ:\n" + text_remind)
            
        threading.Thread(target=send_reminder).start()
        
    except:
        bot.send_message(message.chat.id, "Помилка. Приклад: /remind 5 хв Купити молоко")

@bot.message_handler(content_types=['t
