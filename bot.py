import os
import openai
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# Логирование ошибок
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Хранилище контекста пользователей
user_contexts = {}
MESSAGE_LIMIT = 5  # Ограничение на 5 сообщений в день

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение при запуске бота."""
    await update.message.reply_text("Привет! Я бот, который отвечает на вопросы о здоровье. Просто напиши свой вопрос.")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик сообщений."""
    user_id = update.message.chat_id
    text = update.message.text

    # Проверяем лимит сообщений
    if user_id not in user_contexts:
        user_contexts[user_id] = {"messages": [], "count": 0}

    if user_contexts[user_id]["count"] >= MESSAGE_LIMIT:
        await update.message.reply_text("Вы исчерпали дневной лимит сообщений. Попробуйте завтра.")
        return

    # Добавляем сообщение пользователя в контекст
    user_contexts[user_id]["messages"].append({"role": "user", "content": text})
    user_contexts[user_id]["count"] += 1

    # Отправляем запрос в OpenAI API
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=user_contexts[user_id]["messages"]
        )
        reply = response["choices"][0]["message"]["content"]
        user_contexts[user_id]["messages"].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
    except Exception as e:
        logging.error(f"Ошибка OpenAI: {e}")
        await update.message.reply_text("Произошла ошибка при обработке запроса.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс контекста диалога."""
    user_id = update.message.chat_id
    user_contexts[user_id] = {"messages": [], "count": 0}
    await update.message.reply_text("Контекст сброшен.")

def main():
    """Запуск бота."""
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
