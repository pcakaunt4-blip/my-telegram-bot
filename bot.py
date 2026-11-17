# -*- coding: utf-8 -*-

import os
import json
import time
import random
import string
import secrets
import threading
import re
import html
from datetime import datetime
from flask import Flask
import telebot
from telebot import types

# ==================================
# НАЛАШТУВАННЯ
# ==================================

TOKEN = os.getenv("TOKEN", "").strip()
ADMIN_ID = 7623353420

if not TOKEN:
    raise ValueError("Не знайдено TOKEN! Додай токен у змінні середовища.")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DB_FILE = "bot_database.json"
lock = threading.RLock()

# ==================================
# БАЗА ДАНИХ
# ==================================

def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "users": {},
            "library": {},
            "logs": {},
            "banned": []
        }

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        data.setdefault("users", {})
        data.setdefault("library", {})
        data.setdefault("logs", {})
        data.setdefault("banned", [])

        return data

    except (json.JSONDecodeError, OSError):
        return {
            "users": {},
            "library": {},
            "logs": {},
            "banned": []
        }


db = load_db()


def save_db():
    with lock:
        temp = DB_FILE + ".tmp"

        with open(temp, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=4)

        os.replace(temp, DB_FILE)


def log_action(user_id, action):
    uid = str(user_id)

    with lock:
        db["logs"].setdefault(uid, [])

        db["logs"][uid].append({
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "action": action
        })

        db["logs"][uid] = db["logs"][uid][-50:]

        save_db()


def register_user(user):
    uid = str(user.id)

    with lock:
        is_new = uid not in db["users"]

        db["users"][uid] = {
            "id": user.id,
            "username": user.username or "",
            "first_name": user.first_name or "Без імені",
            "joined": db["users"].get(
                uid, {}
            ).get(
                "joined",
                datetime.now().strftime("%d.%m.%Y %H:%M")
            )
        }

        db["library"].setdefault(uid, [])

        save_db()

    if is_new:
        log_action(user.id, "Новий користувач")


def is_banned(user_id):
    return str(user_id) in db["banned"]


def check_access(message):
    register_user(message.from_user)

    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ Ти заблокований.")
        return False

    return True


# ==================================
# ГОЛОВНЕ МЕНЮ
# ==================================

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)

    markup.add(
        types.InlineKeyboardButton(
            "🔐 Пароль",
            callback_data="password_menu"
        ),
        types.InlineKeyboardButton(
            "😎 Нік",
            callback_data="nickname"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔤 Парольна фраза",
            callback_data="passphrase"
        ),
        types.InlineKeyboardButton(
            "📚 Бібліотека",
            callback_data="library"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🛡 Перевірка пароля",
            callback_data="check_password"
        ),
        types.InlineKeyboardButton(
            "⏰ Нагадування",
            callback_data="reminder_help"
        )
    )

    return markup


# ==================================
# ГЕНЕРАТОР ПАРОЛІВ
# ==================================

def generate_password(length=16, symbols=True):

    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*()-_=+"

    alphabet = lower + upper + digits

    if symbols:
        alphabet += special

    groups = [lower, upper, digits]

    if symbols:
        groups.append(special)

    result = [
        secrets.choice(group)
        for group in groups
    ]

    while len(result) < length:
        result.append(secrets.choice(alphabet))

    secrets.SystemRandom().shuffle(result)

    return "".join(result)


def generate_passphrase():
    words = [
        "apple", "horse", "sunset", "river",
        "cloud", "tiger", "stone", "green",
        "dragon", "forest", "moon", "star",
        "ocean", "winter", "summer", "fire"
    ]

    return "-".join(secrets.SystemRandom().sample(words, 4))


# ==================================
# ГЕНЕРАТОР НІКІВ
# ==================================

def generate_nickname():

    adjectives = [
        "Cool", "Smart", "Fast", "Dark",
        "Light", "Brave", "Crazy", "Silent",
        "Super", "Mega", "Ultra", "Shadow"
    ]

    nouns = [
        "Tiger", "Wolf", "Eagle", "Lion",
        "Fox", "Bear", "Dragon", "Ghost",
        "Ninja", "Pirate", "King", "Legend"
    ]

    return (
        secrets.choice(adjectives)
        + "_"
        + secrets.choice(nouns)
        + "_"
        + str(secrets.randbelow(990) + 10)
    )


# ==================================
# БІБЛІОТЕКА
# ==================================

def save_item(user_id, title, value):

    uid = str(user_id)

    with lock:
        db["library"].setdefault(uid, [])

        db["library"][uid].append({
            "title": title[:40],
            "value": value,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        })

        save_db()

    log_action(user_id, "Зберіг результат")


def show_library(chat_id, user_id):

    items = db["library"].get(str(user_id), [])

    if not items:
        bot.send_message(chat_id, "📚 Твоя бібліотека порожня.")
        return

    text = "📚 <b>ТВОЯ БІБЛІОТЕКА</b>\n\n"

    markup = types.InlineKeyboardMarkup()

    for i, item in enumerate(items[-15:]):
        number = len(items) - min(len(items), 15) + i

        text += (
            f"<b>{number + 1}. "
            f"{html.escape(item['title'])}</b>\n"
            f"<code>{html.escape(item['value'])}</code>\n"
            f"<i>{html.escape(item['date'])}</i>\n\n"
        )

        markup.add(
            types.InlineKeyboardButton(
                f"🗑 Видалити №{number + 1}",
                callback_data=f"delete_{number}"
            )
        )

    bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=markup
    )


# ==================================
# ОСТАННІ ГЕНЕРАЦІЇ
# ==================================

last_generated = {}
waiting_check = set()


def send_generated(message, value, title):

    user_id = message.from_user.id

    last_generated[user_id] = (title, value)

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "💾 Зберегти в бібліотеку",
            callback_data="save_result"
        )
    )

    markup.add(
