import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

# ⚠️ آیدی عددی تلگرام خودت به عنوان ادمین اصلی
OWNER_ID = 7474010387
TOKEN = "8934125933:AAF2dD4FpUY_09YSUqoI3MPreHaaNB5g4bc"

# دیتابیس‌های موقت در حافظه
ADMIN_IDS = {OWNER_ID}
USERS_DB = set()
MOVIES_DB = {}

# حالت‌های گفتگو (Conversation States)
(GET_TITLE, GET_VIDEO, GET_NEW_ADMIN, 
 REMOVE_ADMIN, DELETE_MOVIE, BROADCAST_MSG) = range(6)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- وب سرور ساختگی برای Health Check رایگان Render ---
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

# --- منوی اصلی ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USERS_DB.add(user_id)
    
    keyboard = []
    for m_id, m_data in MOVIES_DB.items():
        keyboard.append([InlineKeyboardButton(f"🎬 {m_data['title']}", callback_data=f"show_{m_id}")])

    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ پنل مدیریت پیشرفته", callback_data='admin_panel')])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    msg = "سلام! به ربات اختصاصی فیلم خوش آمدید.\nلطفاً فیلم مورد نظر خود را انتخاب کنید:" if MOVIES_DB else "سلام! هنوز هیچ فیلمی اضافه نشده است."

    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text(msg, reply_markup=reply_markup)

# --- مدیریت کلیک روی دکمه‌ها ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

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
        if user_id not in ADMIN_IDS:
            return
        
        keyboard = [
            [InlineKeyboardButton("➕ افزودن فیلم", callback_data='add_movie'),
             InlineKeyboardButton("❌ حذف فیلم", callback_data='del_movie')],
            [InlineKeyboardButton("👤 افزودن ادمین", callback_data='add_admin'),
             InlineKeyboardButton("🗑 حذف ادمین", callback_data='rem_admin')],
            [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data='broadcast')],
            [InlineKeyboardButton("📊 آمار ربات", callback_data='stats')]
        ]
        await query.message.reply_text("🛠 **پنل مدیریت پیشرفته**\nلطفاً یک گزینه را انتخاب کنید:", 
                                       reply_markup=InlineKeyboardMarkup(keyboard), 
                                       parse_mode='Markdown')
        
    elif query.data == 'stats':
        if user_id in ADMIN_IDS:
            text = f"📊 **آمار کل ربات:**\n\n👥 تعداد کاربران: {len(USERS_DB)}\n🎬 تعداد فیلم‌ها: {len(MOVIES_DB)}\n👮‍♂️ تعداد ادمین‌ها: {len(ADMIN_IDS)}"
            await query.message.reply_text(text, parse_mode='Markdown')

# --- بخش افزودن فیلم ---
async def start_add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await query.message.reply_text("لطفاً **عنوان/اسم فیلم** را ارسال کنید:")
    return GET_TITLE

async def get_movie_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_title'] = update.message.text
    await update.message.reply_text("عالی! حالا **خود ویدیو/فایل فیلم** را بفرستید:")
    return GET_VIDEO

async def get_movie_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_file_id = update.message.video.file_id
    title = context.user_data['temp_title']
    movie_id = str(len(MOVIES_DB) + 1)
    MOVIES_DB[movie_id] = {'title': title, 'file_id': video_file_id}
    await update.message.reply_text(f"✅ فیلم **{title}** با موفقیت اضافه شد!")
    return ConversationHandler.END

# --- بخش حذف فیلم ---
async def start_del_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not MOVIES_DB:
        await query.message.reply_text("هیچ فیلمی برای حذف وجود ندارد.")
        return ConversationHandler.END
    
    text = "لیست فیلم‌ها:\n"
    for m_id, m_data in MOVIES_DB.items():
        text += f"کد `{m_id}` -> {m_data['title']}\n"
    text += "\nلطفاً **کد فیلم** مورد نظر جهت حذف را بفرستید:"
    await query.message.reply_text(text, parse_mode='Markdown')
    return DELETE_MOVIE

async def process_del_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m_id = update.message.text.strip()
    if m_id in MOVIES_DB:
        deleted = MOVIES_DB.pop(m_id)
        await update.message.reply_text(f"✅ فیلم **{deleted['title']}** حذف شد.")
    else:
        await update.message.reply_text("❌ کدی که فرستادید معتبر نیست.")
    return ConversationHandler.END

# --- بخش مدیریت ادمین‌ها ---
async def start_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID:
        await query.message.reply_text("⚠️ فقط ادمین اصلی می‌تواند ادمین جدید اضافه کند.")
        return ConversationHandler.END
    await query.message.reply_text("لطفاً **آیدی عددی (User ID)** کاربر مورد نظر را بفرستید:")
    return GET_NEW_ADMIN

async def process_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_id = int(update.message.text.strip())
        ADMIN_IDS.add(new_id)
        await update.message.reply_text(f"✅ کاربر `{new_id}` با موفقیت ادمین شد.", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ آیدی عددی نامعتبر است.")
    return ConversationHandler.END

async def start_rem_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID:
        await query.message.reply_text("⚠️ فقط ادمین اصلی می‌تواند ادمین‌ها را عزل کند.")
        return ConversationHandler.END
    await query.message.reply_text("لطفاً **آیدی عددی** ادمینی که می‌خواهید دسترسی‌اش گرفته شود را بفرستید:")
    return REMOVE_ADMIN

async def process_rem_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text.strip())
        if target_id == OWNER_ID:
            await update.message.reply_text("❌ امکان حذف ادمین اصلی وجود ندارد!")
        elif target_id in ADMIN_IDS:
            ADMIN_IDS.remove(target_id)
            await update.message.reply_text(f"✅ دسترسی ادمین `{target_id}` گرفته شد.", parse_mode='Markdown')
        else:
            await update.message.reply_text("این کاربر در لیست ادمین‌ها نبود.")
    except ValueError:
        await update.message.reply_text("❌ آیدی عددی نامعتبر است.")
    return ConversationHandler.END

# --- پیام همگانی ---
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("متن پیامی که می‌خواهید برای **همه کاربران** ارسال شود را بفرستید:")
    return BROADCAST_MSG

async def process_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    count = 0
    for uid in USERS_DB:
        try:
            await context.bot.send_message(chat_id=uid, text=msg_text)
            count += 1
        except Exception:
            pass
    await update.message.reply_text(f"📢 پیام برای {count} کاربر ارسال شد.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

if __name__ == '__main__':
    threading.Thread(target=run_dummy_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_movie, pattern='^add_movie$'),
            CallbackQueryHandler(start_del_movie, pattern='^del_movie$'),
            CallbackQueryHandler(start_add_admin, pattern='^add_admin$'),
            CallbackQueryHandler(start_rem_admin, pattern='^rem_admin$'),
            CallbackQueryHandler(start_broadcast, pattern='^broadcast$')
        ],
        states={
            GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_movie_title)],
            GET_VIDEO: [MessageHandler(filters.VIDEO, get_movie_video)],
            DELETE_MOVIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_del_movie)],
            GET_NEW_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_admin)],
            REMOVE_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_rem_admin)],
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_broadcast)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()