import os
import logging
from telegram import Update, MessageEntity
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Убрать спам getUpdates в логах
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Опционально: custom emoji id (Telegram custom emoji). Если не задан — используем обычные эмодзи.
CUSTOM_EMOJI_ID = os.getenv("CUSTOM_EMOJI_ID")  # пример: "5337327812345678901"

# message_id (в чате админа) -> chat_id клиента
routes: dict[int, int] = {}


def build_user_line(username: str) -> tuple[str, list[MessageEntity] | None]:
    """
    "Пользователь: <эмодзи> @username"
    Если задан CUSTOM_EMOJI_ID — вставляем custom emoji entity на плейсхолдер-символ.
    """
    if CUSTOM_EMOJI_ID:
        placeholder = "🙂"  # одиночный символ
        text = f"Пользователь: {placeholder} {username}"
        offset = text.index(placeholder)
        entities = [
            MessageEntity(
                type="custom_emoji",
                offset=offset,
                length=1,
                custom_emoji_id=CUSTOM_EMOJI_ID,
            )
        ]
        return text, entities

    return f"Пользователь: 👤 {username}", None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напиши сообщение (текст/файл/голос/видео), и я передам его нашей команде."
    )


async def entities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Получить custom_emoji_id:
    1) отправь боту сообщение с кастомным эмодзи
    2) ответь командой /entities на это сообщение (reply)
       или просто вызови /entities и затем отправь сообщение (не всегда сохраняет entities у команды)
    """
    msg = update.message

    # Если /entities отправили reply на сообщение — берём entities из того сообщения
    target = msg.reply_to_message if msg and msg.reply_to_message else msg

    if not target or not target.entities:
        await msg.reply_text("Сделай reply /entities на сообщение с кастомным эмодзи.")
        return

    lines = []
    for e in target.entities:
        cid = getattr(e, "custom_emoji_id", None)
        if cid:
            lines.append(f"custom_emoji_id={cid} (offset={e.offset}, length={e.length})")
    await msg.reply_text("\n".join(lines) if lines else "В сообщении нет custom_emoji entities.")


async def handle_user_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = msg.from_user
    user_chat_id = update.effective_chat.id

    username = f"@{user.username}" if user.username else "без username"

    # 1) Строка админу: только "Пользователь: @username"
    text, ents = build_user_line(username)
    info = await context.bot.send_message(chat_id=ADMIN_ID, text=text, entities=ents)
    routes[info.message_id] = user_chat_id

    # 2) Пересылка сообщения клиента (любые типы)
    fwd = await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=user_chat_id,
        message_id=msg.message_id,
    )
    routes[fwd.message_id] = user_chat_id

    # Подтверждения "отправлено" убраны


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
    app.add_handler(CommandHandler("entities", entities))

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.User(ADMIN_ID), handle_user_any))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & filters.User(ADMIN_ID), handle_admin_any))

    app.add_error_handler(error_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
