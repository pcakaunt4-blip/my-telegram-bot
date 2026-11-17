
import os
import sqlite3
import string
import secrets
import threading

import telebot
from telebot import types
from flask import Flask


# ========== CONFIG ==========

TOKEN = "ВСТАВЬ_ТОКЕН"
ADMIN_ID = 123456789

PORT = int(os.environ.get("PORT", 10000))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DB = "database.db"
settings = {}
lock = threading.Lock()


# ========== DATABASE ==========

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY,
                generations INTEGER DEFAULT 0
            )
        """)


def register(user):
    with lock, sqlite3.connect(DB) as con:
        con.execute(
            "INSERT OR IGNORE INTO users VALUES (?, ?)",
            (user.id, user.username or "unknown")
        )

        con.execute(
            "INSERT OR IGNORE INTO stats VALUES (?, 0)",
            (user.id,)
        )


# ========== MENUS ==========

def main_menu():
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    kb.row("🎲 Генератор ников")
    kb.row("⚙️ Настройки", "ℹ️ Помощь")
    kb.row("👑 Админ-панель")

    return kb


def generator_menu():
    kb = types.InlineKeyboardMarkup()

    kb.add(types.InlineKeyboardButton(
        "🎲 Создать ники",
        callback_data="generate"
    ))

    kb.add(types.InlineKeyboardButton(
        "⚙️ Настройки",
        callback_data="settings"
    ))

    return kb


# ========== START ==========

@bot.message_handler(commands=["start"])
def start(message):
    if message.chat.type != "private":
        return

    register(message.from_user)

    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать!\n\n"
        "🎲 Генератор никнеймов\n"
        "⚙️ Настройки генерации\n"
        "👑 Админ-панель",
        reply_markup=main_menu()
    )


# ========== GENERATOR ==========

def make_nick(length, mode):
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
        "🎲 ГЕНЕРАТОР НИКОВ",
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

    result = [
        make_nick(length, mode)
        for _ in range(count)
    ]

    with lock, sqlite3.connect(DB) as con:
        con.execute(
            "UPDATE stats SET generations = generations + ? WHERE id = ?",
            (count, uid)
        )

    text = "🎲 ТВОИ НИКИ:\n\n"

    for i, nick in enumerate(result, 1):
        text += f"{i}. <code>{nick}</code>\n"

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=generator_menu()
    )


# ========== SETTINGS ==========

def show_settings(chat_id):
    kb = types.InlineKeyboardMarkup(row_width=2)

    for n in [6, 8, 10, 12, 16, 20, 24, 32]:
        kb.add(types.InlineKeyboardButton(
            f"📏 {n} символов",
            callback_data=f"length:{n}"
        ))

    modes = [
        ("letters", "🔤 Буквы"),
        ("numbers", "🔢 Цифры"),
        ("mixed", "🔠 Смешанный"),
        ("symbols", "✨ Символы")
    ]

    for mode, name in modes:
        kb.add(types.InlineKeyboardButton(
            name,
            callback_data=f"mode:{mode}"
        ))

    for n in [1, 5, 10, 20, 50]:
        kb.add(types.InlineKeyboardButton(
            f"Количество: {n}",
            callback_data=f"count:{n}"
        ))

    bot.send_message(
        chat_id,
        "⚙️ НАСТРОЙКИ ГЕНЕРАТОРА",
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
    func=lambda c: c.data.startswith("length:")
)
def set_length(call):
    value = int(call.data.split(":")[1])

    settings.setdefault(
        call.from_user.id, {}
    )["length"] = value

    bot.answer_callback_query(
        call.id,
        f"Длина: {value}"
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("mode:")
)
def set_mode(call):
    value = call.data.split(":")[1]

    settings.setdefault(
        call.from_user.id, {}
    )["mode"] = value

    bot.answer_callback_query(
        call.id,
        "Режим изменён!"
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith("count:")
)
def set_count(call):
    value = int(call.data.split(":")[1])

    settings.setdefault(
        call.from_user.id, {}
    )["count"] = value

    bot.answer_callback_query(
        call.id,
        f"Количество: {value}"
    )


# ========== ADMIN PANEL ==========

def show_admin(chat_id):
    with sqlite3.connect(DB) as con:
        users = con.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        generations = con.execute(
            "SELECT COALESCE(SUM(generations), 0) FROM stats"
        ).fetchone()[0]

    kb = types.InlineKeyboardMarkup()

    kb.add(types.InlineKeyboardButton(
        "🔄 Обновить статистику",
        callback_data="admin_refresh"
    ))

    bot.send_message(
        chat_id,
        "👑 АДМИН-ПАНЕЛЬ\n\n"
        f"👥 Пользователей: {users}\n"
        f"🎲 Всего генераций: {generations}",
        reply_markup=kb
    )


@bot.message_handler(
    func=lambda m: m.text == "👑 Админ-панель"
)
def admin_button(message):
    if message.from_user.id != ADMIN_ID:
        return

    show_admin(message.chat.id)


@bot.message_handler(commands=["admin"])
def admin_command(message):
    if message.from_user.id == ADMIN_ID:
        show_admin(message.chat.id)


@bot.callback_query_handler(
    func=lambda c: c.data == "admin_refresh"
)
def admin_refresh(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет доступа!")
        return

    bot.answer_callback_query(call.id, "Обновлено!")
    show_admin(call.message.chat.id)


# ========== HELP ==========

@bot.message_handler(
    func=lambda m: m.text == "ℹ️ Помощь"
)
def help_button(message):
    bot.send_message(
        message.chat.id,
        "📖 ИНСТРУКЦИЯ\n\n"
        "/start — главное меню\n"
        "/admin — админ-панель\n\n"
        "🎲 Генератор — создание ников\n"
        "⚙️ Настройки — длина, режим и количество"
    )


# ========== FLASK ==========

@app.route("/")
def home():
    return "BOT IS ONLINE", 200


# ========== RUN ==========

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
