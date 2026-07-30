import os
import json
import threading
import logging
import asyncio
import re
from typing import Dict, Any
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
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
# 2. Database Management (JSON Persistence)
# ------------------------------------------------------------------------------
DB_FILE = "bot_database.json"
OWNER_ID = 7474010387  # آیدی عددی مالک اصلی

DEFAULT_DATA = {
    "admins": [OWNER_ID],
    "required_channel": "",
    "movie_counter": 1,
    "movies": {}
}

def load_db():
    if not os.path.exists(DB_FILE):
        save_db(DEFAULT_DATA)
        return DEFAULT_DATA
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["movies"] = {int(k): v for k, v in data.get("movies", {}).items()}
            return data
    except Exception as e:
        logger.error(f"Error loading DB: {e}")
        return DEFAULT_DATA

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error saving DB: {e}")

DB = load_db()
BOT_TOKEN = "8934125933:AAF2dD4FpUY_09YSUqoI3MPreHaaNB5g4bc"

# Conversation States
(
    TITLE, SYNOPSIS, TEASER, QUALITIES, 
    ADD_ADMIN_ID, SET_CHANNEL_USERNAME
) = range(6)

# ------------------------------------------------------------------------------
# 3. Helpers & Security
# ------------------------------------------------------------------------------
def sanitize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'[<>]', '', text).strip()

def is_admin(user_id: int) -> bool:
    return user_id in DB.get("admins", [OWNER_ID])

async def check_channel_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    channel = DB.get("required_channel", "")
    if not channel:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        logger.error(f"Channel Check Error: {e}")
        return True

