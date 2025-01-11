import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import speedtest
import asyncio
from datetime import datetime
import os
import statistics
import psutil
from dotenv import load_dotenv

# تحميل المتغيرات البيئية من ملف .env
load_dotenv()

# معرف المجموعة (استبدل بالقيمة الفعلية)
GROUP_ID = os.getenv("GROUP_ID", "-1002341995131")  # يجب أن يكون Group ID عددًا سالبًا
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/+x6RCtclrFpNjMmU0")  # استبدل برابط المجموعة الفعلي

# ملف لتخزين التقييمات وقياسات السرعة
RATINGS_FILE = "ratings.json"
SPEED_TESTS_FILE = "speed_tests.json"

# معايير التقييم
SPEED_CRITERIA = {
    "good": {"download": 50, "upload": 10, "ping": 50},
    "medium": {"download": 20, "upload": 5, "ping": 100}
}

# تقييم سرعة الإنترنت بناءً على النتائج
def evaluate_speed(download_speed, upload_speed, ping):
    if download_speed > SPEED_CRITERIA["good"]["download"] and upload_speed > SPEED_CRITERIA["good"]["upload"] and ping < SPEED_CRITERIA["good"]["ping"]:
        return "جيدة 🟢"
    elif download_speed > SPEED_CRITERIA["medium"]["download"] and upload_speed > SPEED_CRITERIA["medium"]["upload"] and ping < SPEED_CRITERIA["medium"]["ping"]:
        return "متوسطة 🟡"
    else:
        return "ضعيفة 🔴"

# تقييم جودة الاتصال بناءً على البينغ وفقدان الحزم
def evaluate_connection_quality(ping, packet_loss):
    if ping < 50 and packet_loss == 0:
        return "ممتازة 🟢"
    elif ping < 100 and packet_loss < 5:
        return "جيدة 🟡"
    else:
        return "ضعيفة 🔴"

# تحميل التقييمات من الملف
def load_ratings():
    try:
        with open(RATINGS_FILE, "r") as file:
            ratings = json.load(file)
            if "ratings" not in ratings:
                ratings["ratings"] = []
            return ratings
    except FileNotFoundError:
        return {"total_ratings": 0, "sum_ratings": 0, "average": 0, "ratings": []}

# تحميل قياسات السرعة من الملف
def load_speed_tests():
    try:
        with open(SPEED_TESTS_FILE, "r") as file:
            speed_tests = json.load(file)
            if "speed_tests" not in speed_tests:
                speed_tests["speed_tests"] = []
            return speed_tests
    except FileNotFoundError:
        return {"speed_tests": []}

# حفظ التقييمات في الملف
def save_ratings(ratings):
    with open(RATINGS_FILE, "w") as file:
        json.dump(ratings, file, indent=4)

# حفظ قياسات السرعة في الملف
def save_speed_tests(speed_tests):
    with open(SPEED_TESTS_FILE, "w") as file:
        json.dump(speed_tests, file, indent=4)

