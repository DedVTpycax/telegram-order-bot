import os
import logging
from telegram import Update, MessageEntity
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Чтобы не спамило getUpdates в логах
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Твой кастомный премиум-эмодзи для приветствия
START_EMOJI_ID = "5202151555276506786"

# (Опционально) кастомный эмодзи для строки "Пользователь: ..."
CUSTOM_EMOJI_ID = os.getenv("CUSTOM_EMOJI_ID")  # можно не задавать

# message_id (в чате админа) -> chat_id клиента
routes: dict[int, int] = {}


def build_custom_emoji(prefix: str, emoji_id: str, suffix: str) -> tuple[str, list[MessageEntity]]:
    """
    Вставляет кастомный эмодзи в текст через placeholder + entities.
    Возвращает (text, entities).
    """
    placeholder = "🙂"  # одиночный символ, на который навесим custom emoji
    text = f"{prefix}{placeholder}{suffix}"
    offset = text.index(placeholder)
    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=offset,
            length=1,
            custom_emoji_id=emoji_id,
        )
    ]
    return text, entities


def build_user_line(username: str) -> tuple[str, list[MessageEntity] | None]:
    """
    Строка админу: "Пользователь: <эмодзи> @username"
    Если CUSTOM_EMOJI_ID задан — используем кастомный, иначе обычный 👤.
    """
    if CUSTOM_EMOJI_ID:
        return build_custom_emoji("Пользователь: ", CUSTOM_EMOJI_ID, f" {username}")
    return f"Пользователь: 👤 {username}", None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ровно нужное приветствие:
    # <кастомный смайлик> Привет! Я Бот-Помощник, я помогу настроить идеальный диалог между тобой и командой! Напиши свой вопрос!
    greeting_suffix = (
        " Привет! Я Бот-Помощник, я помогу настроить идеальный диалог между тобой и командой! "
        "Напиши свой вопрос!"
    )
    text, ents = build_custom_emoji("", START_EMOJI_ID, greeting_suffix)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, entities=ents)


async def handle_user_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любое сообщение от клиента -> админу (username + пересылка контента)."""
    msg = update.message
    user = msg.from_user
    user_chat_id = update.effective_chat.id

    username = f"@{user.username}" if user.username else "без username"

    # 1) Админу: "Пользователь: @username"
    text, ents = build_user_line(username)
    info = await context.bot.send_message(chat_id=ADMIN_ID, text=text, entities=ents)
    routes[info.message_id] = user_chat_id

    # 2) Админу: само сообщение клиента (любой тип)
    fwd = await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=user_chat_id,
        message_id=msg.message_id,
    )
    routes[fwd.message_id] = user_chat_id


async def handle_admin_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любое сообщение от админа -> клиенту (если это reply на сообщение клиента/строку 'Пользователь: ...')."""
    msg = update.message
    if not msg.reply_to_message:
        return

    key = msg.reply_to_message.message_id
    user_chat_id = routes.get(key)
    if not user_chat_id:
        return

    # copy() переносит любые типы сообщений, отправителем для клиента будет бот (админ скрыт)
    await msg.copy(chat_id=user_chat_id)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error: %s", context.error)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # Клиенты: всё, кроме команд, и не админ
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.User(ADMIN_ID), handle_user_any)
    )

    # Админ: всё, кроме команд
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND & filters.User(ADMIN_ID), handle_admin_any)
    )

    app.add_error_handler(error_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