# ------------------------------------------------------------------------------
# 4. User Handlers
# ------------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id) and not await check_channel_membership(user.id, context):
        channel = DB["required_channel"]
        keyboard = [
            [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{channel.replace('@', '')}")],
            [InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_join")]
        ]
        msg = f"⚠️ کاربر گرامی، برای استفاده از ربات لطفاً ابتدا در کانال زیر عضو شوید:\n\n👉 {channel}"
        if update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        elif update.callback_query:
            await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    welcome_msg = (
        f"سلام {user.first_name} عزیز! 👋\n\n"
        "به ربات تخصصی دانلود و تماشای فیلم خوش آمدید.\n"
        "جهت مشاهده فهرست یا استفاده از امکانات، از دکمه‌های زیر استفاده کنید:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎬 لیست فیلم‌ها", callback_data="list_movies")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help_info")]
    ]
    
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("⚙️ پنل مدیریت کامل", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(welcome_msg, reply_markup=reply_markup)

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if await check_channel_membership(query.from_user.id, context):
        await query.message.reply_text("✅ عضویت شما تأیید شد!")
        await start_command(update, context)
    else:
        await query.answer("❌ شما هنوز در کانال عضو نشده‌اید!", show_alert=True)

async def help_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    help_text = (
        "ℹ️ **راهنمای استفاده از ربات:**\n\n"
        "1. از بخش 'لیست فیلم‌ها' فیلم مورد نظر خود را انتخاب کنید.\n"
        "2. خلاصه داستان و تیزر را مشاهده کنید.\n"
        "3. کیفیت دلخواه را جهت دانلود انتخاب کنید."
    )
    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]]
    await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def list_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    movies = DB.get("movies", {})
    if not movies:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")]]
        await query.edit_message_text("هنوز هیچ فیلمی ثبت نشده است.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for m_id, m_data in movies.items():
        keyboard.append([InlineKeyboardButton(f"🎬 {m_data['title']}", callback_data=f"mv_{m_id}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main")])

    await query.edit_message_text(
        "📋 **فهرست فیلم‌های موجود:**\nفیلم مورد نظر خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def show_movie_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        movie_id = int(query.data.split("_")[1])
    except Exception:
        await query.edit_message_text("❌ دیتای نامعتبر.")
        return

    movie = DB["movies"].get(movie_id)

    if not movie:
        await query.edit_message_text("❌ فیلم یافت نشد یا پاک شده است.")
        return

    caption = f"🎬 **{movie['title']}**\n\n📝 **خلاصه داستان:**\n{movie['synopsis']}\n"
    keyboard = []
    
    q_buttons = []
    qualities = movie.get("qualities", {})
    for idx, q_name in enumerate(qualities.keys()):
        q_buttons.append(InlineKeyboardButton(f"📥 {q_name}", callback_data=f"dl_{movie_id}_{idx}"))
    if q_buttons:
        keyboard.append(q_buttons)

    if movie.get("teaser_file_id"):
        keyboard.append([InlineKeyboardButton("🎥 تماشای تیزر", callback_data=f"ts_{movie_id}")])

    if is_admin(query.from_user.id):
        keyboard.append([InlineKeyboardButton("🗑 حذف این فیلم", callback_data=f"dmv_{movie_id}")])

    keyboard.append([InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="list_movies")])

    await query.edit_message_text(text=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def send_teaser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    movie_id = int(query.data.split("_")[1])
    movie = DB["movies"].get(movie_id)
    if movie and movie.get("teaser_file_id"):
        await query.message.reply_video(video=movie["teaser_file_id"], caption=f"🎥 تیزر: **{movie['title']}**", parse_mode="Markdown")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    movie_id = int(parts[1])
    q_idx = int(parts[2])

    movie = DB["movies"].get(movie_id)
    if not movie:
        await query.message.reply_text("❌ فیلم پیدا نشد.")
        return

    qualities_list = list(movie.get("qualities", {}).items())
    if q_idx >= len(qualities_list):
        await query.message.reply_text("❌ کیفیت نامعتبر است.")
        return

    q_name, file_ref = qualities_list[q_idx]
    await query.message.reply_text(f"⏳ در حال آماده‌سازی **{q_name}** فیلم **{movie['title']}**...", parse_mode="Markdown")

    try:
        if file_ref.startswith("http"):
            await query.message.reply_text(f"🔗 **لینک دانلود ({q_name}):**\n{file_ref}", parse_mode="Markdown")
        else:
            await query.message.reply_video(video=file_ref, caption=f"🎬 {movie['title']} - {q_name}")
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        await query.message.reply_text("❌ خطا در ارسال فایل. دوباره تلاش کنید.")

# ------------------------------------------------------------------------------
# 5. Admin Panel Functions
# ------------------------------------------------------------------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
        return
    await query.answer()

    channel_status = DB.get("required_channel") or "غیرفعال"
    text = f"⚙️ **پنل مدیریت ربات**\n\n📢 **کانال جوین اجباری:** {channel_status}\n👥 **تعداد ادمین‌ها:** {len(DB['admins'])}"

    keyboard = [
        [InlineKeyboardButton("➕ افزودن فیلم جدید", callback_data="admin_add_movie")],
        [InlineKeyboardButton("🗑 لیست حذف فیلم‌ها", callback_data="admin_delete_list")],
        [InlineKeyboardButton("👥 مدیریت ادمین‌ها", callback_data="admin_manage_admins")],
        [InlineKeyboardButton("📢 تنظیم کانال جوین اجباری", callback_data="admin_set_channel")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ **عنوان فیلم را وارد کنید:**")
    return TITLE

async def admin_get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = sanitize_text(update.message.text)
    context.user_data["new_movie"] = {"title": title, "qualities": {}}
    await update.message.reply_text("📝 **خلاصه داستان فیلم را وارد کنید:**")
    return SYNOPSIS

async def admin_get_synopsis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_movie"]["synopsis"] = sanitize_text(update.message.text)
    await update.message.reply_text("🎥 **فایل ویدیو تیزر را ارسال کنید** یا کلمه `skip` را بنویسید:", parse_mode="Markdown")
    return TEASER

async def admin_get_teaser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        context.user_data["new_movie"]["teaser_file_id"] = update.message.video.file_id
    else:
        context.user_data["new_movie"]["teaser_file_id"] = None

    await update.message.reply_text(
        "📥 **کیفیت‌ها را وارد کنید:**\nمثال: `1080p = لینک` یا ویدیو بفرستید و کپشن کیفیت بگذارید.\nدر پایان کلمه `done` را بفرستید.",
        parse_mode="Markdown"
    )
    return QUALITIES

async def admin_get_qualities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text if update.message.text else ""
    if text.lower() == "done":
        movie_data = context.user_data.get("new_movie")
        if not movie_data.get("qualities"):
            await update.message.reply_text("⚠️ حداقل یک کیفیت ثبت کنید!")
            return QUALITIES
        
        m_id = DB["movie_counter"]
        DB["movies"][m_id] = movie_data
        DB["movie_counter"] += 1
        save_db(DB)
        
        await update.message.reply_text(f"✅ فیلم **{movie_data['title']}** با موفقیت ثبت شد!", parse_mode="Markdown")
        return ConversationHandler.END

    if update.message.video and update.message.caption:
        q_name = sanitize_text(update.message.caption)
        context.user_data["new_movie"]["qualities"][q_name] = update.message.video.file_id
        await update.message.reply_text(f"✅ کیفیت `{q_name}` ثبت شد. بعدی یا `done`؟", parse_mode="Markdown")
        return QUALITIES

    if "=" in text:
        parts = text.split("=", 1)
        q_name, ref = sanitize_text(parts[0]), parts[1].strip()
        context.user_data["new_movie"]["qualities"][q_name] = ref
        await update.message.reply_text(f"✅ کیفیت `{q_name}` ثبت شد. بعدی یا `done`؟", parse_mode="Markdown")
        return QUALITIES

    await update.message.reply_text("❌ فرمت نامعتبر!")
    return QUALITIES

async def admin_delete_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    movies = DB.get("movies", {})
    if not movies:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]]
        await query.edit_message_text("هیچ فیلمی برای حذف وجود ندارد.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for m_id, m_data in movies.items():
        keyboard.append([InlineKeyboardButton(f"❌ حذف: {m_data['title']}", callback_data=f"dmv_{m_id}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")])

    await query.edit_message_text(
        "🗑 **روی فیلم مورد نظر جهت حذف کلیک کنید:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def admin_delete_movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    movie_id = int(query.data.split("_")[1])
    if movie_id in DB["movies"]:
        deleted_title = DB["movies"][movie_id]["title"]
        del DB["movies"][movie_id]
        save_db(DB)
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]]
        await query.edit_message_text(f"✅ فیلم **{deleted_title}** با موفقیت حذف شد.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await query.edit_message_text("❌ این فیلم قبلاً حذف شده است.")

async def admin_manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admins_text = "\n".join([f"• `{a}`" for a in DB["admins"]])
    msg = f"👥 **لیست ادمین‌های فعلی:**\n{admins_text}"
    
    keyboard = [
        [InlineKeyboardButton("➕ افزودن ادمین جدید", callback_data="admin_add_new")],
        [InlineKeyboardButton("🗑 حذف ادمین", callback_data="admin_remove_select")],
        [InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def start_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("❌ فقط مالک اصلی می‌تواند ادمین اضافه کند!", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text("🔢 **آیدی عددی کاربر جدید را ارسال کنید:**")
    return ADD_ADMIN_ID

async def get_add_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_id = int(update.message.text.strip())
        if new_id not in DB["admins"]:
            DB["admins"].append(new_id)
            save_db(DB)
            await update.message.reply_text(f"✅ کاربر `{new_id}` به ادمین‌ها اضافه شد.", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ این کاربر از قبل ادمین بود.")
    except ValueError:
        await update.message.reply_text("❌ آیدی عددی نامعتبر است.")
    return ConversationHandler.END

async def remove_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("❌ فقط مالک اصلی می‌تواند ادمین حذف کند!", show_alert=True)
        return
    await query.answer()
    
    keyboard = []
    for a_id in DB["admins"]:
        if a_id != OWNER_ID:
            keyboard.append([InlineKeyboardButton(f"❌ حذف {a_id}", callback_data=f"deladmin_{a_id}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_manage_admins")])
    await query.edit_message_text("کدام ادمین را می‌خواهید حذف کنید؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split("_")[1])
    if target_id in DB["admins"] and target_id != OWNER_ID:
        DB["admins"].remove(target_id)
        save_db(DB)
        await query.edit_message_text(f"✅ ادمین `{target_id}` با موفقیت حذف شد.", parse_mode="Markdown")

async def start_set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("🚫 غیرفعال‌سازی جوین اجباری", callback_data="disable_channel")]]
    await query.edit_message_text(
        "📢 **آیدی کانال را با @ بفرستید:**\n(مثال: `@mychannel`)\n\n⚠️ **نکته:** ربات حتماً باید در کانال ادمین باشد.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return SET_CHANNEL_USERNAME

async def get_channel_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ch_name = update.message.text.strip()
    if not ch_name.startswith("@"):
        await update.message.reply_text("❌ آیدی کانال باید با @ شروع شود.")
        return SET_CHANNEL_USERNAME
    
    DB["required_channel"] = ch_name
    save_db(DB)
    await update.message.reply_text(f"✅ کانال جوین اجباری روی `{ch_name}` تنظیم شد.", parse_mode="Markdown")
    return ConversationHandler.END

async def disable_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    DB["required_channel"] = ""
    save_db(DB)
    await query.edit_message_text("✅ قفل عضویت اجباری کانال غیرفعال شد.")

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ عملیات لغو شد.")
    return ConversationHandler.END

# ------------------------------------------------------------------------------
# 6. Web Server & Async Telegram Bot Runner
# ------------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Movie Bot Status: Alive and Running 24/7 on Render Web Service!", 200

def run_telegram_bot():
    """اجرای ربات تلگرام در یک Event Loop جداگانه در پس‌زمینه"""
    loop = asyncio.new_event_policy().new_event_loop()
    asyncio.set_event_loop(loop)

    bot_app = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handlers
    movie_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_start_add, pattern="^admin_add_movie$")],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_title)],
            SYNOPSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_synopsis)],
            TEASER: [MessageHandler(filters.VIDEO | filters.TEXT, admin_get_teaser)],
            QUALITIES: [MessageHandler(filters.VIDEO | filters.TEXT, admin_get_qualities)]
        },
        fallbacks=[CommandHandler("cancel", cancel_flow)]
    )

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_admin, pattern="^admin_add_new$")],
        states={ADD_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_add_admin_id)]},
        fallbacks=[CommandHandler("cancel", cancel_flow)]
    )

    channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_set_channel, pattern="^admin_set_channel$")],
        states={SET_CHANNEL_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_channel_username)]},
        fallbacks=[CommandHandler("cancel", cancel_flow)]
    )

    # Handlers
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(movie_conv)
    bot_app.add_handler(admin_conv)
    bot_app.add_handler(channel_conv)

    bot_app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    bot_app.add_handler(CallbackQueryHandler(list_movies, pattern="^list_movies$"))
    bot_app.add_handler(CallbackQueryHandler(help_info, pattern="^help_info$"))
    bot_app.add_handler(CallbackQueryHandler(start_command, pattern="^back_to_main$"))
    
    bot_app.add_handler(CallbackQueryHandler(show_movie_details, pattern="^mv_"))
    bot_app.add_handler(CallbackQueryHandler(send_teaser, pattern="^ts_"))
    bot_app.add_handler(CallbackQueryHandler(handle_download, pattern="^dl_"))
    bot_app.add_handler(CallbackQueryHandler(admin_delete_movie_callback, pattern="^dmv_"))
    
    bot_app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    bot_app.add_handler(CallbackQueryHandler(admin_delete_list, pattern="^admin_delete_list$"))
    bot_app.add_handler(CallbackQueryHandler(admin_manage_admins, pattern="^admin_manage_admins$"))
    bot_app.add_handler(CallbackQueryHandler(remove_admin_list, pattern="^admin_remove_select$"))
    bot_app.add_handler(CallbackQueryHandler(handle_remove_admin, pattern="^deladmin_"))
    bot_app.add_handler(CallbackQueryHandler(disable_channel_callback, pattern="^disable_channel$"))

    logger.info("Initializing Telegram Bot Polling...")
    bot_app.run_polling(close_loop=False)

# روشن کردن ربات تلگرام در پس‌زمینه
t = threading.Thread(target=run_telegram_bot, daemon=True)
t.start()

# این بخش اصلی پروژه برای اجرای وب‌سرور Flask روی پورت Render است
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)