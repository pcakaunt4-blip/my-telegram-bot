
import os
import json
import secrets
import string
import threading
from datetime import datetime, date
from flask import Flask
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============== НАСТРОЙКИ ==============

TOKEN = "ВСТАВЬ_НОВЫЙ_ТОКЕН"
ADMIN_ID = 7623353420

bot = TeleBot(TOKEN)
app = Flask(__name__)

DB_FILE = "passwords.json"
USERS_FILE = "users.json"
LOG_FILE = "bot_logs.json"

last_generated = {}
pending = {}

# ============== БАЗА ДАННЫХ ==============

def load_json(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(filename, data):
    temp = filename + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(temp, filename)

def log_action(uid, action):
    logs = load_json(LOG_FILE)
    uid = str(uid)
    logs.setdefault(uid, [])
    logs[uid].append({
        "action": action,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    logs[uid] = logs[uid][-100:]
    save_json(LOG_FILE, logs)

def register_user(user):
    users = load_json(USERS_FILE)
    uid = str(user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if uid not in users:
        users[uid] = {
            "username": user.username or "NoUsername",
            "first_name": user.first_name or "User",
            "joined": now
        }

    users[uid]["last_seen"] = now
    save_json(USERS_FILE, users)

# ============== ГЕНЕРАТОРЫ ==============

def generate_password(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_+="

    chars = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*()-_+=")
    ]

    chars += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(chars)

    return "".join(chars)

WORDS = [
    "Shadow", "Dark", "Night", "Ghost", "Wolf",
    "Dragon", "Fire", "Storm", "Blaze", "Frost",
    "King", "Queen", "Legend", "Cyber", "Phantom",
    "Venom", "Hunter", "Ninja", "Raven", "Angel",
    "Toxic", "Zero", "Pixel", "Lucky", "Silent"
]

def generate_nick():
    formats = [
        lambda: secrets.choice(WORDS) + str(secrets.randbelow(9999)),
        lambda: secrets.choice(WORDS) + "_" + secrets.choice(WORDS),
        lambda: "xX" + secrets.choice(WORDS) + "Xx",
        lambda: secrets.choice(WORDS) + str(secrets.randbelow(999)),
        lambda: "_" + secrets.choice(WORDS) + "_"
    ]

    return secrets.choice(formats)()

def check_strength(password):
    score = 0
    tips = []

    if len(password) >= 12:
        score += 2
    elif len(password) >= 8:
        score += 1
    else:
        tips.append("❌ Минимум 8 символов")

    if any(c.islower() for c in password):
        score += 1
    else:
        tips.append("❌ Добавь строчные буквы")

    if any(c.isupper() for c in password):
        score += 1
    else:
        tips.append("❌ Добавь заглавные буквы")

    if any(c.isdigit() for c in password):
        score += 1
    else:
        tips.append("❌ Добавь цифры")

    if any(c in string.punctuation for c in password):
        score += 1
    else:
        tips.append("❌ Добавь спецсимволы")

    if score >= 5:
        level = "🟢 ОЧЕНЬ НАДЁЖНЫЙ"
    elif score >= 3:
        level = "🟡 СРЕДНИЙ"
    else:
        level = "🔴 СЛАБЫЙ"

    return level, tips

# ============== КЛАВИАТУРЫ ==============

def main_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton("🔐 Пароли", callback_data="passwords"),
        InlineKeyboardButton("🎮 Ники", callback_data="nicks")
    )

    kb.add(
        InlineKeyboardButton("📚 Библиотека", callback_data="library"),
        InlineKeyboardButton("🛡 Проверка", callback_data="check")
    )

    return kb

def password_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)

    for length in [8, 12, 16, 20, 32, 64]:
        kb.add(
            InlineKeyboardButton(
                f"🔐 {length} символов",
                callback_data=f"gen_{length}"
            )
        )

    kb.add(
        InlineKeyboardButton("⬅️ Назад", callback_data="home")
    )

    return kb

def admin_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")
    )

    kb.add(
        InlineKeyboardButton("📈 Активность", callback_data="admin_activity"),
        InlineKeyboardButton("⬅️ Назад", callback_data="home")
    )

    return kb

# ============== СТАРТ ==============

@bot.message_handler(commands=["start"])
def start(message):
    register_user(message.from_user)
    log_action(message.from_user.id, "Start")

    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать!\n\n"
        "🔐 Генератор паролей\n"
        "🎮 Генератор ников\n"
        "📚 Личная библиотека\n"
        "🛡 Проверка паролей\n\n"
        "Выбери действие:",
        reply_markup=main_keyboard()
    )

