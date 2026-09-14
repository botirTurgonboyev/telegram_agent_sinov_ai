import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment o'zgaruvchilarini olish
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")        # Masalan: @kanal_nomi yoki -100...
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # Masalan: 123456789

# --- AVTOMATIK VAZIFALAR (SCHEDULER) ---

async def post_ai_news_to_channel(context: ContextTypes.DEFAULT_TYPE):
    """Kanalga avto-post yuborish funksiyasi"""
    if CHANNEL_ID:
        text = "🤖 **AI Agent Yangiliklari**\n\nBugungi kunda sun'iy intellekt sohasi jadal rivojlanmoqda. Biz bilan kuzatib boring!"
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
        logging.info("Kanalga avto-post yuborildi.")

async def daily_supervisor_check(context: ContextTypes.DEFAULT_TYPE):
    """Har kuni soat 21:00 da adminga nazorat xabarini yuborish"""
    if ADMIN_CHAT_ID:
        text = f"⚙️ **Tizim Nazorati**\n\nBot muvaffaqiyatli ishlamoqda!\nVaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="Markdown")
        logging.info("Adminga nazorat xabari yuborildi.")


# --- HANDLERLAR (BOT BUYRUQLARI VA XABARLAR) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start buyrug'iga javob qaytarish"""
    user_name = update.effective_user.first_name
    reply_text = f"Salom, {user_name}! Men Botirga yordam beruvchi AI Agentman. Menga savolingizni yuborishingiz mumkin."
    await update.message.reply_text(reply_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Oddiy matnli xabarlarga javob qaytarish"""
    user_text = update.message.text
    # Bu yerga OpenAI yoki boshqa AI mantiqini ulashingiz mumkin
    reply_text = f"Sizning xabaringiz qabul qilindi: '{user_text}'"
    await update.message.reply_text(reply_text)


# --- ASOSIY ISHGA TUSHIRISH QISMI ---

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN ortam o'zgaruvchisi topilmadi!")

    # Application yaratish
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Buyruq va xabar ishlovchilarini qo'shish
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # AsyncIOScheduler sozlash (v20+ bilan mos ishlaydi)
    scheduler = AsyncIOScheduler()
    
    # 1. Har 3 kunda 1 marta kanalga avto-post joylash
    scheduler.add_job(
        post_ai_news_to_channel,
        'interval',
        days=3,
        args=[app]
    )
    
    # 2. Har kuni soat 21:00 da adminga nazorat xabarini yuborish
    scheduler.add_job(
        daily_supervisor_check,
        'cron',
        hour=21,
        minute=0,
        args=[app]
    )
    
    scheduler.start()

    logging.info("AI Agent bot muvaffaqiyatli ishga tushdi...")

    # Botni ishga tushirish (Long Polling)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()