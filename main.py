import logging
import json
import os
import time
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ---------------- وب‌سرور برای نگه داشتن ربات در Render ----------------
app_web = Flask('')

@app_web.route('/')
def home():
    return "Bot is alive and secure!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ---------------- تنظیمات امنیتی و اصلی ----------------
# دریافت توکن و آیدی ادمین از متغیرهای محیطی یا مقادیر پیش‌فرض
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8934125933:AAF2dD4FpUY_09YSUqoI3MPreHaaNB5g4bc")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 7474072387))

DATA_FILE = "settings.json"

# پسوندهای خطرناک ممنوعه برای جلوگیری از ورود ویروس
DANGEROUS_EXTENSIONS = [
    '.exe', '.bat', '.cmd', '.sh', '.php', '.pl', '.cgi', 
    '.js', '.vbs', '.py', '.scr', '.pif', '.application', '.gadget'
]

# سیستم آنتی اسپم (حافظه موقت زمان ارسال پیام کاربران)
USER_LAST_MESSAGE_TIME = {}
SPAM_THRESHOLD = 1.2  # حداقل فاصله زمانی بین دو پیام (ثانیه)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---------------- مدیریت دیتابیس ----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "force_join_enabled": True,
            "channels": [],
            "tickets": {},
            "ticket_counter": 1,
            "movies": {},
            "users": []  # ذخیره آیدی تمام کاربران برای ارسال همگانی
        }
        save_data(default_data)
        return default_data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if "tickets" not in data: data["tickets"] = {}
        if "ticket_counter" not in data: data["ticket_counter"] = 1
        if "movies" not in data: data["movies"] = {}
        if "users" not in data: data["users"] = []
        return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def register_user(user_id: int):
    data = load_data()
    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)

# ---------------- بررسی آنتی‌اسپم ----------------
def is_spamming(user_id: int) -> bool:
    current_time = time.time()
    last_time = USER_LAST_MESSAGE_TIME.get(user_id, 0)
    USER_LAST_MESSAGE_TIME[user_id] = current_time
    return (current_time - last_time) < SPAM_THRESHOLD

