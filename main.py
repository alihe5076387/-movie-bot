import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

BOT_USERNAME = "YourBotUsername" # آیدی ربات بدون @
CHANNEL_USERNAME = "YourChannelUsername" # آیدی کانال شما بدون @

# دیتابیس فیلم‌ها
movies_db = {
    "Inception": {
        "info": "سال ساخت: 2010 | کارگردان: کریستوفر نولان",
        "trailer": None,
        "qualities": {
            "1080p": "BAACAgIAAxkBAAI...", # file_id تلگرام
            "720p": "BAACAgIAAxkBAAJ..."
        }
    }
}

# ---------------- بررسی عضویت در کانال ----------------
async def is_subscribed(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

# ---------------- پیام عضویت اجباری ----------------
async def show_force_join_msg(update: Update, context: ContextTypes.DEFAULT_TYPE, target_param: str = ""):
    keyboard = [
        [InlineKeyboardButton("📢 عضویت در کانال ما", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("✅ عضو شدم / تایید", callback_data=f"check_join_{target_param}")]
    ]
    text = "❤️ **برای دانلود رایگان فیلم‌ها، لطفاً ابتدا در کانال ما عضو شوید:**"
    
    query = update.callback_query
    if query:
        await query.answer("لطفاً ابتدا عضو کانال شوید!", show_alert=True)
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ---------------- استارت ربات و دریافت لینک اختصاصی ----------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    target_param = args[0] if args else "main"

    # بررسی عضویت کانال
    if not await is_subscribed(context, user_id):
        await show_force_join_msg(update, context, target_param)
        return

    # اگر کاربر عضو بود، هدایت مستقیم به فیلم
    if target_param.startswith("movie_"):
        movie_title = target_param.replace("movie_", "")
        await send_movie_page(update, context, movie_title)
    else:
        await send_main_menu(update, context)

# ---------------- تایید عضویت ----------------
async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    target_param = query.data.replace("check_join_", "")

    if await is_subscribed(context, user_id):
        await query.answer("✅ خوش آمدید!", show_alert=False)
        if target_param.startswith("movie_"):
            movie_title = target_param.replace("movie_", "")
            await send_movie_page(update, context, movie_title)
        else:
            await send_main_menu(update, context)
    else:
        await query.answer("❌ هنوز عضو کانال نشده‌اید!", show_alert=True)

# ---------------- صفحه دانلود رایگان فیلم ----------------
async def send_movie_page(update: Update, context: ContextTypes.DEFAULT_TYPE, movie_title: str):
    movie = movies_db.get(movie_title)
    if not movie:
        text = "❌ فیلم مورد نظر یافت نشد."
        markup = None
    else:
        text = (
            f"🎬 **{movie_title}**\n\n"
            f"📝 **توضیحات:**\n{movie['info']}\n\n"
            f"🎉 **دانلود ۱۰۰٪ رایگان:**\nلطفاً کیفیت مورد نظر را انتخاب کنید:"
        )
        
        keyboard = []
        for q_name in movie["qualities"].keys():
            keyboard.append([InlineKeyboardButton(f"📥 دانلود رایگان {q_name}", callback_data=f"dl_{movie_title}_{q_name}")])
        
        keyboard.append([InlineKeyboardButton("🔙 لیست همه فیلم‌ها", callback_data="main_menu")])
        markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    if query:
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode="Markdown")

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🎬 **به آرشیو رایگان فیلم خوش آمدید!**\nاز منوی زیر فیلم مورد نظرتون رو انتخاب کنید:"
    keyboard = [[InlineKeyboardButton("📜 مشاهده لیست فیلم‌ها", callback_data="list_movies")]]
    
    query = update.callback_query
    if query:
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")