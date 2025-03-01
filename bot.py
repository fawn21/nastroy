import os
import logging
import openai
import requests
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

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

# 1. Создаём Telegram-приложение (Application) из python-telegram-bot
app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()

# Храним историю диалогов по user_id
user_contexts = {}

async def start_command(update: Update, context):
    await update.message.reply_text("Привет! Я чат-бот на базе GPT. Задавай мне вопросы.")

async def reset_command(update: Update, context):
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
        logging.error(f"Ошибка при обращении к OpenAI: {e}")
        await update.message.reply_text("Произошла ошибка при обработке запроса.")

# Регистрируем хендлеры команд и сообщений
app_telegram.add_handler(CommandHandler("start", start_command))
app_telegram.add_handler(CommandHandler("reset", reset_command))
app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# 2. Создаём FastAPI-приложение, которое будет принимать вебхуки
fastapi_app = FastAPI()

@fastapi_app.get("/")
def root():
    return {"status": "ok"}

@fastapi_app.post("/webhook")
async def telegram_webhook(request: Request):
    """Эндпоинт, на который Telegram будет слать обновления."""
    data = await request.json()
    update = Update.de_json(data, app_telegram.bot)
    # Обрабатываем обновление через telegram-приложение
    await app_telegram.process_update(update)
    return {"ok": True}

# 3. На событии старта FastAPI инициализируем и запускаем бота, потом ставим вебхук
@fastapi_app.on_event("startup")
async def startup_event():
    # Инициализируем и запускаем Telegram-приложение
    await app_telegram.initialize()
    await app_telegram.start()

    # Настраиваем вебхук без двойного слэша
    webhook_endpoint = WEBHOOK_URL.rstrip('/') + "/webhook"
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
        json={"url": webhook_endpoint}
    )
    logging.info(f"Webhook setup response: {resp.json()}")

# 4. Запуск Uvicorn сервера, чтобы FastAPI слушал на порту PORT
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:fastapi_app", host="0.0.0.0", port=PORT)
