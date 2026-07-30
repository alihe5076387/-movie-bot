import os
import json
import logging
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

OWNER_ID = 7474010387
TOKEN = "8934125933:AAF2dD4FpUY_09YSUqoI3MPreHaaNB5g4bc"

# اطلاعات اتصال به دیتابیس ابری Upstash
REDIS_URL = "https://strong-boxer-108975.upstash.io"
REDIS_TOKEN = "gQAAAAAAAamvAAIgcDJhYjNiY2E1MjFiODU0Mzc5OGZmOWI0ZjM4ODBkMWRkOA"

ADMIN_IDS = {OWNER_ID}

# --- ذخیره و دریافت کاربران از دیتابیس ابری (بدون نیاز به requests) ---
def load_users():
    try:
        url = f"{REDIS_URL}/smembers/bot_users"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {REDIS_TOKEN}"})
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            if "result" in res and res["result"]:
                return set(int(x) for x in res["result"])
    except Exception as e:
        logging.error(f"Error loading users: {e}")
    return set()

def save_user(user_id):
    try:
        url = f"{REDIS_URL}/sadd/bot_users/{user_id}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {REDIS_TOKEN}"})
        urllib.request.urlopen(req)
    except Exception as e:
        logging.error(f"Error saving user: {e}")

# --- ذخیره و دریافت فیلم‌ها از دیتابیس ابری ---
def load_movies():
    try:
        url = f"{REDIS_URL}/get/bot_movies"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {REDIS_TOKEN}"})
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            if "result" in res and res["result"]:
                return json.loads(res["result"])
    except Exception as e:
        logging.error(f"Error loading movies: {e}")
    return {}

def save_movies(movies_db):
    try:
        data = json.dumps(movies_db, ensure_ascii=False).encode('utf-8')
        url = f"{REDIS_URL}/set/bot_movies"
        req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {REDIS_TOKEN}"}, method='POST')
        urllib.request.urlopen(req)
    except Exception as e:
        logging.error(f"Error saving movies: {e}")

MOVIES_DB = load_movies()

(GET_TITLE, GET_VIDEO, GET_NEW_ADMIN, 
 REMOVE_ADMIN, DELETE_MOVIE, BROADCAST_MSG, SEARCH_MOVIE) = range(7)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

async def safe_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int):
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

