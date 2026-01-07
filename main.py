# main.py

import asyncio
import logging
import base64  # <-- Библиотека для кодирования/декодирования

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- ДЕКОДИРУЕМ СЕКРЕТНЫЕ ДАННЫЕ ИЗ BASE64 ---

# Здесь "спрятан" ваш НОВЫЙ токен
ENCODED_TOKEN = 'ODUyNjQxOTUzMTpBQUhlVndiSzJOWnBSN2VmUUFwNThwUlNFUzJ2czNrMU5NQQ=='
TOKEN = base64.b64decode(ENCODED_TOKEN).decode('utf-8')

# Здесь "спрятаны" ваши ID (остались без изменений)
ENCODED_ADMIN_IDS = 'OTU5OTg0MDMwLDY3Njk0NzU0MTcsMTAzNDE3OTg4MSw3OTU4MDY5NTgw'
ADMIN_IDS_STR = base64.b64decode(ENCODED_ADMIN_IDS).decode('utf-8')
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',')]

# --------------------------------------------------------

# Остальная часть кода остается без изменений

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

FAQ_TEXT = """
*Часто задаваемые вопросы (FAQ):*

*В: Какой график работы поддержки?*
*О:* Мы стараемся отвечать как можно скорее, 24/7.

*В: Как мне стать частью РП проекта?*
*О:* Следите за новостями в нашем основном канале.

*В: Могу ли я предложить свою идею?*
*О:* Конечно! Напишите администратору, и мы обсудим ваше предложение.

Если у вас остались вопросы, нажмите на кнопку «✍️ Написать поддержке».
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("❓ FAQ", callback_data='faq')],
        [InlineKeyboardButton("✍️ Написать поддержке", callback_data='support')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'Добро пожаловать в нашу поддержку!\n\n'
        'Здесь вы можете найти ответы на частые вопросы или задать свой.',
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == 'faq':
        await query.message.reply_text(FAQ_TEXT, parse_mode='Markdown')
    elif query.data == 'support':
        await query.message.reply_text('Напишите ваш вопрос, и я передам его администрации.')

async def forward_to_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message
    user = user_message.from_user
    if user.id not in ADMIN_IDS:
        forward_text = (
            f"Новое сообщение от пользователя {user.full_name} (@{user.username}, ID: {user.id}).\n"
            "Чтобы ответить, используйте функцию 'Ответить' (Reply) на это сообщение."
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=forward_text)
                await context.bot.forward_message(
                    chat_id=admin_id,
                    from_chat_id=user_message.chat_id,
                    message_id=user_message.message_id
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.reply_to_message and update.message.from_user.id in ADMIN_IDS:
        original_message = update.message.reply_to_message
        if original_message.forward_from:
            user_id = original_message.forward_from.id
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"Ответ от администрации:\n\n{update.message.text}"
                )
                await update.message.reply_text("✅ Ответ пользователю отправлен.")
            except Exception as e:
                await update.message.reply_text(f"❌ Не удалось отправить ответ: {e}")
        elif "Новое сообщение от пользователя" in original_message.text:
            try:
                user_id_line = [line for line in original_message.text.split('\n') if "ID:" in line][0]
                user_id = int(user_id_line.split("ID: ")[1].replace(")", ""))
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"Ответ от администрации:\n\n{update.message.text}"
                )
                await update.message.reply_text("✅ Ответ пользователю отправлен.")
            except (IndexError, ValueError):
                 await update.message.reply_text("❌ Не удалось извлечь ID пользователя. Пожалуйста, отвечайте на пересланное сообщение.")
            except Exception as e:
                await update.message.reply_text(f"❌ Не удалось отправить ответ: {e}")

def main() -> None:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.REPLY & filters.User(user_id=ADMIN_IDS), reply_to_user))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_admins))
    application.run_polling()

if __name__ == '__main__':
    main()