# تحديث قياسات السرعة
def update_speed_tests(user_id, username, download_speed, upload_speed, ping, packet_loss):
    speed_tests = load_speed_tests()
    speed_tests["speed_tests"].append({
        "user_id": user_id,
        "username": username,
        "download_speed": download_speed,
        "upload_speed": upload_speed,
        "ping": ping,
        "packet_loss": packet_loss,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_speed_tests(speed_tests)

# تحليل البيانات التاريخية
def analyze_speed_tests():
    speed_tests = load_speed_tests()
    if not speed_tests["speed_tests"]:
        return None

    download_speeds = [test["download_speed"] for test in speed_tests["speed_tests"]]
    upload_speeds = [test["upload_speed"] for test in speed_tests["speed_tests"]]
    pings = [test["ping"] for test in speed_tests["speed_tests"]]

    analysis = {
        "average_download": statistics.mean(download_speeds),
        "average_upload": statistics.mean(upload_speeds),
        "average_ping": statistics.mean(pings),
        "best_download": max(download_speeds),
        "worst_download": min(download_speeds),
        "best_upload": max(upload_speeds),
        "worst_upload": min(upload_speeds),
        "best_ping": min(pings),
        "worst_ping": max(pings)
    }
    return analysis

# التحقق من اشتراك المستخدم في المجموعة
async def is_user_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Error checking membership: {e}")
        return False

# تحديد لون الشريط بناءً على النسبة المئوية
def get_progress_bar_color(progress):
    if progress < 33:
        return "🔴"  # أحمر
    elif progress < 66:
        return "🟡"  # أصفر
    else:
        return "🟢"  # أخضر

# تحديث شريط التقدم بناءً على المرحلة
async def update_progress(chat_id, context, message_id, progress, stage):
    bar = "[" + "█" * (progress // 10) + " " * (10 - (progress // 10)) + "]"
    color = get_progress_bar_color(progress)
    stages = {
        0: "🔍 <b>اختيار أفضل خادم...</b>",
        1: "📥 <b>قياس سرعة التحميل...</b>",
        2: "📤 <b>قياس سرعة الرفع...</b>",
        3: "✅ <b>الانتهاء من القياس!</b>"
    }
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=f"{stages[stage]}\n<code>{bar} {progress}%</code> {color}",
        parse_mode="HTML"
    )
    await asyncio.sleep(1)  # تأخير لمدة ثانية بين التحديثات

# الحصول على معلومات IP ونوع الاتصال
def get_network_info():
    st = speedtest.Speedtest()
    ip = st.get_best_server()["host"]
    connection_type = get_connection_type()
    return ip, connection_type

# تحديد نوع الاتصال
def get_connection_type():
    interfaces = psutil.net_if_addrs()
    for interface, addresses in interfaces.items():
        if "wlan" in interface.lower() or "wi-fi" in interface.lower():
            return "Wi-Fi"
        elif "cellular" in interface.lower() or "mobile" in interface.lower():
            return "Cellular"
    return "Unknown"

# التحقق مما إذا كان المستخدم قد قام بالتقييم مسبقًا
def has_user_rated(user_id, ratings):
    for rating in ratings["ratings"]:
        if rating["user_id"] == user_id:
            return True
    return False

# تحديث التقييمات
def update_rating(user_id, username, new_rating):
    ratings = load_ratings()
    
    # التحقق مما إذا كان المستخدم قد قام بالتقييم مسبقًا
    if has_user_rated(user_id, ratings):
        return False  # المستخدم قام بالتقييم مسبقًا
    
    ratings["total_ratings"] += 1
    ratings["sum_ratings"] += new_rating
    ratings["average"] = ratings["sum_ratings"] / ratings["total_ratings"]
    
    # إضافة التقييم الجديد مع معلومات المستخدم
    ratings["ratings"].append({
        "user_id": user_id,
        "username": username,
        "rating": new_rating,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    save_ratings(ratings)
    return True  # التقييم تم تسجيله بنجاح

# أمر /start مع زر تفاعلي
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "زائر"

    if not await is_user_member(user_id, context):
        await update.message.reply_html(
            f"🌟 <b>مرحبًا {username}!</b> 🌟\n\n"
            f"🚫 <b>عذرًا، يجب عليك الانضمام إلى مجموعتنا أولاً لاستخدام البوت.</b>\n\n"
            f"👉 <a href='{GROUP_LINK}'>انضم إلى المجموعة هنا</a>\n\n"
            "بعد الانضمام، اضغط على /start مرة أخرى."
        )
        return

    welcome_message = (
        f"🌟 <b>مرحبًا {username}!</b> 🌟\n\n"
        f"🆔 <b>معرفك:</b> <code>{user_id}</code>\n\n"
        "⚡ <b>مرحبًا بك في بوت قياس سرعة الإنترنت!</b> ⚡\n\n"
        "يمكنك استخدام الزر أدناه لقياس سرعة الإنترنت بسهولة وسرعة.\n\n"
        "🚀 <b>مميزات البوت:</b>\n"
        "✅ قياس سرعة التحميل والرفع.\n"
        "✅ قياس جودة الاتصال.\n"
        "✅ تحليل البيانات التاريخية.\n"
        "✅ واجهة تفاعلية وسهلة الاستخدام.\n\n"
        "👇 اضغط على الزر أدناه للبدء:"
    )

    keyboard = [
        [InlineKeyboardButton("🚀 قياس سرعة الإنترنت", callback_data='speedtest')],
        [InlineKeyboardButton("📊 تحليل البيانات", callback_data='analyze_data')],
        [InlineKeyboardButton("⭐ تقييم البوت", callback_data='rate_bot')],
        [InlineKeyboardButton("🚩 الإبلاغ عن مشكلة", callback_data='report_issue')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(welcome_message, reply_markup=reply_markup)

# معالجة الضغط على الزر التفاعلي
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'back_to_main':
        keyboard = [
            [InlineKeyboardButton("🚀 قياس سرعة الإنترنت", callback_data='speedtest')],
            [InlineKeyboardButton("📊 تحليل البيانات", callback_data='analyze_data')],
            [InlineKeyboardButton("⭐ تقييم البوت", callback_data='rate_bot')],
            [InlineKeyboardButton("🚩 الإبلاغ عن مشكلة", callback_data='report_issue')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="القائمة الرئيسية - ماذا تريد أن تفعل؟",
            reply_markup=reply_markup
        )
        return

    if query.data == 'speedtest':
        # قياس سرعة الإنترنت
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        progress_message = await query.edit_message_text("🔍 <b>اختيار أفضل خادم...</b>\n<code>[          ] 0%</code> 🔴", parse_mode="HTML")

        st = speedtest.Speedtest()
        ip, connection_type = get_network_info()

        await update_progress(query.message.chat_id, context, progress_message.message_id, 10, 0)
        st.get_best_server()

        await update_progress(query.message.chat_id, context, progress_message.message_id, 40, 1)
        download_speed = st.download() / 1_000_000

        await update_progress(query.message.chat_id, context, progress_message.message_id, 70, 2)
        upload_speed = st.upload() / 1_000_000

        await update_progress(query.message.chat_id, context, progress_message.message_id, 100, 3)
        ping = st.results.ping
        packet_loss = 0  # يمكن استبدالها بقيمة فعلية إذا كانت متاحة

        evaluation = evaluate_speed(download_speed, upload_speed, ping)
        quality_evaluation = evaluate_connection_quality(ping, packet_loss)

        result_message = (
            "✅ <b>تم قياس سرعة الإنترنت بنجاح:</b>\n\n"
            f"📅 <b>وقت القياس:</b> <code>{start_time}</code>\n\n"
            f"🌐 <b>عنوان IP:</b> <code>{ip}</code>\n"
            f"📶 <b>نوع الاتصال:</b> <code>{connection_type}</code>\n\n"
            f"📥 <b>سرعة التحميل:</b> <code>{download_speed:.2f} Mbps</code>\n"
            f"📤 <b>سرعة الرفع:</b> <code>{upload_speed:.2f} Mbps</code>\n"
            f"⏱ <b>البينغ:</b> <code>{ping:.2f} ms</code>\n"
            f"📦 <b>فقدان الحزم (Packet Loss):</b> <code>{packet_loss}%</code>\n\n"
            f"<b>تقييم السرعة:</b> {evaluation}\n"
            f"<b>تقييم جودة الاتصال:</b> {quality_evaluation}"
        )

        keyboard = [
            [InlineKeyboardButton("🔄 إعادة القياس", callback_data='speedtest')],
            [InlineKeyboardButton("الرجوع للرئيسية 🏠", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(result_message, reply_markup=reply_markup, parse_mode="HTML")

        # إرسال النتيجة إلى المجموعة
        user = query.from_user
        group_message = (
            f"📊 <b>تم قياس سرعة الإنترنت بواسطة:</b> @{user.username}\n\n"
            f"📅 <b>وقت القياس:</b> <code>{start_time}</code>\n\n"
            f"📶 <b>نوع الاتصال:</b> <code>{connection_type}</code>\n\n"
            f"📥 <b>سرعة التحميل:</b> <code>{download_speed:.2f} Mbps</code>\n"
            f"📤 <b>سرعة الرفع:</b> <code>{upload_speed:.2f} Mbps</code>\n"
            f"⏱ <b>البينغ:</b> <code>{ping:.2f} ms</code>\n"
            f"📦 <b>فقدان الحزم (Packet Loss):</b> <code>{packet_loss}%</code>\n\n"
            f"<b>تقييم السرعة:</b> {evaluation}\n"
            f"<b>تقييم جودة الاتصال:</b> {quality_evaluation}"
        )
        await context.bot.send_message(chat_id=GROUP_ID, text=group_message, parse_mode="HTML")

        # تحديث قياسات السرعة
        update_speed_tests(user.id, user.username, download_speed, upload_speed, ping, packet_loss)
    elif query.data == 'analyze_data':
        analysis = analyze_speed_tests()
        if not analysis:
            keyboard = [[InlineKeyboardButton("الرجوع للرئيسية 🏠", callback_data='back_to_main')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "⚠️ <b>لا توجد بيانات متاحة للتحليل!</b>",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return

        analysis_message = (
            "📊 <b>تحليل البيانات التاريخية:</b>\n\n"
            f"📥 <b>متوسط سرعة التحميل:</b> <code>{analysis['average_download']:.2f} Mbps</code>\n"
            f"📤 <b>متوسط سرعة الرفع:</b> <code>{analysis['average_upload']:.2f} Mbps</code>\n"
            f"⏱ <b>متوسط البينغ:</b> <code>{analysis['average_ping']:.2f} ms</code>\n\n"
            f"🚀 <b>أفضل سرعة تحميل:</b> <code>{analysis['best_download']:.2f} Mbps</code>\n"
            f"🐌 <b>أسوأ سرعة تحميل:</b> <code>{analysis['worst_download']:.2f} Mbps</code>\n\n"
            f"🚀 <b>أفضل سرعة رفع:</b> <code>{analysis['best_upload']:.2f} Mbps</code>\n"
            f"🐌 <b>أسوأ سرعة رفع:</b> <code>{analysis['worst_upload']:.2f} Mbps</code>\n\n"
            f"⏱ <b>أفضل بينغ:</b> <code>{analysis['best_ping']:.2f} ms</code>\n"
            f"⏱ <b>أسوأ بينغ:</b> <code>{analysis['worst_ping']:.2f} ms</code>"
        )
        keyboard = [[InlineKeyboardButton("الرجوع للرئيسية 🏠", callback_data='back_to_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            analysis_message,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    elif query.data == 'rate_bot':
        user = query.from_user
        ratings = load_ratings()
        
        # التحقق مما إذا كان المستخدم قد قام بالتقييم مسبقًا
        if has_user_rated(user.id, ratings):
            await query.edit_message_text("⚠️ <b>لقد قمت بالتقييم مسبقًا!</b>\n\nيمكنك التقييم مرة واحدة فقط.", parse_mode="HTML")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("1⭐", callback_data='rating_1'),
                InlineKeyboardButton("2⭐", callback_data='rating_2'),
                InlineKeyboardButton("3⭐", callback_data='rating_3'),
                InlineKeyboardButton("4⭐", callback_data='rating_4'),
                InlineKeyboardButton("5⭐", callback_data='rating_5')
            ],
            [InlineKeyboardButton("الرجوع للرئيسية 🏠", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="كيف تقيم البوت؟",
            reply_markup=reply_markup
        )
    elif query.data.startswith('rating_'):
        rating = int(query.data.split('_')[1])
        user = query.from_user
        if update_rating(user.id, user.username, rating):
            ratings = load_ratings()
            keyboard = [[InlineKeyboardButton("الرجوع للرئيسية 🏠", callback_data='back_to_main')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"شكرًا لتقييمك! ⭐️\n\n"
                     f"متوسط التقييمات: {ratings['average']:.1f}/5\n"
                     f"عدد التقييمات: {ratings['total_ratings']}",
                reply_markup=reply_markup
            )
        else:
            keyboard = [[InlineKeyboardButton("الرجوع للرئيسية 🏠", callback_data='back_to_main')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text="⚠️ <b>لقد قمت بالتقييم مسبقًا!</b>\n\nيمكنك التقييم مرة واحدة فقط.",
                reply_markup=reply_markup
            )
    elif query.data == 'report_issue':
        keyboard = [[InlineKeyboardButton("الرجوع للرئيسية 🏠", callback_data='back_to_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🚩 <b>الإبلاغ عن مشكلة</b>\n\n"
            "يرجى وصف المشكلة التي تواجهها أو الضغط على زر الرجوع للرئيسية:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        context.user_data["awaiting_report"] = True

# معالجة الرسائل النصية للإبلاغ عن المشاكل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting_report"):
        issue_description = update.message.text
        if len(issue_description.strip()) < 10:
            await update.message.reply_text("⚠️ <b>الوصف قصير جدًا!</b>\n\nيرجى تقديم وصف أكثر تفصيلاً للمشكلة.", parse_mode="HTML")
            return
        user = update.message.from_user
        report_message = (
            f"🚩 <b>تم الإبلاغ عن مشكلة جديدة:</b>\n\n"
            f"👤 <b>المستخدم:</b> @{user.username}\n"
            f"🆔 <b>المعرف:</b> <code>{user.id}</code>\n\n"
            f"📄 <b>وصف المشكلة:</b>\n{issue_description}"
        )
        await context.bot.send_message(chat_id=GROUP_ID, text=report_message, parse_mode="HTML")
        await update.message.reply_text("شكرًا على إبلاغك! سنقوم بمراجعة المشكلة قريبًا.")
        context.user_data["awaiting_report"] = False

async def main():
    # تهيئة البوت
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("Error: BOT_TOKEN not found in environment variables")
        return

    # إنشاء تطبيق البوت
    application = Application.builder().token(bot_token).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء البوت
    print("Bot started...")
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    asyncio.run(main())