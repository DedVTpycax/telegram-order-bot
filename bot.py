import os
import logging
from telegram import Update, MessageEntity
from telegram.error import BadRequest
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Кастомные emoji id (то, что ты дал)
EMOJI_WAVE_ID = "5202151555276506786"      # вместо 👋
EMOJI_PUZZLE_ID = "5202042871129082406"    # вместо 🧩
EMOJI_BRICK_ID = "5201721092179264394"     # вместо 🧱
EMOJI_PALETTE_ID = "5202143098485899804"   # вместо 🎨

# (опционально) кастомный эмодзи для строки "Пользователь: ..."
CUSTOM_EMOJI_ID = os.getenv("CUSTOM_EMOJI_ID")

routes: dict[int, int] = {}


def utf16_len(s: str) -> int:
    """Длина строки в UTF-16 code units (то, что требует Telegram для offset/length)."""
    return len(s.encode("utf-16-le")) // 2


def build_custom_emoji_message(parts: list[tuple[str, str | None]]) -> tuple[str, list[MessageEntity]]:
    """
    parts: список кусков (text, custom_emoji_id или None)
    Если custom_emoji_id задан — вставляем placeholder (❤) и навешиваем на него custom_emoji entity.
    """
    placeholder = "❤"  # один символ, обычно 1 UTF-16 unit
    text_out = ""
    entities: list[MessageEntity] = []

    for chunk_text, emoji_id in parts:
        if emoji_id:
            # запоминаем текущий offset (в utf-16), вставляем placeholder
            offset = utf16_len(text_out)
            text_out += placeholder
            entities.append(
                MessageEntity(
                    type="custom_emoji",
                    offset=offset,
                    length=1,
                    custom_emoji_id=emoji_id,
                )
            )
        text_out += chunk_text

    return text_out, entities


async def safe_send(bot, chat_id: int, text: str, entities: list[MessageEntity] | None, fallback_text: str):
    """
    Пробуем отправить текст с entities.
    Если Telegram ругается на entities — отправляем fallback текст без кастомных emoji.
    """
    try:
        return await bot.send_message(chat_id=chat_id, text=text, entities=entities)
    except BadRequest as e:
        logger.warning("Send with entities failed: %s", e)
        return await bot.send_message(chat_id=chat_id, text=fallback_text)


def build_user_line(username: str) -> tuple[str, list[MessageEntity] | None]:
    if CUSTOM_EMOJI_ID:
        # "Пользователь: <custom> @username"
        text, ents = build_custom_emoji_message([
            ("Пользователь: ", None),
            (" ", CUSTOM_EMOJI_ID),
            (f"{username}", None),
        ])
        return text, ents
    return f"Пользователь: 👤 {username}", None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Текст приветствия (как вариант №2, который тебе понравился)
    # Вставляем кастомные emoji:
    # 👋 -> EMOJI_WAVE_ID
    # 🧩 -> EMOJI_PUZZLE_ID
    # 🧱 -> EMOJI_BRICK_ID
    # 🎨 -> EMOJI_PALETTE_ID

    parts = [
        (" ", EMOJI_WAVE_ID),
        (" Привет! Добро пожаловать в <b>ScaleTeam</b>!\n\n", None),
        ("Мы занимаемся:\n", None),

        ("• ", None),
        (" ", EMOJI_PUZZLE_ID),
        (" модами\n", None),

        ("• ", None),
        (" ", EMOJI_BRICK_ID),
        (" картами и постройками!\n", None),

        ("• ", None),
        (" ", EMOJI_PALETTE_ID),
        (" 3D-моделями и ассетами!\n\n", None),

        ("Напиши нам о своей идее! Мы обязательно ответим и сориентируем!", None),
    ]

    text, ents = build_custom_emoji_message(parts)

    # Фолбэк на обычные эмодзи (если у кого-то Telegram/клиент не примет entities)
    fallback = (
        "👋 Привет! Добро пожаловать в <b>ScaleTeam</b>!\n\n"
        "Мы занимаемся:\n"
        "• 🧩 модами на разные версии!\n"
        "• 🧱 картами и постройками!\n"
        "• 🎨 3D-моделями и ассетами!\n\n"
        "Напиши нам о своей идее! Мы обязательно ответим и сориентируем!"
    )

    await safe_send(
        bot=context.bot,
        chat_id=update.effective_chat.id,
        text=text,
        entities=ents,
        fallback_text=fallback,
    )


async def handle_user_any(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_chat_id = update.effective_chat.id
    user = msg.from_user

    username = f"@{user.username}" if user.username else "без username"

    # 1) админу строка "Пользователь: @username"
    text, ents = build_user_line(username)
    try:
        info = await context.bot.send_message(chat_id=ADMIN_ID, text=text, entities=ents)
    except BadRequest:
        info = await context.bot.send_message(chat_id=ADMIN_ID, text=f"Пользователь: {username}")
    routes[info.message_id] = user_chat_id

    # 2) админу пересылка контента клиента
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

