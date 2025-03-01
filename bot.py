import os
import openai
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import Defaults
from fastapi import FastAPI, Request
from uvicorn import Config, Server
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Добавь этот URL в переменные окружения Render

openai.api_key = OPENAI_API_KEY

# Логирование ошибок
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Хранилище контекста пользователей
user_contexts = {}
MESSAGE_LIMIT = 5  # Ограничение на 5 сообщений в день

# Создаём FastAPI приложение
app = FastAPI()

# Создаём бота с токеном и дефолтными параметрами
application = Application.builder().token(TELEGRAM_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение при запуске бота."""
    await update.message.reply_text("привет) я переведу твои эмоции и мысли в язык гормонов и помогу вернуть их в норму. что сейчас происходит?")

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

# Webhook обработчик для входящих запросов
@app.post(f"/{TELEGRAM_TOKEN}")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)

def main():
    """Настройка Webhook и запуск сервера."""
    # Устанавливаем Webhook
    application.bot.set_webhook(url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}")
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    # Запуск FastAPI сервера
    server = Server(Config(app, host="0.0.0.0", port=8000))
    server.run()

if __name__ == "__main__":
    main()
