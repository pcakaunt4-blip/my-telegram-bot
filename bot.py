
import os
import sqlite3
import string
import secrets
import html
import threading
from datetime import datetime

import telebot
from telebot import types
from flask import Flask

from cryptography.fernet import Fernet


# =====================================
# НАСТРОЙКИ
# =====================================

TOKEN = "ВСТАВЬ_СЮДА_ТОКЕН_BOTFATHER"
ADMIN_ID = 123456789  # ТВОЙ TELEGRAM ID

PORT = int(os.environ.get("PORT", 10000))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DB = "bot.db"
LOCK = threading.Lock()

settings = {}
states = {}


# =====================================
# ШИФРОВАНИЕ
# =====================================

if not os.path.exists("secret.key"):
    with open("secret.key", "wb") as f:
        f.write(Fernet.generate_key())

with open("secret.key", "rb") as f:
    cipher = Fernet(f.read())


# =====================================
# БАЗА ДАННЫХ
# =====================================

def connect():
    return sqlite3.connect(DB, timeout=30)


def init_db():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                joined TEXT
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                user_id INTEGER PRIMARY KEY,
                generations INTEGER DEFAULT 0
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS passwords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                password TEXT,
                created TEXT
            )
        """)


def register(user):
    with LOCK, connect() as con:
        con.execute("""
            INSERT OR IGNORE INTO users
            VALUES (?, ?, ?)
        """, (
            user.id,
            user.username or "unknown",
            datetime.now().isoformat()
        ))

        con.execute("""
            INSERT OR IGNORE INTO stats
            VALUES (?, 0)
        """, (user.id,))


# =====================================
# ГЛАВНОЕ МЕНЮ
# =====================================

def main_menu():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )

    kb.add(
        "🎲 Генератор ников",
        "🔐 Мои пароли"
    )

    kb.add(
        "⚙️ Настройки",
        "ℹ️ Инструкция"
    )

    if ADMIN_ID:
        kb.add("👑 Админ-панель")

    return kb


def generator_menu():
    kb = types.InlineKeyboardMarkup()

    kb.add(types.InlineKeyboardButton(
        "🎲 Сгенерировать ники",
        callback_data="generate"
    ))

    kb.add(types.InlineKeyboardButton(
        "⚙️ Настройки",
        callback_data="settings"
    ))

    return kb


# =====================================
# START
# =====================================

@bot.message_handler(commands=["start"])
def start(message):
    if message.chat.type != "private":
        return

    register(message.from_user)

    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать!\n\n"
        "🎲 Генератор никнеймов\n"
        "🔐 Личная библиотека паролей\n"
        "⚙️ Настройки генерации\n"
        "👑 Админ-панель\n\n"
        "Выбери нужный раздел:",
        reply_markup=main_menu()
    )


# =====================================
# ГЕНЕРАТОР НИКОВ
# =====================================

def generate_nick(length, mode):
    chars = string.ascii_lowercase

    if mode in ["numbers", "mixed", "symbols"]:
        chars += string.digits

    if mode == "mixed":
        chars += string.ascii_uppercase

    if mode == "symbols":
        chars += "_-."

    return "".join(
        secrets.choice(chars)
        for _ in range(length)
    )


@bot.message_handler(
    func=lambda m: m.text == "🎲 Генератор ников"
)
def generator(message):
    bot.send_message(
        message.chat.id,
        "🎲 ГЕНЕРАТОР НИКНЕЙМОВ",
        reply_markup=generator_menu()
    )


@bot.callback_query_handler(
    func=lambda c: c.data == "generate"
)
def generate(call):
    uid = call.from_user.id

    s = settings.get(uid, {})

    length = s.get("length", 12)
    count = s.get("count", 5)
    mode = s.get("mode", "mixed")

    result = []

    for _ in range(count):
        result.append(generate_nick(length, mode))

    with LOCK, connect() as con:
        con.execute("""
            UPDATE stats
            SET generations = generations + ?
            WHERE user_id = ?
        """, (count, uid))

    text = "🎲 <b>ТВОИ НИКНЕЙМЫ</b>\n\n"

    for i, nick in enumerate(result, 1):
        text += f"{i}. <code>{nick}</code>\n"

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=generator_menu()
    )


# =====================================
# НАСТРОЙКИ
# =====================================

def show_settings(chat_id):
    kb = types.InlineKeyboardMarkup(row_width=2)

    for n in [6, 8, 10, 12, 16, 20, 24, 32]:
        kb.add(types.InlineKeyboardButton(
            f"📏 {n} символов",
            callback_data=f"len:{n}"
        ))

    kb.add(
        types.InlineKeyboardButton(
            "🔤 Буквы",
            callback_data="mode:letters"
        ),
        types.InlineKeyboardButton(
            "🔢 Цифры",
            callback_data="mode:numbers"
        )
    )

    kb.add(
        types.InlineKeyboardButton(
            "🔠 Смешанный",
            callback_data="mode:mixed"
        ),
        types.InlineKeyboardButton(
            "✨ Символы",
            callback_data="mode:symbols"
        )
    )

    for n in [1, 5, 10, 20, 50]:
        kb.add(types.InlineKeyboardButton(
            f"Количество: {n}",
            callback_data=f"count:{n}"
        ))

    bot.send_message(
        chat_id,
        "⚙️ <b>НАСТРОЙКИ ГЕНЕРАТОРА</b>",
        parse_mode="HTML",
        reply_markup=kb
    )


@bot.message_handler(
    func=lambda m: m.text == "⚙️ Настройки"
)
def settings_button(message):
    show_settings(message.chat.id)


@bot.callback_query_handler(
    func=lambda c: c.data == "settings"
)
def settings_callback(call):
    bot.answer_callback_query(call.id)
    show_settings(call.message.chat.id)


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("len:")
)
def set_length(call):
    n = int(call.data.split(":")[1])

    settings.setdefault(
        call.from_user.id, {}
    )["length"] = n

    bot.answer_callback_query(
        call.id,
        f"Длина: {n} символов"
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("mode:")
)
def set_mode(call):
    mode = call.data.split(":")[1]

    settings.setdefault(
        call.from_user.id, {}
    )["mode"] = mode

    bot.answer_callback_query(
        call.id,
        "Режим изменён!"
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("count:")
)
def set_count(call):
    n = int(call.data.split(":")[1])

    settings.setdefault(
        call.from_user.id, {}
    )["count"] = n

    bot.answer_callback_query(
        call.id,
        f"Количество: {n}"
    )


# =====================================
# БИБЛИОТЕКА ПАРОЛЕЙ
# =====================================

@bot.message_handler(
    func=lambda m: m.text == "🔐 Мои пароли"
)
def vault(message):
    if message.chat.type != "private":
        return

    kb = types.InlineKeyboardMarkup()

    kb.add(types.InlineKeyboardButton(
        "➕ Добавить пароль",
        callback_data="add"
    ))

    kb.add(types.InlineKeyboardButton(
        "📂 Мои записи",
        callback_data="list"
    ))

    bot.send_message(
        message.chat.id,
        "🔐 <b>ЛИЧНАЯ БИБЛИОТЕКА</b>",
        parse_mode="HTML",
        reply_markup=kb
    )


@bot.callback_query_handler(
    func=lambda c: c.data == "add"
)
def add_password_start(call):
    if call.message.chat.type != "private":
        bot.answer_callback_query(call.id)
        return

    states[call.from_user.id] = {
        "step": "name"
    }

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "📝 Введи название записи:"
    )


def save_name(message):
    name = (message.text or "").strip()

    if not name or len(name) > 80:
        bot.send_message(
            message.chat.id,
            "Название должно содержать от 1 до 80 символов."
        )
        return

    states[message.from_user.id] = {
        "step": "password",
        "name": name
    }

    bot.send_message(
        message.chat.id,
        "🔐 Теперь введи пароль:"
    )


def save_password(message):
    password = message.text or ""

    if not password or len(password) > 500:
        bot.send_message(
            message.chat.id,
            "Некорректный пароль. Попробуй ещё раз."
        )
        return

    uid = message.from_user.id
    name = states[uid]["name"]

    encrypted = cipher.encrypt(
        password.encode()
    ).decode()

    with LOCK, connect() as con:
        con.execute("""
            INSERT INTO passwords
            (user_id, name, password, created)
            VALUES (?, ?, ?, ?)
        """, (
            uid,
            name,
            encrypted,
            datetime.now().isoformat()
        ))

    states.pop(uid, None)

    bot.send_message(
        message.chat.id,
        "✅ Пароль успешно сохранён!"
    )


@bot.callback_query_handler(
    func=lambda c: c.data == "list"
)
def list_passwords(call):
    uid = call.from_user.id

    with connect() as con:
        rows = con.execute("""
            SELECT id, name
            FROM passwords
            WHERE user_id = ?
            ORDER BY id DESC
        """, (uid,)).fetchall()

    bot.answer_callback_query(call.id)

    if not rows:
        bot.send_message(
            call.message.chat.id,
            "📂 Твоя библиотека пока пустая."
        )
        return

    kb = types.InlineKeyboardMarkup()

    for pid, name in rows:
        kb.add(types.InlineKeyboardButton(
            f"🔐 {name[:35]}",
            callback_data=f"show:{pid}"
        ))

    bot.send_message(
        call.message.chat.id,
        "📂 ТВОИ ЗАПИСИ:",
        reply_markup=kb
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("show:")
)
def show_password(call):
    uid = call.from_user.id
    pid = int(call.data.split(":")[1])

    with connect() as con:
        row = con.execute("""
            SELECT name, password
            FROM passwords
            WHERE id = ? AND user_id = ?
        """, (pid, uid)).fetchone()

    if not row:
        bot.answer_callback_query(
            call.id,
            "Запись не найдена!"
        )
        return

    name, encrypted = row

    password = cipher.decrypt(
        encrypted.encode()
    ).decode()

    kb = types.InlineKeyboardMarkup()

    kb.add(types.InlineKeyboardButton(
        "🗑 Удалить",
        callback_data=f"delete:{pid}"
    ))

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        f"🔐 <b>{html.escape(name)}</b>\n\n"
        f"<code>{html.escape(password)}</code>",
        parse_mode="HTML",
        reply_markup=kb
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("delete:")
)
def delete_password(call):
    uid = call.from_user.id
    pid = int(call.data.split(":")[1])

    with LOCK, connect() as con:
        cur = con.execute("""
            DELETE FROM passwords
            WHERE id = ? AND user_id = ?
        """, (pid, uid))

        deleted = cur.rowcount

    bot.answer_callback_query(
        call.id,
        "Запись удалена!" if deleted else "Запись не найдена!"
    )


@bot.message_handler(
    func=lambda m: states.get(m.from_user.id, {}).get("step")
    in ("name", "password")
)
def password_input(message):
    if message.chat.type != "private":
        return

    if message.content_type != "text":
        bot.reply_to(message, "Отправь текст.")
        return

    state = states.get(message.from_user.id)

    if not state:
        return

    if state["step"] == "name":
        save_name(message)
    else:
        save_password(message)


# =====================================
# АДМИН-ПАНЕЛЬ
# =====================================

def show_admin(chat_id):
    with connect() as con:
        users = con.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        generations = con.execute(
            "SELECT COALESCE(SUM(generations), 0) FROM stats"
        ).fetchone()[0]

        passwords = con.execute(
            "SELECT COUNT(*) FROM passwords"
        ).fetchone()[0]

    bot.send_message(
        chat_id,
        "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        f"👥 Пользователей: {users}\n"
        f"🎲 Генераций: {generations}\n"
        f"🔐 Сохранённых записей: {passwords}\n\n"
        "🔒 Чужие пароли недоступны.",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["admin"])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        return

    show_admin(message.chat.id)


@bot.message_handler(
    func=lambda m: m.text == "👑 Админ-панель"
)
def admin_button(message):
    if message.from_user.id != ADMIN_ID:
        return

    show_admin(message.chat.id)


# =====================================
# ИНСТРУКЦИЯ
# =====================================

@bot.message_handler(
    func=lambda m: m.text == "ℹ️ Инструкция"
)
def help_button(message):
    bot.send_message(
        message.chat.id,
        "📖 <b>ИНСТРУКЦИЯ</b>\n\n"
        "🎲 Генератор — создание ников.\n"
        "⚙️ Настройки — длина, стиль и количество.\n"
        "🔐 Мои пароли — личная библиотека.\n"
        "/start — главное меню.\n"
        "/admin — админ-панель.",
        parse_mode="HTML"
    )


# =====================================
# FLASK ДЛЯ RENDER
# =====================================

@app.route("/")
def home():
    return "BOT ONLINE", 200


# =====================================
# ЗАПУСК
# =====================================

def run_bot():
    bot.remove_webhook()

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=25
    )


if __name__ == "__main__":
    init_db()

    threading.Thread(
        target=run_bot,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=PORT,
        threaded=True
    )
