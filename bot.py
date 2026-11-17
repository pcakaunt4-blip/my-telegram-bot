# -*- coding: utf-8 -*-
import os
import json
import time
import random
import string
import secrets
import threading
import html
from datetime import datetime

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from cryptography.fernet import Fernet, InvalidToken

# ================== CONFIG ==================

TOKEN = os.environ.get("TOKEN")
ADMIN_ID = 7623353420

if not TOKEN:
    raise RuntimeError("Додай TOKEN у змінні середовища!")

# Ключ шифрування. Створюється один раз і зберігається у файлі.
KEY_FILE = "encryption.key"

if os.environ.get("ENCRYPTION_KEY"):
    ENCRYPTION_KEY = os.environ["ENCRYPTION_KEY"].encode()
elif os.path.exists(KEY_FILE):
    with open(KEY_FILE, "rb") as f:
        ENCRYPTION_KEY = f.read()
else:
    ENCRYPTION_KEY = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(ENCRYPTION_KEY)

cipher = Fernet(ENCRYPTION_KEY)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DB_FILE = "passwords.json"
USERS_FILE = "users.json"
LOG_FILE = "bot_logs.json"

last_generated = {}
settings = {}
waiting_save = set()
waiting_check = set()
waiting_length = set()

db_lock = threading.RLock()

# ================== DATABASE ==================

def load_db(filename):
    with db_lock:
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}


def save_db(filename, data):
    with db_lock:
        temp = filename + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp, filename)


def log_action(user_id, action):
    logs = load_db(LOG_FILE)
    uid = str(user_id)

    if uid not in logs:
        logs[uid] = []

    logs[uid].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "action": action
    })

    logs[uid] = logs[uid][-50:]
    save_db(LOG_FILE, logs)


def register_user(user):
    users = load_db(USERS_FILE)
    uid = str(user.id)

    if uid not in users:
        users[uid] = {
            "username": user.username or "",
            "first_name": user.first_name or "",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "generations": 0
        }
        log_action(user.id, "Реєстрація")

    else:
        users[uid]["username"] = user.username or ""
        users[uid]["first_name"] = user.first_name or ""

    save_db(USERS_FILE, users)


def increment_generation(user_id):
    users = load_db(USERS_FILE)
    uid = str(user_id)

    if uid in users:
        users[uid]["generations"] = (
            users[uid].get("generations", 0) + 1
        )
        save_db(USERS_FILE, users)


# ================== PASSWORD STORAGE ==================

def get_user_passwords(user_id):
    data = load_db(DB_FILE)
    uid = str(user_id)

    if uid not in data:
        data[uid] = []

    # Підтримка старої бази: зашифровуємо старі записи.
    if isinstance(data[uid], dict):
        migrated = []

        for title, password in data[uid].items():
            migrated.append({
                "id": secrets.token_hex(4),
                "title": title,
                "password": cipher.encrypt(
                    str(password).encode()
                ).decode(),
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")
            })

        data[uid] = migrated
        save_db(DB_FILE, data)

    return data[uid]


def save_password(user_id, title, password):
    data = load_db(DB_FILE)
    uid = str(user_id)

    if uid not in data:
        data[uid] = []

    if isinstance(data[uid], dict):
        data[uid] = []

    if len(data[uid]) >= 100:
        return False

    encrypted = cipher.encrypt(password.encode()).decode()

    data[uid].append({
        "id": secrets.token_hex(4),
        "title": title[:40],
        "password": encrypted,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    })

    save_db(DB_FILE, data)
    return True


def decrypt_password(encrypted):
    return cipher.decrypt(encrypted.encode()).decode()


def delete_password(user_id, entry_id):
    data = load_db(DB_FILE)
    uid = str(user_id)

    if uid not in data:
        return False

    old_length = len(data[uid])

    data[uid] = [
        item for item in data[uid]
        if item.get("id") != entry_id
    ]

    save_db(DB_FILE, data)
    return len(data[uid]) < old_length


# ================== GENERATORS ==================

def default_settings():
    return {
        "length": 16,
        "upper": True,
        "lower": True,
        "digits": True,
        "symbols": False
    }


def generate_password(options):
    chars = ""
    required = []

    if options["upper"]:
        chars += string.ascii_uppercase
        required.append(secrets.choice(string.ascii_uppercase))

    if options["lower"]:
        chars += string.ascii_lowercase
        required.append(secrets.choice(string.ascii_lowercase))

    if options["digits"]:
        chars += string.digits
        required.append(secrets.choice(string.digits))

    if options["symbols"]:
        symbols = "!@#$%^&*()-_=+[]{}?"
        chars += symbols
        required.append(secrets.choice(symbols))

    if not chars:
        return None

    length = options["length"]

    if length < len(required):
        return None

    result = required + [
        secrets.choice(chars)
        for _ in range(length - len(required))
    ]

    secrets.SystemRandom().shuffle(result)
    return "".join(result)


def generate_passphrase():
    words = [
        "apple", "horse", "sunset", "river",
        "cloud", "tiger", "stone", "green",
        "forest", "planet", "silver", "ocean",
        "rocket", "winter", "orange", "shadow"
    ]

    return "-".join(secrets.SystemRandom().sample(words, 4))


def generate_nickname():
    adjectives = [
        "cool", "smart", "fast", "dark", "light",
        "brave", "crazy", "silent", "super", "mega",
        "happy", "wild", "epic", "shadow"
    ]

    nouns = [
        "tiger", "wolf", "eagle", "lion", "fox",
        "bear", "dragon", "ghost", "ninja", "pirate",
        "hunter", "storm", "legend", "king"
    ]

    return (
        secrets.choice(adjectives) + "_" +
        secrets.choice(nouns) + "_" +
        str(secrets.randbelow(900) + 100)
    )


# ================== KEYBOARDS ==================

def main_keyboard(user_id):
    markup = InlineKeyboardMarkup(row_width=2)

    markup.add(
        InlineKeyboardButton("🔐 Генератор паролів", callback_data="generator"),
        InlineKeyboardButton("👤 Нікнейм", callback_data="nickname")
    )

    markup.add(
        InlineKeyboardButton("📚 Моя бібліотека", callback_data="library"),
        InlineKeyboardButton("🛠 Перевірити пароль", callback_data="check")
    )

    markup.add(
        InlineKeyboardButton("ℹ
