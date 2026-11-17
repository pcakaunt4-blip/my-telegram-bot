bot.send_message(
        message.chat.id,
        "👑 <b>АДМІН-ПАНЕЛЬ</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )


# ================== FLASK ==================

@app.route("/")
def index():
    return "SECUREBOX BOT IS RUNNING"


@app.route("/health")
def health():
    return {"status": "ok"}


# ================== RUN ==================

def run_bot():
    while True:
        try:
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=30,
                skip_pending=True
            )
        except Exception as e:
            print("Bot polling error:", e)
            time.sleep(5)


if name == "main":
    threading.Thread(target=run_bot, daemon=True).start()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        use_reloader=False
    )
