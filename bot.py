import os
import io
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import matplotlib
matplotlib.use('Agg') # Serverda grafik UI'siz ishlashi uchun
import matplotlib.pyplot as plt

from docx import Document
from pypdf import PdfReader
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0.7)

# Oddiy xotira uchun in-memory moliya va rejalar strukturasi
user_finance = {"income": 0, "expense": 0, "savings_goal": 10000000, "history": []}
user_tasks = []

# ==========================================
# MODUL 1: AUTO-POSTER (Data Bilim kanali)
# ==========================================
async def post_ai_news_to_channel(bot):
    """Har 3 kunda AI yangiliklarini izlab, o'zbek tilida kanalga post joylaydi."""
    logging.info("Kanal uchun AI post yaratilmoqda...")
    prompt = (
        "Siz Data Science va AI sohasi bo'yicha ekspert va kontent meykersiz. "
        "Sun'iy intellekt sohasidagi eng so'nggi va dolzarb yangiliklar, vositalar yoki "
        "trendlar haqida 'Data Bilim' Telegram kanali uchun jozibador, professional va "
        "o'zbek tilida post tayyorlang. Postda kirish, asosiy mazmun, xulosa va 3-4 ta hashtag bo'lsin."
    )
    try:
        response = await llm.ainvoke(prompt)
        post_content = response.content
        await bot.send_message(chat_id=CHANNEL_ID, text=post_content)
        logging.info("Kanalga post muvaffaqiyatli joylandi.")
    except Exception as e:
        logging.error(f"Kanalga post joylashda xatolik: {e}")

# ==========================================
# MODUL 2: PERSONAL SUPERVISOR (Rejalar va Nazorat)
# ==========================================
async def daily_supervisor_check(bot):
    """Kunlik rejalarni bajarilganini so'rab hisobot oladi."""
    if not ADMIN_CHAT_ID:
        return
    
    msg = (
        "👋 Xayrli kech! Kunlik nazorat vaqti bo'ldi.\n\n"
        "Bugungi dars qilish, kitob o'qish, uchrashuvlar hamda kunlik daromad/xarajatlaringiz "
        "bajarildimi? Hisobotingizni qisqa yozib yuboring!"
    )
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)

# ==========================================
# MODUL 3: FILE & VISION OCR ANALYZER
# ==========================================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """PDF va DOCX fayllarni o'qib, tahlil beradi."""
    doc = update.message.document
    file_name = doc.file_name.lower()
    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()

    extracted_text = ""
    
    if file_name.endswith(".pdf"):
        pdf_reader = PdfReader(io.BytesIO(file_bytes))
        for page in pdf_reader.pages:
            extracted_text += page.extract_text() or ""
    elif file_name.endswith(".docx"):
        docx_file = Document(io.BytesIO(file_bytes))
        extracted_text = "\n".join([p.text for p in docx_file.paragraphs])
    else:
        await update.message.reply_text("Faqat PDF va DOCX fayllarini qabul qila olaman.")
        return

    if not extracted_text.strip():
        await update.message.reply_text("Fayl matnini o'qib bo'lmadi.")
        return

    await update.message.reply_text("📄 Fayl o'rganib chiqilmoqda, kuting...")
    
    prompt = f"Ushbu hujjat matnini tahlil qiling va uning qisqacha mazmunini ile muhim nuqtalarini o'zbek tilida tushuntirib bering:\n\n{extracted_text[:4000]}"
    response = await llm.ainvoke(prompt)
    await update.message.reply_text(response.content)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rasmlarni Vision API orqali tahlil qiladi."""
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    photo_url = file.file_path

    await update.message.reply_text("🖼 Rasm tahlil qilinmoqda...")

    message = HumanMessage(
        content=[
            {"type": "text", "text": "Ushbu rasmda nima tasvirlangan va undagi muhim ma'lumotlarni o'zbek tilida tushuntirib bering."},
            {"type": "image_url", "image_url": {"url": photo_url}}
        ]
    )
    
    try:
        response = await llm.ainvoke([message])
        await update.message.reply_text(response.content)
    except Exception as e:
        logging.error(f"Rasm tahlilida xatolik: {e}")
        await update.message.reply_text("Rasmni tahlil qilishda xatolik yuz berdi.")

# ==========================================
# MODUL 4: FINANCE & CHART MANAGER
# ==========================================
async def generate_finance_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Moliya holatini visual grafik (PNG) ko'rinishida chiqarib beradi."""
    categories = ['Daromad', 'Xarajat', 'Jamg'arma Maqsadi']
    values = [user_finance["income"], user_finance["expense"], user_finance["savings_goal"]]

    plt.figure(figsize=(7, 4))
    plt.bar(categories, values, color=['#2ecc71', '#e74c3c', '#3498db'])
    plt.title('Moliyaviy Holat Statistikasi (So'm)')
    plt.ylabel('Mablağ')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()

    needed = user_finance["savings_goal"] - (user_finance["income"] - user_finance["expense"])
    text_info = (
        f"📊 **Moliyaviy Hisobot:**\n"
        f"💵 Jami Daromad: {user_finance['income']:,} so'm\n"
        f"💸 Jami Xarajat: {user_finance['expense']:,} so'm\n"
        f"🎯 Maqsadga yetish uchun yana: {max(needed, 0):,} so'm kerak."
    )

    await update.message.reply_photo(photo=buf, caption=text_info)

# ==========================================
# UMUMIY MATN XABARLARINI QAYTA ISHLASH
# ==========================================
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    # Moliya haqidagi xabarlar uchun sodda kalit so'z tahlili
    if "daromad:" in user_text.lower():
        try:
            val = int("".join(filter(str.isdigit, user_text)))
            user_finance["income"] += val
            await update.message.reply_text(f"✅ {val:,} so'm daromad hisobga olindi.")
            return
        except:
            pass
    elif "xarajat:" in user_text.lower():
        try:
            val = int("".join(filter(str.isdigit, user_text)))
            user_finance["expense"] += val
            await update.message.reply_text(f"✅ {val:,} so'm xarajat hisobga olindi.")
            return
        except:
            pass

    # Umumiy savol va rejalarga AI javobi
    prompt = (
        f"Siz foydalanuvchining shaxsiy assistenti va nazoratchisisiz. "
        f"Foydalanuvchi yozdi: '{user_text}'. "
        f"Uning kunlik rejalari, daromadi, dars jarayoni va kitob o'qishini tartibga soluvchi va "
        f"dalda beruvchi samimiy javob qaytaring."
    )
    response = await llm.ainvoke(prompt)
    await update.message.reply_text(response.content)

# ==========================================
# MAIN EXECUTION & SCHEDULER
# ==========================================
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("chart", generate_finance_chart))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Scheduler (Avto-Post va Nazorat uchun)
    scheduler = AsyncIOScheduler()
    
    # 1. Har 3 kunda 1 marta kanalga avto-post joylash
    scheduler.add_job(
        post_ai_news_to_channel,
        'interval',
        days=3,
        args=[app.bot]
    )

    # 2. Har kuni soat 21:00 da nazorat qilish
    scheduler.add_job(
        daily_supervisor_check,
        'cron',
        hour=21,
        minute=0,
        args=[app.bot]
    )

    scheduler.start()

    logging.info("AI Agent bot muvaffaqiyatli ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()