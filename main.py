import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ------------------------------------------------------------------------------
# 1. Logging
# ------------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# 2. Config & Env Variables
# ------------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

if RENDER_URL.endswith("/"):
    RENDER_URL = RENDER_URL[:-1]

# ------------------------------------------------------------------------------
# 3. Handlers
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
        "2️⃣ ارسال لینک مستقیم فایل جهت دانلود مستقیم"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("http://") or text.startswith("https://"):
        await update.message.reply_text("🔗 لینک دریافت شد! در حال پردازش...")
    else:
        await update.message.reply_text(f"🔍 در حال جستجوی فیلم/سریال: **{text}** ...", parse_mode="Markdown")

# ------------------------------------------------------------------------------
# 4. Build Application
# ------------------------------------------------------------------------------
bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ------------------------------------------------------------------------------
# 5. Flask App
# ------------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Bot Server is Alive!", 200

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, bot_app.bot)
        
        # اجرای ایمن آپدیت‌ها در event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(bot_app.initialize())
            loop.run_until_complete(bot_app.process_update(update))
        finally:
            loop.close()

        return "OK", 200

# ------------------------------------------------------------------------------
# 6. Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # تنظیم وب‌هووک با API مستقیم تلگرام
    if RENDER_URL and BOT_TOKEN:
        import requests
        webhook_url = f"{RENDER_URL}/telegram"
        set_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
        res = requests.get(set_url)
        logger.info(f"Set Webhook Response: {res.json()}")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)