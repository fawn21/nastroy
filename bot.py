import os
import logging
import openai
import requests
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
import asyncio

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", "8443"))

openai.api_key = OPENAI_API_KEY

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Инициализируем Telegram-приложение
app = Application.builder().token(TELEGRAM_TOKEN).build()

user_contexts = {}

async def start(update: Update, context):
    await update.message.reply_text("Привет! Я чат-бот на базе GPT. Задавай мне вопросы.")

async def reset(update: Update, context):
    user_id = update.message.from_user.id
    user_contexts[user_id] = {"messages": [], "count": 0}
    await update.message.reply_text("Контекст сброшен.")

async def handle_message(update: Update, context):
    user_id = update.message.from_user.id
    message = update.message.text

    if user_id not in user_contexts:
        user_contexts[user_id] = {"messages": [], "count": 0}

    user_contexts[user_id]["messages"].append({"role": "user", "content": message})
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

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# FastAPI-приложение для вебхука
fastapi_app = FastAPI()

@fastapi_app.get("/")
def read_root():
    return {"status": "ok"}

@fastapi_app.post("/webhook")
async def telegram_webhook(request: Request):
    json_data = await request.json()
    update = Update.de_json(json_data, app.bot)
    # Обрабатываем обновление сразу:
    await app.process_update(update)
    return {"ok": True}

# Функция установки вебхука
async def set_webhook():
    # Убираем возможный завершающий слэш, чтобы не было двойного слеша
    url = WEBHOOK_URL.rstrip('/') + "/webhook"
    data = {"url": url}
    response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json=data)
    print("Webhook response:", response.json())

# Основная функция
async def main():
    await set_webhook()
    # Инициализируем и запускаем Telegram-приложение (оно будет обрабатывать обновления)
    await app.initialize()
    await app.start()
    import uvicorn
    config = uvicorn.Config("bot:fastapi_app", host="0.0.0.0", port=PORT)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