# ---------------- بررسی قفل کانال‌ها ----------------
async def check_user_subscriptions(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    data = load_data()
    if not data.get("force_join_enabled", True):
        return True, []

    not_joined = []
    for channel in data.get("channels", []):
        try:
            member = await context.bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(channel)
        except Exception:
            not_joined.append(channel)

    return (len(not_joined) == 0), not_joined

async def show_force_join_msg(update: Update, context: ContextTypes.DEFAULT_TYPE, not_joined_channels: list):
    keyboard = []
    for ch in not_joined_channels:
        keyboard.append([InlineKeyboardButton(f"📢 عضویت در کانال @{ch}", url=f"https://t.me/{ch}")])
    
    keyboard.append([InlineKeyboardButton("✅ عضو شدم / بررسی مجدد", callback_data="check_join_again")])
    text = "❤️ **برای استفاده از ربات، لطفاً ابتدا در کانال‌های زیر عضو شوید:**"
    
    if update.message:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ---------------- کیبورد اصلی ----------------
def get_main_keyboard(user_id: int):
    keyboard = [
        [KeyboardButton("📜 مشاهده لیست فیلم‌ها"), KeyboardButton("🔍 جستجوی فیلم")],
        [KeyboardButton("📞 پشتیبانی / ارسال تیکت")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton("⚙️ پنل مدیریت")])
        
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ---------------- دستور /start ----------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    if is_spamming(user_id):
        return

    is_joined, not_joined = await check_user_subscriptions(context, user_id)
    if not is_joined:
        await show_force_join_msg(update, context, not_joined)
        return

    reply_markup = get_main_keyboard(user_id)
    await update.message.reply_text(
        "🎬 **به آرشیو رایگان فیلم خوش آمدید!**\nاز کیبورد پایین گزینه مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ---------------- پنل مدیریت ارتقایافته ----------------
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    data = load_data()
    status_str = "🟢 فعال" if data.get("force_join_enabled", True) else "🔴 غیرفعال"
    channels_list = "\n".join([f"• @{ch}" for ch in data.get("channels", [])]) or "هیچ کانالی ثبت نشده"
    
    open_tickets = [t for t in data["tickets"].values() if t["status"] == "open"]
    ticket_count = len(open_tickets)
    user_count = len(data.get("users", []))
    movie_count = len(data.get("movies", {}))

    text = (
        f"⚙️ **پنل مدیریت پیشرفته و امن**\n\n"
        f"📊 **آمار کل:**\n"
        f"• تعداد کاربران: **{user_count} نفر**\n"
        f"• تعداد فیلم‌ها: **{movie_count} عدد**\n"
        f"• تیکت‌های باز: **{ticket_count} عدد**\n\n"
        f"🔒 وضعیت قفل عضویت: **{status_str}**\n\n"
        f"📋 **کانال‌های قفل:**\n{channels_list}"
    )

    toggle_btn_text = "🔴 غیرفعال‌سازی قفل" if data.get("force_join_enabled", True) else "🟢 فعال‌سازی قفل"
    
    keyboard = [
        [InlineKeyboardButton("➕ افزودن فیلم جدید", callback_data="admin_add_movie")],
        [InlineKeyboardButton(f"📩 مشاهده تیکت‌ها ({ticket_count})", callback_data="admin_view_tickets")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی (Broadcast)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(toggle_btn_text, callback_data="admin_toggle_lock")],
        [InlineKeyboardButton("➕ افزودن کانال", callback_data="admin_add_channel"),
         InlineKeyboardButton("➖ حذف کانال", callback_data="admin_del_channel")]
    ]

    query = update.callback_query
    if query:
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ---------------- پردازش پیام‌های متنی و امنیت فایل ----------------
async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)

    # سیستم آنتی اسپم
    if is_spamming(user_id):
        await update.message.reply_text("⚠️ **لطفاً کمی آرام‌تر پیام بفرستید!** (جلوگیری از اسپم)")
        return

    text = update.message.text.strip() if update.message.text else ""
    user_data = context.user_data

    # بررسی قفل کانال‌ها
    is_joined, not_joined = await check_user_subscriptions(context, user_id)
    if not is_joined:
        await show_force_join_msg(update, context, not_joined)
        return

    # ۱. دریافت پیام تیکت
    if user_data.get("state") == "waiting_for_ticket":
        config_data = load_data()
        t_id = str(config_data["ticket_counter"])
        config_data["ticket_counter"] += 1
        
        user_name = update.effective_user.first_name or "کاربر"
        config_data["tickets"][t_id] = {
            "user_id": user_id,
            "user_name": user_name,
            "text": text,
            "status": "open"
        }
        save_data(config_data)
        user_data["state"] = None
        
        await update.message.reply_text(f"✅ **تیکت شما با موفقیت ثبت شد (کد تیکت: #{t_id})**", parse_mode="Markdown")
        try:
            await context.bot.send_message(ADMIN_ID, f"📩 **تیکت جدید (#{t_id})**\nاز طرف: {user_name}\nمتن: {text}")
        except Exception: pass
        return

    # ۲. پاسخ ادمین به تیکت
    if user_id == ADMIN_ID and user_data.get("state") == "answering_ticket":
        target_ticket_id = user_data.get("target_ticket_id")
        config_data = load_data()
        ticket = config_data["tickets"].get(target_ticket_id)

        if ticket and ticket["status"] == "open":
            ticket["status"] = "closed"
            save_data(config_data)
            try:
                await context.bot.send_message(ticket["user_id"], f"📩 **پاسخ پشتیبانی به تیکت #{target_ticket_id}:**\n\n{text}", parse_mode="Markdown")
                await update.message.reply_text(f"✅ پاسخ ارسال شد و تیکت #{target_ticket_id} بسته شد.")
            except Exception as e:
                await update.message.reply_text(f"❌ خطا در ارسال: {e}")

        user_data["state"] = None
        user_data["target_ticket_id"] = None
        await show_admin_panel(update, context)
        return

    # ۳. مراحل افزودن فیلم جدید توسط ادمین
    if user_id == ADMIN_ID and user_data.get("state") == "add_movie_name":
        user_data["temp_movie_name"] = text
        user_data["state"] = "add_movie_info"
        await update.message.reply_text("📝 **توضیحات یا خلاصه‌داستان فیلم را وارد کنید:**")
        return

    elif user_id == ADMIN_ID and user_data.get("state") == "add_movie_info":
        user_data["temp_movie_info"] = text
        user_data["state"] = "add_movie_link"
        await update.message.reply_text("🔗 **لینک دانلود یا فایل کیفیت فیلم را بفرستید:**")
        return

    elif user_id == ADMIN_ID and user_data.get("state") == "add_movie_link":
        m_name = user_data.get("temp_movie_name")
        m_info = user_data.get("temp_movie_info")
        
        config_data = load_data()
        config_data["movies"][m_name] = {
            "info": m_info,
            "download_link": text
        }
        save_data(config_data)
        user_data["state"] = None
        await update.message.reply_text(f"✅ فیلم **{m_name}** با موفقیت اضافه شد!", parse_mode="Markdown")
        await show_admin_panel(update, context)
        return

    # ۴. ارسال پیام همگانی توسط ادمین
    if user_id == ADMIN_ID and user_data.get("state") == "waiting_for_broadcast":
        config_data = load_data()
        all_users = config_data.get("users", [])
        sent_count = 0
        
        await update.message.reply_text("⏳ در حال ارسال پیام به تمام کاربران...")
        for uid in all_users:
            try:
                await context.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
                sent_count += 1
            except Exception:
                pass

        user_data["state"] = None
        await update.message.reply_text(f"📢 **پیام همگانی با موفقیت به {sent_count} کاربر ارسال شد.**", parse_mode="Markdown")
        await show_admin_panel(update, context)
        return

    # ۵. دکمه‌های اصلی کیبورد
    if text == "📜 مشاهده لیست فیلم‌ها":
        config_data = load_data()
        movies = config_data.get("movies", {})
        if not movies:
            await update.message.reply_text("📜 هنوز هیچ فیلمی ثبت نشده است.")
            return
        
        keyboard = []
        for m_title in movies.keys():
            keyboard.append([InlineKeyboardButton(f"🎬 {m_title}", callback_data=f"show_m_{m_title}")])
        await update.message.reply_text("📋 **لیست فیلم‌های موجود:**\nیک مورد را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    elif text == "🔍 جستجوی فیلم":
        user_data["state"] = "searching_movie"
        await update.message.reply_text("🔎 **نام فیلم مورد نظر خود را بنویسید:**")
        return

    elif user_data.get("state") == "searching_movie":
        user_data["state"] = None
        config_data = load_data()
        movies = config_data.get("movies", {})
        results = [m for m in movies.keys() if text.lower() in m.lower()]
        
        if results:
            keyboard = [[InlineKeyboardButton(f"🎬 {m}", callback_data=f"show_m_{m}")] for m in results]
            await update.message.reply_text("🎉 **نتایج یافت‌شده:**", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("❌ متأسفانه فیلمی با این نام یافت نشد.")
        return

    elif text == "📞 پشتیبانی / ارسال تیکت":
        user_data["state"] = "waiting_for_ticket"
        await update.message.reply_text("✍️ **لطفاً متن سوال یا مشکل خود را بفرستید:**", parse_mode="Markdown")
        return

    elif text == "⚙️ پنل مدیریت" and user_id == ADMIN_ID:
        await show_admin_panel(update, context)
        return

    # ۶. مدیریت افزودن/حذف کانال‌ها
    if user_id == ADMIN_ID and user_data.get("awaiting_input"):
        state = user_data.get("awaiting_input")
        clean_ch = text.replace("@", "")
        config_data = load_data()

        if state == "add_channel":
            if clean_ch not in config_data["channels"]:
                config_data["channels"].append(clean_ch)
                save_data(config_data)
                await update.message.reply_text(f"✅ کانال @{clean_ch} اضافه شد.")
        elif state == "del_channel":
            if clean_ch in config_data["channels"]:
                config_data["channels"].remove(clean_ch)
                save_data(config_data)
                await update.message.reply_text(f"❌ کانال @{clean_ch} حذف شد.")

        user_data["awaiting_input"] = None
        await show_admin_panel(update, context)
        return

    await update.message.reply_text("متوجه نشدم! لطفاً از دکمه‌های کیبورد پایین استفاده کنید.")

# ---------------- آنتی ویروس و فیلتر فایل‌های آلوده ----------------
async def handle_documents_security(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document

    if doc:
        file_name = doc.file_name.lower()
        # بررسی پسوندهای خطرناک ویروسی
        for ext in DANGEROUS_EXTENSIONS:
            if file_name.endswith(ext):
                await update.message.reply_text(
                    "🚨 **هشدار امنیتی:**\n"
                    "ارسال فایل‌های اجرایی و مشکوک ممنوع است! فایل شما توسط سیستم امنیتی بلوکه شد.",
                    parse_mode="Markdown"
                )
                logging.warning(f"SECURITY ALERT: Blocked suspicious file '{file_name}' from user {user_id}")
                return

# ---------------- پردازش دکمه‌های شیشه‌ای ----------------
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if is_spamming(user_id):
        await query.answer("لطفاً کمی صبر کنید...", show_alert=True)
        return

    if data == "check_join_again":
        is_joined, not_joined = await check_user_subscriptions(context, user_id)
        if is_joined:
            await query.answer("✅ عضویت تایید شد!")
            await query.message.delete()
            await context.bot.send_message(user_id, "🎬 **خوش آمدید!**", reply_markup=get_main_keyboard(user_id))
        else:
            await query.answer("❌ هنوز در تمام کانال‌ها عضو نشده‌اید!", show_alert=True)

    elif data.startswith("show_m_"):
        movie_title = data.replace("show_m_", "")
        config_data = load_data()
        movie = config_data.get("movies", {}).get(movie_title)
        
        if movie:
            text = f"🎬 **{movie_title}**\n\n📝 {movie['info']}\n\n📥 **لینک دانلود:**\n{movie['download_link']}"
            await query.edit_message_text(text=text, parse_mode="Markdown")
        else:
            await query.answer("فیلم یافت نشد!")

    elif user_id == ADMIN_ID:
        config_data = load_data()

        if data == "admin_add_movie":
            context.user_data["state"] = "add_movie_name"
            await query.edit_message_text("✏️ **لطفاً نام فیلم جدید را وارد کنید:**")

        elif data == "admin_broadcast":
            context.user_data["state"] = "waiting_for_broadcast"
            await query.edit_message_text("📢 **لطفاً پیامی که می‌خواهید برای همه ارسال شود را تایپ کنید:**")

        elif data == "admin_view_tickets":
            open_tickets = {tid: t for tid, t in config_data["tickets"].items() if t["status"] == "open"}
            if not open_tickets:
                await query.answer("هیچ تیکت بازی وجود ندارد!", show_alert=True)
                return

            keyboard = [[InlineKeyboardButton(f"📩 تیکت #{tid} - {t['user_name']}", callback_data=f"admin_reply_t_{tid}")] for tid, t in open_tickets.items()]
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back")])
            await query.edit_message_text("📋 **لیست تیکت‌های باز:**", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("admin_reply_t_"):
            ticket_id = data.replace("admin_reply_t_", "")
            ticket = config_data["tickets"].get(ticket_id)
            if ticket:
                context.user_data["state"] = "answering_ticket"
                context.user_data["target_ticket_id"] = ticket_id
                await query.edit_message_text(f"📩 **پاسخ به تیکت #{ticket_id}**\nمتن: {ticket['text']}\n\n👇 **پاسخ را بنویسید:**", parse_mode="Markdown")

        elif data == "admin_back":
            await show_admin_panel(update, context)

        elif data == "admin_toggle_lock":
            config_data["force_join_enabled"] = not config_data.get("force_join_enabled", True)
            save_data(config_data)
            await show_admin_panel(update, context)

        elif data == "admin_add_channel":
            context.user_data["awaiting_input"] = "add_channel"
            await query.edit_message_text("✏️ آیدی کانال را **بدون @** بفرستید:")

        elif data == "admin_del_channel":
            context.user_data["awaiting_input"] = "del_channel"
            await query.edit_message_text("✏️ آیدی کانال برای حذف را بفرستید:")

if __name__ == '__main__':
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("panel", show_admin_panel))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    # فیلتر امنیتی فایل‌ها و آنتی‌ویروس
    app.add_handler(MessageHandler(filters.Document.ALL, handle_documents_security))
    
    # پیام‌های متنی
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    print("Bot is running securely...")
    app.run_polling()