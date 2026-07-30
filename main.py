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
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app-name.onrender.com")

if RENDER_URL.endswith("/"):
    RENDER_URL = RENDER_URL[:-1]

# ------------------------------------------------------------------------------
# 3. Telegram Bot Handlers
# ------------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور start - خوش‌آمدگویی به کاربر"""
    user = update.effective_user
    welcome_text = (
        f"سلام {user.first_name} عزیز! 👋\n\n"
        "به ربات دانلود فیلم و سریال خوش آمدید.\n"
        "کافیه اسم فیلم، سریال یا لینک مستقیمی که می‌خواهی رو بفرستی!"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور help - راهنمای کاربر"""
    help_text = (
        "📖 **راهنمای استفاده از ربات:**\n\n"
        "1️⃣ ارسال نام فیلم یا سریال برای جستجو\n"
        "2️⃣ ارسال لینک مستقیم فایل جهت دانلود مستقیم\n"
        "3️⃣ دریافت فایل‌ها با سرعت بالا"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام‌های متنی و لینک‌های ارسالی"""
    text = update.message.text.strip()
    
    # برسی لینک بودن پیام
    if text.startswith("http://") or text.startswith("https://"):
        await update.message.reply_text("🔗 لینک دریافت شد! در حال پردازش دانلود...")
    else:
        await update.message.reply_text(f"🔍 در حال جستجوی فیلم/سریال: **{text}** ...", parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش دکمه‌های شیشه‌ای"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"گزینه انتخاب شده: {query.data}")

# ------------------------------------------------------------------------------
# 4. Initialize Telegram Application
# ------------------------------------------------------------------------------
bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

# اضافه کردن Handlerها
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
    """دریافت زنده پیام‌های تلگرام از طریق Webhook"""
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, bot_app.bot)
        
        # اجرای پردازش پیام در event loop جاری
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        loop.create_task(bot_app.process_update(update))
        return "OK", 200

# ------------------------------------------------------------------------------
# 6. Main Execution Block
# ------------------------------------------------------------------------------
async def main_async():
    """تنظیمات اولیه وب‌هووک و شروع ربات"""
    async with bot_app:
        await bot_app.initialize()
        await bot_app.start()
        
        webhook_url = f"{RENDER_URL}/telegram"
        await bot_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set successfully to: {webhook_url}")

if __name__ == "__main__":
    # اجرا و ثبت Webhook
    asyncio.run(main_async())
    
    # اجرا و بالا آوردن سرور Flask روی پورت Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)