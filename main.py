import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ---------------- تنظیمات اصلی ----------------
BOT_TOKEN = "8934125933:AAF2dD4FpUY_09YSUqoI3MPreHaaNB5g4bc"
ADMIN_ID = 7474072387

DATA_FILE = "settings.json"

# تنظیم لاگ‌ها
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---------------- مدیریت ذخیره‌سازی تنظیمات ----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {"force_join_enabled": True, "channels": []}
        save_data(default_data)
        return default_data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ---------------- دیتابیس فیلم‌ها ----------------
movies_db = {
    "Inception": {
        "info": "سال ساخت: 2010 | کارگردان: کریستوفر نولان",
        "qualities": {
            "1080p": "BAACAgIAAxkBAAI...",
            "720p": "BAACAgIAAxkBAAJ..."
        }
    }
}

# ---------------- بررسی عضویت در همه کانال‌ها ----------------
async def check_user_subscriptions(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    data = load_data()
    if not data.get("force_join_enabled", True):
        return True, []  # اگر قفل خاموش باشه، تایید میشه

    not_joined = []
    for channel in data.get("channels", []):
        try:
            member = await context.bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(channel)
        except Exception:
            # اگر ربات توی کانال ادمین نباشه یا آیدی اشتباه باشه
            not_joined.append(channel)

    is_all_joined = (len(not_joined) == 0)
    return is_all_joined, not_joined

# ---------------- پیام عضویت اجباری ----------------
async def show_force_join_msg(update: Update, context: ContextTypes.DEFAULT_TYPE, not_joined_channels: list, target_param: str = ""):
    keyboard = []
    for ch in not_joined_channels:
        keyboard.append([InlineKeyboardButton(f"📢 عضویت در کانال @{ch}", url=f"https://t.me/{ch}")])
    
    keyboard.append([InlineKeyboardButton("✅ عضو شدم / تایید", callback_data=f"check_join_{target_param}")])
    text = "❤️ **برای استفاده از ربات و دانلود فیلم‌ها، لطفاً ابتدا در کانال‌های زیر عضو شوید:**"
    
    query = update.callback_query
    if query:
        await query.answer("لطفاً ابتدا در تمام کانال‌ها عضو شوید!", show_alert=True)
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ---------------- دستور /start ----------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    target_param = args[0] if args else "main"

    is_joined, not_joined = await check_user_subscriptions(context, user_id)
    if not is_joined:
        await show_force_join_msg(update, context, not_joined, target_param)
        return

    if target_param.startswith("movie_"):
        movie_title = target_param.replace("movie_", "")
        await send_movie_page(update, context, movie_title)
    else:
        await send_main_menu(update, context)

# ---------------- منوی اصلی و دانلود ----------------
async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🎬 **به آرشیو رایگان فیلم خوش آمدید!**\nاز منوی زیر استفاده کنید:"
    keyboard = [[InlineKeyboardButton("📜 مشاهده لیست فیلم‌ها", callback_data="list_movies")]]
    
    query = update.callback_query
    if query:
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def send_movie_page(update: Update, context: ContextTypes.DEFAULT_TYPE, movie_title: str):
    movie = movies_db.get(movie_title)
    if not movie:
        text = "❌ فیلم مورد نظر یافت نشد."
        markup = None
    else:
        text = f"🎬 **{movie_title}**\n\n📝 {movie['info']}\n\nکیفیت مورد نظر را انتخاب کنید:"
        keyboard = []
        for q_name in movie["qualities"].keys():
            keyboard.append([InlineKeyboardButton(f"📥 دانلود {q_name}", callback_data=f"dl_{movie_title}_{q_name}")])
        keyboard.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="main_menu")])
        markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    if query:
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode="Markdown")

# ----------------------------------------------------
# 👑 بخش پنل ادمین (ADMIN PANEL)
# ----------------------------------------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    data = load_data()
    status_str = "🟢 فعال" if data.get("force_join_enabled", True) else "🔴 غیرفعال"
    channels_list = "\n".join([f"• @{ch}" for ch in data.get("channels", [])]) or "هیچ کانالی ثبت نشده"

    text = (
        f"⚙️ **پنل مدیریت ربات**\n\n"
        f"وضعیت قفل عضویت: **{status_str}**\n\n"
        f"📋 **لیست کانال‌های فعال:**\n{channels_list}"
    )

    toggle_btn_text = "🔴 غیرفعال‌سازی قفل" if data.get("force_join_enabled", True) else "🟢 فعال‌سازی قفل"
    
    keyboard = [
        [InlineKeyboardButton(toggle_btn_text, callback_data="admin_toggle_lock")],
        [InlineKeyboardButton("➕ افزودن کانال", callback_data="admin_add_channel"),
         InlineKeyboardButton("➖ حذف کانال", callback_data="admin_del_channel")]
    ]

    query = update.callback_query
    if query:
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ---------------- مدیریت کارهای ادمین و دکمه‌ها ----------------
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    # ۱. بررسی عضویت مجدد کاربر
    if data.startswith("check_join_"):
        target_param = data.replace("check_join_", "")
        is_joined, not_joined = await check_user_subscriptions(context, user_id)
        if is_joined:
            await query.answer("✅ عضویت شما تایید شد!", show_alert=False)
            if target_param.startswith("movie_"):
                movie_title = target_param.replace("movie_", "")
                await send_movie_page(update, context, movie_title)
            else:
                await send_main_menu(update, context)
        else:
            await show_force_join_msg(update, context, not_joined, target_param)

    elif data == "main_menu":
        await send_main_menu(update, context)

    # ۲. دکمه‌های پنل ادمین
    elif user_id == ADMIN_ID:
        config_data = load_data()

        if data == "admin_toggle_lock":
            config_data["force_join_enabled"] = not config_data.get("force_join_enabled", True)
            save_data(config_data)
            await query.answer("وضعیت قفل تغییر کرد!")
            await admin_panel(update, context)

        elif data == "admin_add_channel":
            context.user_data["awaiting_input"] = "add_channel"
            await query.edit_message_text("✏️ لطفاً آیدی کانال را **بدون @** بفرستید:\nمثال: `MyMovieChannel`", parse_mode="Markdown")

        elif data == "admin_del_channel":
            context.user_data["awaiting_input"] = "del_channel"
            await query.edit_message_text("✏️ لطفاً آیدی کانالی که می‌خواهید حذف شود را **بدون @** بفرستید:", parse_mode="Markdown")

# ---------------- دریافت متن ورودی از ادمین ----------------
async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    state = context.user_data.get("awaiting_input")
    if not state:
        return

    text = update.message.text.strip().replace("@", "")
    config_data = load_data()

    if state == "add_channel":
        if text not in config_data["channels"]:
            config_data["channels"].append(text)
            save_data(config_data)
            await update.message.reply_text(f"✅ کانال @{text} با موفقیت اضافه شد.\n⚠️ **نکته مهم:** حتماً ربات را در این کانال ادمین کنید!")
        else:
            await update.message.reply_text("این کانال قبلاً اضافه شده است.")

    elif state == "del_channel":
        if text in config_data["channels"]:
            config_data["channels"].remove(text)
            save_data(config_data)
            await update.message.reply_text(f"❌ کانال @{text} حذف شد.")
        else:
            await update.message.reply_text("این کانال در لیست وجود ندارد.")

    context.user_data["awaiting_input"] = None
    await admin_panel(update, context)

# ---------------- بخش اصلی اجرا ----------------
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ثبت دستورات
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("panel", admin_panel))  # دستور پنل ادمین
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    print("Bot is running...")
    app.run_polling()