# ============== КНОПКИ ==============

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = str(call.from_user.id)
    chat = call.message.chat.id
    data = call.data

    register_user(call.from_user)
    bot.answer_callback_query(call.id)

    if data == "home":
        pending.pop(uid, None)
        bot.send_message(
            chat, "🏠 Главное меню",
            reply_markup=main_keyboard()
        )

    elif data == "passwords":
        bot.send_message(
            chat,
            "Выбери длину пароля:",
            reply_markup=password_keyboard()
        )

    elif data.startswith("gen_"):
        try:
            length = int(data.split("_")[1])
        except ValueError:
            return

        if length not in [8, 12, 16, 20, 32, 64]:
            return

        password = generate_password(length)
        last_generated[uid] = ("Пароль", password)

        log_action(uid, "Password generated")

        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("💾 Сохранить", callback_data="save")
        )
        kb.add(
            InlineKeyboardButton("⬅️ Меню", callback_data="home")
        )

        bot.send_message(
            chat,
            f"🔐 Твой пароль:\n\n<code>{password}</code>",
            parse_mode="HTML",
            reply_markup=kb
        )

    elif data == "nicks":
        nick = generate_nick()
        last_generated[uid] = ("Ник", nick)

        log_action(uid, "Nickname generated")

        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("🔄 Ещё ник", callback_data="nicks"),
            InlineKeyboardButton("💾 Сохранить", callback_data="save")
        )
        kb.add(
            InlineKeyboardButton("⬅️ Меню", callback_data="home")
        )

        bot.send_message(
            chat,
            f"🎮 Твой ник:\n\n<code>{nick}</code>",
            parse_mode="HTML",
            reply_markup=kb
        )

    elif data == "save":
        if uid not in last_generated:
            return bot.send_message(chat, "❌ Сначала создай пароль или ник.")

        pending[uid] = {"action": "save"}
        bot.send_message(chat, "✏️ Напиши название записи:")

    elif data == "library":
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("📋 Посмотреть", callback_data="lib_view")
        )
        kb.add(
            InlineKeyboardButton("🗑 Удалить", callback_data="lib_delete")
        )
        kb.add(
            InlineKeyboardButton("⬅️ Назад", callback_data="home")
        )

        bot.send_message(
            chat, "📚 Твоя личная библиотека:",
            reply_markup=kb
        )

    elif data == "lib_view":
        db = load_json(DB_FILE)
        records = db.get(uid, {})

        if not records:
            return bot.send_message(chat, "📭 Библиотека пуста.")

        for name, item in records.items():
            bot.send_message(
                chat,
                f"📌 <b>{name}</b>\n"
                f"Тип: {item.get('type', 'Пароль')}\n"
                f"<code>{item.get('value', '')}</code>",
                parse_mode="HTML"
            )

    elif data == "lib_delete":
        db = load_json(DB_FILE)
        records = db.get(uid, {})

        if not records:
            return bot.send_message(chat, "📭 Библиотека пуста.")

        kb = InlineKeyboardMarkup(row_width=1)

        for index, name in enumerate(records):
            kb.add(
                InlineKeyboardButton(
                    f"🗑 {name[:35]}",
                    callback_data=f"del_{index}"
                )
            )

        pending[uid] = {
            "action": "delete",
            "names": list(records.keys())
        }

        bot.send_message(
            chat, "Выбери запись для удаления:",
            reply_markup=kb
        )

    elif data.startswith("del_"):
        state = pending.get(uid, {})

        if state.get("action") != "delete":
            return

        try:
            index = int(data[4:])
            name = state["names"][index]
        except (ValueError, IndexError, KeyError):
            return bot.send_message(chat, "❌ Запись не найдена.")

        db = load_json(DB_FILE)
        records = db.get(uid, {})

        if name in records:
            del records[name]
            save_json(DB_FILE, db)
            log_action(uid, "Library entry deleted")

        pending.pop(uid, None)
        bot.send_message(chat, "✅ Запись удалена.")

    elif data == "check":
        pending[uid] = {"action": "check"}
        bot.send_message(chat, "🛡 Отправь пароль для проверки.")

    elif data == "admin_stats":
        if call.from_user.id != ADMIN_ID:
            return

        users = load_json(USERS_FILE)
        db = load_json(DB_FILE)
        logs = load_json(LOG_FILE)

        records = sum(len(v) for v in db.values())
        actions = sum(len(v) for v in logs.values())

        today = date.today().isoformat()
        today_users = sum(
            1 for u in users.values()
            if u.get("joined", "").startswith(today)
        )

        bot.send_message(
            chat,
            "📊 <b>СТАТИСТИКА</b>\n\n"
            f"👥 Всего пользователей: {len(users)}\n"
            f"🆕 Регистраций сегодня: {today_users}\n"
            f"📚 Записей в библиотеках: {records}\n"
            f"⚡ Всего действий: {actions}",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )

    elif data == "admin_users":
        if call.from_user.id != ADMIN_ID:
            return

        users = load_json(USERS_FILE)

        bot.send_message(
            chat,
            f"👥 Всего пользователей: {len(users)}"
        )

        for user_id, info in list(users.items())[:50]:
            bot.send_message(
                chat,
                f"👤 {info.get('first_name', 'User')}\n"
                f"ID: <code>{user_id}</code>\n"
                f"Username: @{info.get('username', 'NoUsername')}\n"
                f"Регистрация: {info.get('joined', '-')}",
                parse_mode="HTML"
            )

    elif data == "admin_activity":
        if call.from_user.id != ADMIN_ID:
            return

        logs = load_json(LOG_FILE)
        total = sum(len(v) for v in logs.values())

        bot.send_message(
            chat,
            f"📈 Всего действий: {total}\n"
            f"Активных пользователей с логами: {len(logs)}"
        )

