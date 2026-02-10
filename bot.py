import os
import logging
from telegram import Update, MessageEntity
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# (Опционально) сюда можно вписать custom_emoji_id, если хочешь использовать Telegram Custom Emoji.
# Если пусто/None — будут использоваться обычные эмодзи.
CUSTOM_EMOJI_ID = os.getenv("CUSTOM_EMOJI_ID")  # например "5337327812345678901"

# Ключ: message_id в чате админа (то, на что админ отвечает reply)
# Значение: chat_id клиента, куда слать ответ
routes: dict[int, int] = {}


def build_user_line(username: str) -> tuple[str, list[MessageEntity] | None]:
    """
    Возвращает (text, entities) для строки "Пользователь: <эмодзи> @username"
    Если задан CUSTOM_EMOJI_ID — вставляем кастомный эмодзи через entity.
    Иначе используем обычный эмодзи 👤.
    """
    if CUSTOM_EMOJI_ID:
        # Вставляем плейсхолдер-символ (один символ), на него навешиваем custom_emoji entity.
        # Важно: offset считается по строке.
        placeholder = "🙂"  # любой одиночный символ
        text = f"Пользователь: {placeholder} {username}"
        # offset: длина "Пользователь: " = 12 (включая пробел после двоеточия) — но лучше считать программно
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

    # Обычный эмодзи
    return f"Пользователь: 👤 {username}", None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋\nНапиши сообщение (текст/файл/голос/видео), и я передам его нашей команде."
    )


async def entities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда для получения custom_emoji_id.
    Использование:
      1) /entities
      2) Затем отправь боту сообщение, где есть нужный кастомный эмодзи
    Бот ответит списком entities, где будет custom_emoji_id.
    """
    msg = update.message
    if not msg or not msg.entities:
        await msg.reply_text(
            "Пришли сообщение с кастомным эмодзи (из набора Telegram), "
            "и я покажу его custom_emoji_id.\n"
            "Важно: entities должны быть в сообщении."
        )
        return

    lines = []
    for e in msg.entities:
        cid = getattr(e, "custom_emoji_id", None)
        lines.append(
            f"type={e.type}, offset={e.offset}, length={e.length}, custom_emoji_id={cid}"
        )
    await msg.reply_text("\n".join(lines))


async def handle_user_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любое сообщение от клиента -> админу (username + пересылка контента)."""
    msg = update.message
    user = msg.from_user
    user_chat_id = update.effective_chat.id

    username = f"@{user.username}" if user.username else "без username"

    # 1) Отправляем админу строку "Пользователь: ...", с кастомным эмодзи (если задан)
    text, ents = build_user_line(username)
    info = await context.bot.send_message(chat_id=ADMIN_ID, text=text, entities=ents)
    routes[info.message_id] = user_chat_id

    # 2) Пересылаем само сообщение клиента (любой тип: файлы/voice/video/etc)
    fwd = await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=user_chat_id,
        message_id=msg.message_id,
    )
    routes[fwd.message_id] = user_chat_id

    # Подтверждение пользователю убрано


async def handle_admin_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любое сообщение от админа -> клиенту (если это reply на сообщение клиента/строку 'Пользователь: ...')."""
    msg = update.message
    if not msg.reply_to_message:
        return

    key = msg.reply_to_message.message_id
    user_chat_id = routes.get(key)
    if not user_chat_id:
        return

    # copy() переносит любой тип контента, отправитель для клиента = бот (админ скрыт)
    await msg.copy(chat_id=user_chat_id)

    # Подтверждение админу убрано


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled error: %s", context.error)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("entities", entities))

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
