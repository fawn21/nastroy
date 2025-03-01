import os
import openai
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fastapi import FastAPI, Request
from uvicorn import run
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8443))

openai.api_key = OPENAI_API_KEY

# Логирование ошибок
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Хранилище контекста пользователей
user_contexts = {}
MESSAGE_LIMIT = 5  # Ограничение на 5 сообщений в день

# Создаем FastAPI приложение
app = FastAPI()

# Создаем Telegram приложение
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("привет) я переведу твои эмоции и мысли в язык гормонов и помогу вернуть их в норму. что сейчас происходит?")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    text = update.message.text

    if user_id not in user_contexts:
        user_contexts[user_id] = {"messages": [], "count": 0}

    if user_contexts[user_id]["count"] >= MESSAGE_LIMIT:
        await update.message.reply_text("Вы исчерпали дневной лимит сообщений. Попробуйте завтра.")
        return

    user_contexts[user_id]["messages"].append({"role": "user", "content": text})
    user_contexts[user_id]["count"] += 1

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
    user_id = update.message.chat_id
    user_contexts[user_id] = {"messages": [], "count": 0}
    await update.message.reply_text("Контекст сброшен.")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("reset", reset))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

# Устанавливаем Webhook для Telegram
async def set_webhook():
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

@telegram_app.on_startup
async def on_startup():
    await set_webhook()

# Маршрут для Webhook
@app.post("/webhook")
async def handle_webhook(request: Request):
    update = await request.json()
    await telegram_app.update_queue.put(Update.de_json(update, telegram_app.bot))
    return {"status": "ok"}

# Запуск FastAPI сервера
if __name__ == "__main__":
    run(app, host="0.0.0.0", port=PORT)
