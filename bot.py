import os
import logging
from telegram import Update, MessageEntity
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Твой кастомный премиум-эмодзи
START_EMOJI_ID = "5202151555276506786"

# (Опционально) кастомный эмодзи для строки "Пользователь: ..."
CUSTOM_EMOJI_ID = os.getenv("CUSTOM_EMOJI_ID")

routes: dict[int, int] = {}


def custom_emoji_prefix(emoji_id: str, text_after: str) -> tuple[str, list[MessageEntity]]:
    """
    Самый надёжный формат: placeholder в начале строки.
    Тогда offset=0 и не бывает рассинхрона.
    """
    placeholder = "X"  # 1 UTF-16 unit
    text = f"{placeholder}{text_after}"
    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=1,
            custom_emoji_id=emoji_id,
        )
    ]
    return text, entities


def build_user_line(username: str) -> tuple[str, list[MessageEntity] | None]:
    if CUSTOM_EMOJI_ID:
        # "X Пользователь: @username" (X станет кастомным эмодзи)
        text, ents = custom_emoji_prefix(CUSTOM_EMOJI_ID, f" Пользователь: {username}")
        return text, ents
    return f"Пользователь: 👤 {username}", None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    greeting = (
        " Привет! Я Бот-Помощник, я помогу настроить идеальный диалог между тобой и командой! "
        "Напиши свой вопрос!"
    )
    text, ents = custom_emoji_prefix(START_EMOJI_ID, greeting)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, entities=ents)


async def handle_user_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = msg.from_user
    user_chat_id = update.effective_chat.id

    username = f"@{user.username}" if user.username else "без username"

    text, ents = build_user_line(username)
    info = await context.bot.send_message(chat_id=ADMIN_ID, text=text, entities=ents)
    routes[info.message_id] = user_chat_id

    fwd = await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=user_chat_id,
        message_id=msg.message_id,
    )
    routes[fwd.message_id] = user_chat_id


async def handle_admin_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message:
        return

    key = msg.reply_to_message.message_id
    user_chat_id = routes.get(key)
    if not user_chat_id:
        return

    await msg.copy(chat_id=user_chat_id)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error: %s", context.error)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.User(ADMIN_ID), handle_user_any))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & filters.User(ADMIN_ID), handle_admin_any))

    app.add_error_handler(error_handler)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
