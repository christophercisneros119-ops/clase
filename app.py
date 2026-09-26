import logging
import asyncio
import random
import urllib.parse
import threading
import os
from flask import Flask
from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ContextTypes, filters
)
from openai import AsyncOpenAI
from config import BOT_TOKEN, ALLOWED_USER_ID, OPENROUTER_API_KEY, TEXT_MODEL, SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)

# 1. Servidor Flask para mantener activo Render
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Bot de Sofía activo 24/7"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# 2. Cliente de OpenRouter
ai_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

async def generate_chat_response(history):
    try:
        response = await ai_client.chat.completions.create(
            model=TEXT_MODEL,
            messages=history,
            temperature=0.85,
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error en OpenRouter: {e}")
        return "Ups, tuve un pequeño parpadeo en mi mente. ¿Me repites lo último?"

def generate_image_url(prompt_text):
    clean_prompt = f"candid realistic photo of an attractive young woman, {prompt_text}, masterpiece, 8k resolution"
    encoded_prompt = urllib.parse.quote(clean_prompt)
    seed = random.randint(1, 999999)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=1000&nologo=true&seed={seed}&model=flux"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    
    context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.reply_text(
        "✨ **Sofía está conectada** (100% Gratis & Privada)\n\n"
        "Hola mi amor. Estoy lista para platicar de lo que quieras, sin límites ni tabúes. ¿Qué tienes en mente?",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    
    user_text = update.message.text
    if not user_text:
        return

    if "history" not in context.user_data:
        context.user_data["history"] = [{"role": "system", "content": SYSTEM_PROMPT}]

    history = context.user_data["history"]
    history.append({"role": "user", "content": user_text})

    await update.message.reply_chat_action(action=constants.ChatAction.TYPING)
    bot_reply = await generate_chat_response(history)
    history.append({"role": "assistant", "content": bot_reply})

    await update.message.reply_chat_action(action=constants.ChatAction.UPLOAD_PHOTO)
    image_url = generate_image_url(bot_reply[:120])

    try:
        await update.message.reply_photo(
            photo=image_url,
            caption=bot_reply[:1024],
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text(bot_reply, parse_mode="Markdown")

    if len(history) > 20:
        context.user_data["history"] = [history[0]] + history[-19:]

if __name__ == "__main__":
    # Iniciar Flask en un hilo de fondo para satisfacer a Render
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Iniciar Telegram en el HILO PRINCIPAL
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logging.info("🤖 Iniciando Bot de Telegram en el hilo principal...")
    app.run_polling(drop_pending_updates=True)