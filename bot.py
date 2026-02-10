import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Ключ: message_id в чате админа (то, на что админ отвечает reply)
# Значение: chat_id клиента, куда слать ответ
routes: dict[int, int] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напиши сообщение (текст/файл/голSafe: voice/видео и т.д.), и я передам его нашей команде."
    )


async def handle_user_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любое сообщение от клиента -> админу."""
    msg = update.message
    user = msg.from_user
    user_chat_id = update.effective_chat.id

    username = f"@{user.username}" if user.username else "без username"
    user_id = user.id

    # 1) Сначала отправим админу карточку (чтобы он видел username/ID)
    info = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            "📩 Новый запрос\n\n"
            f"👤 Пользователь: {username}\n"
            f"🆔 ID: {user_id}\n\n"
            "↩️ Ответь РЕПЛАЕМ на пересланное ниже сообщение, и я отправлю ответ клиенту."
        ),
    )
    routes[info.message_id] = user_chat_id

    # 2) Потом перешлём само сообщение клиента (в любом формате)
    fwd = await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=user_chat_id,
        message_id=msg.message_id,
    )
    routes[fwd.message_id] = user_chat_id

    await msg.reply_text("Сообщение отправлено. Ожидайте ответа.")


async def handle_admin_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любое сообщение от админа -> клиенту (если это reply на маршрутизируемое сообщение)."""
    msg = update.message

    # Нужно, чтобы админ отвечал reply
    if not msg.reply_to_message:
        return

    key = msg.reply_to_message.message_id
    user_chat_id = routes.get(key)

    if not user_chat_id:
        # Админ ответил на сообщение, которое не в маршрутах (старое/не то)
        return

    # Копируем сообщение админа клиенту в исходном виде (все типы файлов/voice/etc)
    # copy() сохраняет контент, но отправителем будет бот (админ скрыт)
    await msg.copy(chat_id=user_chat_id)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error: %s", context.error)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # Клиенты: всё, кроме команд, и не админ
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND & ~filters.User(ADMIN_ID),
            handle_user_any,
        )
    )

    # Админ: всё, кроме команд
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND & filters.User(ADMIN_ID),
            handle_admin_any,
        )
    )

    app.add_error_handler(error_handler)

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
