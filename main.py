import os
import re
import logging
import asyncio
import requests
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ------------------------------------------------------------------------------
# 1. Logging Configuration
# ------------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# 2. Environment Variables & Credentials
# ------------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

if RENDER_URL.endswith("/"):
    RENDER_URL = RENDER_URL[:-1]

# ------------------------------------------------------------------------------
# 3. Telegram Bot Handlers
# ------------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"سلام {user.first_name} عزیز! 👋\n\n"
        "به ربات دانلود فیلم و سریال خوش آمدید.\n"
        "کافیه اسم فیلم، سریال یا لینک مستقیمی که می‌خواهی رو بفرستی!"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **راهنمای استفاده از ربات:**\n\n"
        "1️⃣ ارسال نام فیلم یا سریال برای جستجو\n"
        "2️⃣ ارسال لینک مستقیم فایل جهت دانلود مستقیم\n"
        "3️⃣ دریافت فایل‌ها با سرعت بالا"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("http://") or text.startswith("https://"):
        await update.message.reply_text("🔗 لینک دریافت شد! در حال پردازش دانلود...")
    else:
        await update.message.reply_text(f"🔍 در حال جستجوی فیلم/سریال: **{text}** ...", parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"گزینه انتخاب شده: {query.data}")

# ------------------------------------------------------------------------------
# 4. Initialize Telegram Application
# ------------------------------------------------------------------------------
bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
bot_app.add_handler(CallbackQueryHandler(button_callback))

# ------------------------------------------------------------------------------
# 5. Flask Webhook Server
# ------------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Movie Bot Webhook Server Alive!", 200

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, bot_app.bot)
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        loop.create_task(bot_app.process_update(update))
        return "OK", 200

# ------------------------------------------------------------------------------
# 6. Set Webhook & Start Flask
# ------------------------------------------------------------------------------
async def setup_bot():
    """راه‌اندازی اولیه اپلیکیشن و تنظیم وب‌هووک"""
    await bot_app.initialize()
    await bot_app.start()
    
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/telegram"
        await bot_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set successfully to: {webhook_url}")

if __name__ == "__main__":
    # 1. تنظیم Webhook
    asyncio.run(setup_bot())
    
    # 2. اجرای Flask Server روی پورت Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)