# ============== СООБЩЕНИЯ ==============

@bot.message_handler(content_types=["text"])
def handle_text(message):
    uid = str(message.from_user.id)
    register_user(message.from_user)

    if message.text.startswith("/"):
        return

    state = pending.get(uid)

    if not state:
        return bot.send_message(
            message.chat.id,
            "Выбери действие в меню:",
            reply_markup=main_keyboard()
        )

    action = state.get("action")

    if action == "save":
        title = message.text.strip()

        if not title or len(title) > 50:
            return bot.send_message(
                message.chat.id,
                "❌ Название должно быть от 1 до 50 символов."
            )

        if uid not in last_generated:
            pending.pop(uid, None)
            return bot.send_message(message.chat.id, "❌ Создай новую запись.")

        db = load_json(DB_FILE)
        db.setdefault(uid, {})

        db[uid][title] = {
            "type": last_generated[uid][0],
            "value": last_generated[uid][1],
            "created": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        save_json(DB_FILE, db)
        pending.pop(uid, None)

        log_action(uid, "Library entry saved")

        bot.send_message(
            message.chat.id,
            "✅ Запись сохранена в твоей библиотеке!"
        )

    elif action == "check":
        level, tips = check_strength(message.text)
        result = level + "\n\n"

        result += (
            "\n".join(tips)
            if tips else "✅ Отличный набор символов!"
        )

        pending.pop(uid, None)
        log_action(uid, "Password checked")

        bot.send_message(message.chat.id, result)

# ============== АДМИН ==============

@bot.message_handler(commands=["admin"])
def admin(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "⛔ Нет доступа.")

    bot.send_message(
        message.chat.id,
        "👑 АДМИН-ПАНЕЛЬ\n\nВыбери раздел:",
        reply_markup=admin_keyboard()
    )

# ============== FLASK ==============

@app.route("/")
def home():
    return "Password Generator Bot is running!"

@app.route("/health")
def health():
    return {"status": "ok"}

# ============== ЗАПУСК ==============

def run_bot():
    print("🤖 Bot started!")
    bot.remove_webhook()
    bot.infinity_polling(
        timeout=60,
        long_polling_timeout=60,
        skip_pending=True
    )

if __name__ == "__main__":
    threading.Thread(
        target=run_bot,
        daemon=True
    ).start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
