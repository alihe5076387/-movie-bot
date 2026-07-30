import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ⚠️ توکن ربات خودت را دقیقاً بین این دو کوتیشن بگذار:
TOKEN = "8934125933:AAF2dD4FpUY_09YSUqoI3MPreHaaNB5g4bc"

# فعال‌سازی لاگ برای مشاهده وضعیت ربات در ترمینال
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# منوی اصلی ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 فیلم ۱: Inception", callback_data='movie_1')],
        [InlineKeyboardButton("🎬 فیلم ۲: Interstellar", callback_data='movie_2')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "سلام علی عزیز! به ربات اختصاصی فیلم خوش آمدید.\n\n"
        "لطفاً فیلم مورد نظر خود را انتخاب کنید:",
        reply_markup=reply_markup
    )

# پردازش دکمه‌ها و ارسال فیلم قفل‌شده (غیرقابل دانلود/فوروارد)
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'movie_1':
        video_url = "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4"
        caption = "🎥 **فیلم سینمایی Inception**\n\n⚠️ *این فایل قفل بوده و قابلیت دانلود، ذخیره در گالری یا فوروارد ندارد.*"
    elif query.data == 'movie_2':
        video_url = "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4"
        caption = "🎥 **فیلم سینمایی Interstellar**\n\n⚠️ *این فایل قفل بوده و قابلیت دانلود، ذخیره در گالری یا فوروارد ندارد.*"

    # ارسال ویدیو با قابلیت protect_content برای جلوگیری از دانلود و فوروارد
    await context.bot.send_video(
        chat_id=query.message.chat_id,
        video=video_url,
        caption=caption,
        parse_mode='Markdown',
        protect_content=True
    )

if __name__ == '__main__':
    print("---------------------------------------")
    print("🚀 ربات با موفقیت روشن شد و در حال کار است...")
    print("---------------------------------------")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    
    app.run_polling()