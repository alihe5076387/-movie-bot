import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

TOKEN = "8934125933:AAF2dD4FpUY_09YSUqoI3MPreHaaNB5g4bc"

# 🎯 آیدی تلگرام خودت و دوستت را اینجا بگذار (آیدی عددی)
ADMIN_IDS = [7474010387]  # آیدی عددی شما از خروجی قبلی

# دیتابیس ساده برای ذخیره فیلم‌ها در حافظه
# فرمت: {'movie_id': {'title': 'نام فیلم', 'file_id': 'کد ویدیو'}}
MOVIES_DB = {}

# مراحل دریافت فیلم جدید
GET_TITLE, GET_VIDEO = range(2)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = []

    # ساخت دکمه‌ها برای فیلم‌های موجود
    for m_id, m_data in MOVIES_DB.items():
        keyboard.append([InlineKeyboardButton(f"🎬 {m_data['title']}", callback_data=f"show_{m_id}")])

    # اگر کاربر ادمین باشد، دکمه پنل مدیریت را هم می‌بیند
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ پنل مدیریت (ویژه ادمین)", callback_data='admin_panel')])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    msg = "سلام! به ربات اختصاصی فیلم خوش آمدید.\nلطفاً فیلم مورد نظر خود را انتخاب کنید:" if MOVIES_DB else "سلام! هنوز هیچ فیلمی اضافه نشده است."

    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text(msg, reply_markup=reply_markup)

# نمایش فیلم انتخاب شده
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith('show_'):
        m_id = query.data.replace('show_', '')
        movie = MOVIES_DB.get(m_id)
        if movie:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=movie['file_id'],
                caption=f"🎥 **{movie['title']}**\n\n⚠️ *این فایل قفل بوده و قابلیت دانلود یا فوروارد ندارد.*",
                parse_mode='Markdown',
                protect_content=True
            )
    elif query.data == 'admin_panel':
        keyboard = [[InlineKeyboardButton("➕ افزودن فیلم جدید", callback_data='add_movie')]]
        await query.message.reply_text("welcome به پنل مدیریت! یک گزینه را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

# شروع فرآیند افزودن فیلم (ادمین)
async def start_add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMIN_IDS:
        return ConversationHandler.END

    await query.message.reply_text("لطفاً **عنوان/اسم فیلم** را ارسال کنید:")
    return GET_TITLE

# دریافت اسم فیلم
async def get_movie_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_title'] = update.message.text
    await update.message.reply_text("عالی! حالا **خود ویدیو/فایل فیلم** را در چت بفرستید:")
    return GET_VIDEO

# دریافت ویدیو و ذخیره آن
async def get_movie_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_file_id = update.message.video.file_id
    title = context.user_data['temp_title']
    movie_id = str(len(MOVIES_DB) + 1)

    MOVIES_DB[movie_id] = {'title': title, 'file_id': video_file_id}

    await update.message.reply_text(f"✅ فیلم **{title}** با موفقیت به ربات اضافه شد!")
    return ConversationHandler.END

# انصراف از ساخت
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    # گفتگوی افزودن فیلم
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_movie, pattern='^add_movie$')],
        states={
            GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_movie_title)],
            GET_VIDEO: [MessageHandler(filters.VIDEO, get_movie_video)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()