async def post_init(application):
    commands = [
        BotCommand("start", "🏠 منوی اصلی و لیست فیلم‌ها"),
        BotCommand("search", "🔍 جستجوی سریع فیلم")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    if update.message:
        await safe_delete(context, update.message.chat_id, update.message.message_id)
    
    keyboard = []
    for m_id, m_data in MOVIES_DB.items():
        views = m_data.get('views', 0)
        keyboard.append([InlineKeyboardButton(f"🎬 {m_data['title']} ({views} بازدید)", callback_data=f"show_{m_id}")])

    user_tools = [
        InlineKeyboardButton("🔍 جستجوی فیلم", callback_data='search_btn'),
        InlineKeyboardButton("🔥 محبوب‌ترین‌ها", callback_data='top_movies')
    ]
    keyboard.append(user_tools)

    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ پنل مدیریت پیشرفته", callback_data='admin_panel')])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 جستجوی فیلم", callback_data='search_btn')],
        [InlineKeyboardButton("⚙️ پنل مدیریت پیشرفته", callback_data='admin_panel')] if user_id in ADMIN_IDS else []
    ])
    
    msg = "🍿 **به آرشیو اختصاصی فیلم خوش آمدید!**\n\nاز لیست زیر فیلم مورد نظر خود را انتخاب کنید یا از دکمه جستجو استفاده کنید:" if MOVIES_DB else "سلام! هنوز هیچ فیلمی در آرشیو اضافه نشده است."

    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=reply_markup, parse_mode='Markdown')
        
    return ConversationHandler.END

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith('show_'):
        m_id = query.data.replace('show_', '')
        movie = MOVIES_DB.get(m_id)
        if movie:
            movie['views'] = movie.get('views', 0) + 1
            save_movies(MOVIES_DB)
            
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=movie['file_id'],
                caption=f"🎥 **{movie['title']}**\n👁 تعداد بازدید: {movie['views']}\n\n⚠️ *این فایل قفل بوده و قابلیت دانلود یا فوروارد ندارد.*",
                parse_mode='Markdown',
                protect_content=True
            )

    elif query.data == 'top_movies':
        sorted_movies = sorted(MOVIES_DB.items(), key=lambda x: x[1].get('views', 0), reverse=True)[:5]
        if not sorted_movies:
            await query.edit_message_text("هنوز فیلمی ثبت نشده است.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='back_home')]]))
            return
            
        text = "🔥 **پربازدیدترین فیلم‌های آرشیو:**\n\n"
        keyboard = []
        for m_id, m_data in sorted_movies:
            text += f"⭐ {m_data['title']} - {m_data.get('views', 0)} بازدید\n"
            keyboard.append([InlineKeyboardButton(f"🎬 {m_data['title']}", callback_data=f"show_{m_id}")])
            
        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data='back_home')])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'back_home':
        await start(update, context)

    elif query.data == 'admin_panel':
        if user_id not in ADMIN_IDS:
            return
        
        keyboard = [
            [InlineKeyboardButton("➕ افزودن فیلم", callback_data='add_movie'),
             InlineKeyboardButton("❌ حذف فیلم", callback_data='del_movie')],
            [InlineKeyboardButton("👤 افزودن ادمین", callback_data='add_admin'),
             InlineKeyboardButton("🗑 حذف ادمین", callback_data='rem_admin')],
            [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data='broadcast')],
            [InlineKeyboardButton("📊 آمار کامل ربات", callback_data='stats')],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data='back_home')]
        ]
        await query.edit_message_text(
            "🛠 **پنل مدیریت پیشرفته سوپربات**\nلطفاً یک گزینه را انتخاب کنید:", 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )
        return ConversationHandler.END
        
    elif query.data == 'stats':
        if user_id in ADMIN_IDS:
            users_count = len(load_users())
            total_views = sum(m.get('views', 0) for m in MOVIES_DB.values())
            text = f"📊 **آمار جامع سوپربات:**\n\n👥 تعداد کاربران: {users_count}\n🎬 تعداد فیلم‌ها: {len(MOVIES_DB)}\n👁 مجموع کل بازدیدها: {total_views}\n👮‍♂️ تعداد ادمین‌ها: {len(ADMIN_IDS)}"
            keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data='admin_panel')]]
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        keyboard = [[InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data='back_home')]]
        await query.edit_message_text("🔍 لطفاً **قسمتی از نام فیلم** مورد نظر را تایپ و ارسال کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        keyboard = [[InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data='back_home')]]
        await update.message.reply_text("🔍 لطفاً **قسمتی از نام فیلم** مورد نظر را تایپ و ارسال کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SEARCH_MOVIE

async def process_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_delete(context, update.message.chat_id, update.message.message_id)
    search_query = update.message.text.lower().strip()
    
    results = []
    for m_id, m_data in MOVIES_DB.items():
        if search_query in m_data['title'].lower():
            results.append((m_id, m_data))
            
    if results:
        keyboard = []
        text = f"🔎 نتایج جستجو برای «{search_query}»:\n"
        for m_id, m_data in results:
            keyboard.append([InlineKeyboardButton(f"🎬 {m_data['title']}", callback_data=f"show_{m_id}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data='back_home')])
        await context.bot.send_message(chat_id=update.message.chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data='back_home')]]
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ هیچ فیلمی با این نام پیدا نشد.", reply_markup=InlineKeyboardMarkup(keyboard))
        
    return ConversationHandler.END

async def start_add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data='admin_panel')]]
    await query.edit_message_text("لطفاً **عنوان/اسم فیلم** را ارسال کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return GET_TITLE

async def get_movie_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_delete(context, update.message.chat_id, update.message.message_id)
    context.user_data['temp_title'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data='admin_panel')]]
    await context.bot.send_message(
        chat_id=update.message.chat_id,
        text="عالی! حالا **خود ویدیو/فایل فیلم** را بفرستید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GET_VIDEO

async def get_movie_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_delete(context, update.message.chat_id, update.message.message_id)
    video_file_id = update.message.video.file_id
    title = context.user_data['temp_title']
    movie_id = str(len(MOVIES_DB) + 1)
    
    MOVIES_DB[movie_id] = {'title': title, 'file_id': video_file_id, 'views': 0}
    save_movies(MOVIES_DB)
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data='admin_panel')]]
    await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=f"✅ فیلم **{title}** با موفقیت ذخیره و به آرشیو اضافه شد!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def start_del_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not MOVIES_DB:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data='admin_panel')]]
        await query.edit_message_text("هیچ فیلمی برای حذف وجود ندارد.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    
    text = "لیست فیلم‌ها:\n"
    for m_id, m_data in MOVIES_DB.items():
        text += f"کد `{m_id}` -> {m_data['title']}\n"
    text += "\nلطفاً **کد فیلم** مورد نظر جهت حذف را بفرستید:"
    keyboard = [[InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data='admin_panel')]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    return DELETE_MOVIE

async def process_del_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_delete(context, update.message.chat_id, update.message.message_id)
    m_id = update.message.text.strip()
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data='admin_panel')]]
    
    if m_id in MOVIES_DB:
        deleted = MOVIES_DB.pop(m_id)
        save_movies(MOVIES_DB)
        msg = f"✅ فیلم **{deleted['title']}** حذف شد."
    else:
        msg = "❌ کدی که فرستادید معتبر نیست."
        
    await context.bot.send_message(chat_id=update.message.chat_id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data='admin_panel')]]
        await query.edit_message_text("⚠️ فقط ادمین اصلی می‌تواند ادمین جدید اضافه کند.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data='admin_panel')]]
    await query.edit_message_text("لطفاً **آیدی عددی (User ID)** کاربر مورد نظر را بفرستید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return GET_NEW_ADMIN

async def process_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_delete(context, update.message.chat_id, update.message.message_id)
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data='admin_panel')]]
    try:
        new_id = int(update.message.text.strip())
        ADMIN_IDS.add(new_id)
        msg = f"✅ کاربر `{new_id}` با موفقیت ادمین شد."
    except ValueError:
        msg = "❌ آیدی عددی نامعتبر است."
        
    await context.bot.send_message(chat_id=update.message.chat_id, text=msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_rem_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != OWNER_ID:
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data='admin_panel')]]
        await query.edit_message_text("⚠️ فقط ادمین اصلی می‌تواند ادمین‌ها را عزل کند.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data='admin_panel')]]
    await query.edit_message_text("لطفاً **آیدی عددی** ادمینی که می‌خواهید دسترسی‌اش گرفته شود را بفرستید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return REMOVE_ADMIN

async def process_rem_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_delete(context, update.message.chat_id, update.message.message_id)
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data='admin_panel')]]
    try:
        target_id = int(update.message.text.strip())
        if target_id == OWNER_ID:
            msg = "❌ امکان حذف ادمین اصلی وجود ندارد!"
        elif target_id in ADMIN_IDS:
            ADMIN_IDS.remove(target_id)
            msg = f"✅ دسترسی ادمین `{target_id}` گرفته شد."
        else:
            msg = "این کاربر در لیست ادمین‌ها نبود."
    except ValueError:
        msg = "❌ آیدی عددی نامعتبر است."
        
    await context.bot.send_message(chat_id=update.message.chat_id, text=msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data='admin_panel')]]
    await query.edit_message_text("متن پیامی که می‌خواهید برای **همه کاربران** ارسال شود را بفرستید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return BROADCAST_MSG

async def process_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_delete(context, update.message.chat_id, update.message.message_id)
    msg_text = update.message.text
    users = load_users()
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=msg_text)
            count += 1
        except Exception:
            pass
            
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data='admin_panel')]]
    await context.bot.send_message(
        chat_id=update.message.chat_id, 
        text=f"📢 پیام برای {count} کاربر ارسال شد.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END

if __name__ == '__main__':
    threading.Thread(target=run_dummy_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_movie, pattern='^add_movie$'),
            CallbackQueryHandler(start_del_movie, pattern='^del_movie$'),
            CallbackQueryHandler(start_add_admin, pattern='^add_admin$'),
            CallbackQueryHandler(start_rem_admin, pattern='^rem_admin$'),
            CallbackQueryHandler(start_broadcast, pattern='^broadcast$'),
            CallbackQueryHandler(start_search, pattern='^search_btn$'),
            CommandHandler('search', start_search)
        ],
        states={
            GET_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_movie_title),
                CallbackQueryHandler(handle_callback)
            ],
            GET_VIDEO: [
                MessageHandler(filters.VIDEO, get_movie_video),
                CallbackQueryHandler(handle_callback)
            ],
            DELETE_MOVIE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_del_movie),
                CallbackQueryHandler(handle_callback)
            ],
            GET_NEW_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_admin),
                CallbackQueryHandler(handle_callback)
            ],
            REMOVE_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_rem_admin),
                CallbackQueryHandler(handle_callback)
            ],
            BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_broadcast),
                CallbackQueryHandler(handle_callback)
            ],
            SEARCH_MOVIE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_search),
                CallbackQueryHandler(handle_callback)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(handle_callback)
        ],
        per_chat=True,
        per_user=True,
        per_message=False
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()