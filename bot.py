
import telebot
import sqlite3
import random
import string
import os
from flask import Flask, request
from cryptography.fernet import Fernet
from telebot import types

# ========== НАСТРОЙКИ ==========

TOKEN = "9060513665:AAFIsr_Ef0R1AY55f4I3O5s0tT110TGztOE"
ADMIN_ID = 123456789  # ТВОЙ TELEGRAM ID

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Ключ создаётся автоматически и сохраняется
if not os.path.exists("secret.key"):
    with open("secret.key", "wb") as f:
        f.write(Fernet.generate_key())

with open("secret.key", "rb") as f:
    cipher = Fernet(f.read())

db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY,
 username TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS passwords (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER,
 name TEXT,
 password TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS stats (
 user_id INTEGER PRIMARY KEY,
 generations INTEGER DEFAULT 0
)
""")

db.commit()

settings = {}

# ========== МЕНЮ ==========

def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎲 Генератор ников")
    kb.row("🔐 Мои пароли", "⚙️ Настройки")
    kb.row("👑 Админ-панель", "ℹ️ Помощь")
    return kb


def register(user):
    cur.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?)",
        (user.id, user.username or "unknown")
    )
    cur.execute(
        "INSERT OR IGNORE INTO stats VALUES (?, 0)",
        (user.id,)
    )
    db.commit()


# ========== START ==========

@bot.message_handler(commands=["start"])
def start(message):
    register(message.from_user)
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать!\n\n"
        "🎲 Генератор никнеймов\n"
        "🔐 Личная библиотека паролей\n"
        "⚙️ Настройки\n"
        "👑 Админ-панель",
        reply_markup=menu()
    )


# ========== ГЕНЕРАТОР ==========

@bot.message_handler(func=lambda m: m.text == "🎲 Генератор ников")
def generator(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "🎲 Сгенерировать",
        callback_data="generate"
    ))
    kb.add(types.InlineKeyboardButton(
        "⚙️ Настройки",
        callback_data="settings"
    ))
    bot.send_message(
        message.chat.id,
        "🎲 Генератор никнеймов",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data == "generate")
def generate(call):
    s = settings.get(call.from_user.id, {})
    length = s.get("length", 12)
    count = s.get("count", 5)
    mode = s.get("mode", "mixed")

    chars = string.ascii_lowercase

    if mode in ["mixed", "numbers", "symbols"]:
        chars += string.digits
    if mode == "mixed":
        chars += string.ascii_uppercase
    if mode == "symbols":
        chars += "_-."

    result = []

    for i in range(count):
        nick = "".join(random.choice(chars) for _ in range(length))
        result.append(f"`{nick}`")

    cur.execute(
        "UPDATE stats SET generations=generations+? WHERE user_id=?",
        (count, call.from_user.id)
    )
    db.commit()

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "🎲 Твои никнеймы:\n\n" + "\n".join(result),
        parse_mode="Markdown"
    )


# ========== НАСТРОЙКИ ==========

@bot.callback_query_handler(func=lambda c: c.data == "settings")
def settings_menu(call):
    kb = types.InlineKeyboardMarkup(row_width=2)

    for n in [6, 8, 10, 12, 16, 20, 24, 32]:
        kb.add(types.InlineKeyboardButton(
            f"{n} символов",
            callback_data=f"len_{n}"
        ))

    for mode, name in [
        ("letters", "Буквы"),
        ("numbers", "Цифры"),
        ("mixed", "Смешанный"),
        ("symbols", "Символы")
    ]:
        kb.add(types.InlineKeyboardButton(
            name,
            callback_data=f"mode_{mode}"
        ))

    for n in [1, 5, 10, 20, 50]:
        kb.add(types.InlineKeyboardButton(
            f"{n} ников",
            callback_data=f"count_{n}"
        ))

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "⚙️ Настройки генератора:",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("len_"))
def set_length(call):
    settings.setdefault(call.from_user.id, {})["length"] = int(
        call.data.split("_")[1]
    )
    bot.answer_callback_query(call.id, "Длина изменена!")


@bot.callback_query_handler(func=lambda c: c.data.startswith("mode_"))
def set_mode(call):
    settings.setdefault(call.from_user.id, {})["mode"] = call.data[5:]
    bot.answer_callback_query(call.id, "Режим изменён!")


@bot.callback_query_handler(func=lambda c: c.data.startswith("count_"))
def set_count(call):
    settings.setdefault(call.from_user.id, {})["count"] = int(
        call.data.split("_")[1]
    )
    bot.answer_callback_query(call.id, "Количество изменено!")


# ========== БИБЛИОТЕКА ПАРОЛЕЙ ==========

@bot.message_handler(func=lambda m: m.text == "🔐 Мои пароли")
def vault(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "➕ Добавить пароль", callback_data="add"
    ))
    kb.add(types.InlineKeyboardButton(
        "📂 Мои записи", callback_data="list"
    ))
    bot.send_message(
        message.chat.id,
        "🔐 Твоя библиотека:",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data == "add")
def add(call):
    if call.message.chat.type != "private":
        bot.answer_callback_query(call.id, "Только личный чат!")
        return

    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        "Введи название записи:"
    )
    bot.register_next_step_handler(msg, add_name)


def add_name(message):
    if message.chat.type != "private":
        return
    name = (message.text or "").strip()[:80]
    if not name:
        bot.send_message(message.chat.id, "Название не может быть пустым.")
        return
    msg = bot.send_message(message.chat.id, "Теперь введи пароль:")
    bot.register_next_step_handler(msg, add_password, name)


def add_password(message, name):
    if message.chat.type != "private":
        return

    password = message.text or ""
    if not password or len(password) > 500:
        bot.send_message(message.chat.id, "Некорректный пароль.")
        return

    encrypted = cipher.encrypt(password.encode()).decode()

    cur.execute(
        "INSERT INTO passwords (user_id,name,password) VALUES (?,?,?)",
        (message.from_user.id, name, encrypted)
    )
    db.commit()

    bot.send_message(message.chat.id, "✅ Пароль сохранён в зашифрованном виде!")


@bot.callback_query_handler(func=lambda c: c.data == "list")
def list_passwords(call):
    cur.execute(
        "SELECT id,name FROM passwords WHERE user_id=?",
        (call.from_user.id,)
    )
    rows = cur.fetchall()

    if not rows:
        bot.answer_callback_query(call.id, "Библиотека пустая!")
        return

    kb = types.InlineKeyboardMarkup()

    for pid, name in rows:
        kb.add(types.InlineKeyboardButton(
            f"🔐 {name}",
            callback_data=f"show_{pid}"
        ))

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "Твои записи:",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("show_"))
def show_password(call):
    pid = int(call.data.split("_")[1])

    cur.execute(
        "SELECT name,password FROM passwords WHERE id=? AND user_id=?",
        (pid, call.from_user.id)
    )
    row = cur.fetchone()

    if not row:
        bot.answer_callback_query(call.id, "Запись не найдена!")
        return

    name, encrypted = row
    password = cipher.decrypt(encrypted.encode()).decode()

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "🗑 Удалить",
        callback_data=f"del_{pid}"
    ))

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"🔐 {name}\n\nПароль: `{password}`",
        parse_mode="Markdown",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete_password(call):
    pid = int(call.data.split("_")[1])

    cur.execute(
        "DELETE FROM passwords WHERE id=? AND user_id=?",
        (pid, call.from_user.id)
    )
    db.commit()

    bot.answer_callback_query(call.id, "Запись удалена!")
    bot.send_message(call.message.chat.id, "🗑 Пароль удалён.")


# ========== АДМИНКА ==========

@bot.message_handler(func=lambda m: m.text == "👑 Админ-панель")
def admin(message):
    if message.from_user.id != ADMIN_ID:
        return

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("SELECT SUM(generations) FROM stats")
    generations = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM passwords")
    passwords = cur.fetchone()[0]

    bot.send_message(
        message.chat.id,
        "👑 АДМИН-ПАНЕЛЬ\n\n"
        f"👥 Пользователей: {users}\n"
        f"🎲 Генераций: {generations}\n"
        f"🔐 Записей: {passwords}"
    )


# ========== ПОМОЩЬ ==========

@bot.message_handler(func=lambda m: m.text == "⚙️ Настройки")
def settings_button(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "Открыть настройки",
        callback_data="settings"
    ))
    bot.send_message(message.chat.id, "Настройки:", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def help_button(message):
    bot.send_message(
        message.chat.id,
        "ℹ️ Помощь\n\n"
        "🎲 Генератор — создаёт никнеймы.\n"
        "🔐 Библиотека — хранит твои записи.\n"
        "⚙️ Настройки — длина, стиль и количество.\n"
        "/start — перезапустить меню."
    )


# ========== WEBHOOK / FLASK ==========

@app.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        return "Forbidden", 403

    update = telebot.types.Update.de_json(
        request.get_data().decode("utf-8")
    )
    bot.process_new_updates([update])
    return "OK", 200


WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change_this_secret")


if __name__ == "__main__":
    bot.infinity_polling(skip_pending=True)
