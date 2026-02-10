from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

TOKEN = "8548761205:AAEh5VcBl19H-imS8Qmmf0W2zJD11RTmJL4"
ADMIN_ID = 1387024303  # <-- ВСТАВЬ СВОЙ TELEGRAM ID

# Храним связь клиент <-> сообщение
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напиши сообщение, и я передам его нашей команде."
    )

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    username = f"@{user.username}" if user.username else "без username"
    user_id = user.id

    user_sessions[user_id] = update.message.chat_id

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            "📩 Новое сообщение от клиента\n\n"
            f"👤 Пользователь: {username}\n"
            f"🆔 ID: {user_id}\n\n"
            f"💬 Сообщение:\n{text}"
        )
    )

    await update.message.reply_text(
        "Сообщение отправлено. Ожидайте ответа."
    )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message is None:
        return

    text = update.message.text
    replied_text = update.message.reply_to_message.text

    for user_id in user_sessions:
        if str(user_id) in replied_text:
            await context.bot.send_message(
                chat_id=user_sessions[user_id],
                text=f"💬 Ответ от команды:\n\n{text}"
            )
            break

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.User(ADMIN_ID), handle_user_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), handle_admin_reply))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
