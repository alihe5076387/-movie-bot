import os
import logging
import asyncio
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

# ادمین اصلی سیستم (آیدی عددیت رو می‌تونی از @userinfobot بگیری)
SUPER_ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))

if RENDER_URL and RENDER_URL.endswith("/"):
    RENDER_URL = RENDER_URL[:-1]

# ------------------------------------------------------------------------------
# 3. In-Memory Data Storage (دیتابیس در حافظه)
# ------------------------------------------------------------------------------
users_list = set()
admins_list = {SUPER_ADMIN_ID}
movies_db = {}  # Format: {"movie_name": "download_link"}

# ذخیره وضعیت مکالمه ادمین‌ها
admin_states = {}

# ------------------------------------------------------------------------------
# 4. Keyboards
# ------------------------------------------------------------------------------
def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 آمار کامل ربات", callback_data="admin_stats")],
        [InlineKeyboardButton("🎬 اضافه کردن فیلم", callback_data="add_movie"), InlineKeyboardButton("🗑 حذف فیلم", callback_data="list_movies_delete")],
        [InlineKeyboardButton("➕ اضافه کردن ادمین", callback_data="add_admin"), InlineKeyboardButton("➖ حذف ادمین", callback_data="list_admins_delete")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ بستن پنل", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ------------------------------------------------------------------------------
# 5. Handlers
# ------------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_list.add(user.id)
    
    welcome_text = (
        f"سلام {user.first_name} عزیز! 👋\n\n"
        "به ربات دانلود فیلم و سریال خوش آمدید.\n"
        "برای دریافت فیلم، کافیست نام آن را ارسال کنید!"
    )
    await update.message.reply_text(welcome_text)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins_list:
        await update.message.reply_text("❌ شما دسترسی به پنل مدیریت را ندارید.")
        return
    
    admin_states.pop(user_id, None)
    await update.message.reply_text(
        "🛠 **پنل مدیریت پیشرفته ربات**\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=get_admin_keyboard(),
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users_list.add(user_id)
    text = update.message.text.strip()

    # وضعیت‌های پردازش ادمین
    if user_id in admin_states:
        state = admin_states[user_id]

        if state == "WAITING_FOR_ADMIN_ID":
            try:
                new_admin_id = int(text)
                admins_list.add(new_admin_id)
                del admin_states[user_id]
                await update.message.reply_text(f"✅ کاربر `{new_admin_id}` با موفقیت به ادمین‌ها اضافه شد.", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            except ValueError:
                await update.message.reply_text("⚠️ لطفاً یک آیدی عددی معتبر بفرستید.")
            return

        elif state == "WAITING_FOR_MOVIE_NAME":
            admin_states[user_id] = {"state": "WAITING_FOR_MOVIE_LINK", "name": text.lower()}
            await update.message.reply_text(f"عنوان فیلم: **{text}** ثبت شد.\nحالا لطفاً لینک دانلود فیلم را ارسال کنید:", parse_mode="Markdown")
            return

        elif isinstance(state, dict) and state.get("state") == "WAITING_FOR_MOVIE_LINK":
            movie_name = state["name"]
            movies_db[movie_name] = text
            del admin_states[user_id]
            await update.message.reply_text(f"✅ فیلم با عنوان `{movie_name}` و لینک دانلود ثبت شد!", parse_mode="Markdown", reply_markup=get_admin_keyboard())
            return

        elif state == "WAITING_FOR_BROADCAST":
            del admin_states[user_id]
            success_count = 0
            await update.message.reply_text("⏳ در حال ارسال پیام به تمام کاربران...")
            
            for uid in list(users_list):
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                    success_count += 1
                except Exception:
                    pass
            
            await update.message.reply_text(f"📢 پیام همگانی با موفقیت به {success_count} کاربر ارسال شد.", reply_markup=get_admin_keyboard())
            return

    # پاسخ خودکار به کاربران عادی (جستجوی فیلم)
    search_query = text.lower()
    if search_query in movies_db:
        link = movies_db[search_query]
        await update.message.reply_text(f"🎬 **فیلم پیدا شد!**\n\n📥 **لینک دانلود:**\n{link}", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"🔍 فیلمی با عنوان **{text}** پیدا نشد.\n\nنام فیلم را به انگلیسی یا دقیق‌تر وارد کنید.", parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if user_id not in admins_list:
        await query.edit_message_text("❌ شما دسترسی به این بخش را ندارید.")
        return

    data = query.data

    if data == "admin_stats":
        stats_text = (
            "📊 **آمار سیستم:**\n\n"
            f"👤 تعداد کل کاربران: **{len(users_list)}**\n"
            f"👑 تعداد ادمین‌ها: **{len(admins_list)}**\n"
            f"🎬 تعداد فیلم‌های موجود: **{len(movies_db)}**\n"
            "🟢 وضعیت سرور: فعال (Render Live)"
        )
        await query.edit_message_text(stats_text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")

    elif data == "add_admin":
        admin_states[user_id] = "WAITING_FOR_ADMIN_ID"
        await query.edit_message_text("➕ لطفاً **آیدی عددی** کاربر جدید را بفرستید:")

    elif data == "list_admins_delete":
        if len(admins_list) <= 1:
            await query.edit_message_text("⚠️ هیچ ادمین دیگری برای حذف وجود ندارد.", reply_markup=get_admin_keyboard())
            return
        
        keyboard = []
        for aid in admins_list:
            if aid != SUPER_ADMIN_ID:
                keyboard.append([InlineKeyboardButton(f"❌ حذف ادمین {aid}", callback_data=f"del_admin_{aid}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")])
        await query.edit_message_text("یک ادمین را برای حذف انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_admin_"):
        aid_to_del = int(data.replace("del_admin_", ""))
        admins_list.discard(aid_to_del)
        await query.edit_message_text(f"✅ ادمین {aid_to_del} با موفقیت حذف شد.", reply_markup=get_admin_keyboard())

    elif data == "add_movie":
        admin_states[user_id] = "WAITING_FOR_MOVIE_NAME"
        await query.edit_message_text("🎬 لطفاً **عنوان فیلم یا سریال** را بفرستید:")

    elif data == "list_movies_delete":
        if not movies_db:
            await query.edit_message_text("⚠️ هیچ فیلمی در سیستم ثبت نشده است.", reply_markup=get_admin_keyboard())
            return

        keyboard = []
        for m_name in movies_db.keys():
            keyboard.append([InlineKeyboardButton(f"🗑 حذف {m_name}", callback_data=f"del_movie_{m_name}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")])
        await query.edit_message_text("فیلم مورد نظر برای حذف را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_movie_"):
        m_to_del = data.replace("del_movie_", "")
        movies_db.pop(m_to_del, None)
        await query.edit_message_text(f"✅ فیلم `{m_to_del}` با موفقیت حذف شد.", reply_markup=get_admin_keyboard())

    elif data == "admin_broadcast":
        admin_states[user_id] = "WAITING_FOR_BROADCAST"
        await query.edit_message_text("📢 **متن پیام همگانی** خود را ارسال کنید:")

    elif data == "back_to_main":
        admin_states.pop(user_id, None)
        await query.edit_message_text("🛠 **پنل مدیریت پیشرفته ربات**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")

    elif data == "close_panel":
        admin_states.pop(user_id, None)
        await query.edit_message_text("پنل مدیریت بسته شد.")

# ------------------------------------------------------------------------------
# 6. Loop & App Initialization
# ------------------------------------------------------------------------------
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(CommandHandler("admin", admin_command))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
bot_app.add_handler(CallbackQueryHandler(button_callback))

loop.run_until_complete(bot_app.initialize())

# ------------------------------------------------------------------------------
# 7. Flask Server
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
        loop.run_until_complete(bot_app.process_update(update))
        return "OK", 200

# ------------------------------------------------------------------------------
# 8. Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    if RENDER_URL and BOT_TOKEN:
        import requests
        webhook_url = f"{RENDER_URL}/telegram"
        set_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
        res = requests.get(set_url)
        logger.info(f"Set Webhook Response: {res.json()}")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)