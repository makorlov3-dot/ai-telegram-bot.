import os
import logging
from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    raise RuntimeError("Set TELEGRAM_BOT_TOKEN and GROQ_API_KEY as environment variables/secrets.")

client = Groq(api_key=GROQ_API_KEY)
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
SYSTEM_PROMPT = (
    "Ты дружелюбный ИИ-помощник. Отвечай на языке пользователя. "
    "Помогай с вопросами, идеями, текстами, рекламой и описаниями товаров. "
    "Не обещай гарантированный доход и не выдумывай факты."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💬 Спросить ИИ", callback_data="chat")],
        [InlineKeyboardButton("✍️ Написать пост", callback_data="post")],
        [InlineKeyboardButton("📣 Создать рекламу", callback_data="ad")],
        [InlineKeyboardButton("🛍 Описание товара", callback_data="product")],
    ]
    await update.message.reply_text(
        "Привет! Я ИИ-помощник 🤖\n\nМогу отвечать на вопросы и помогать создавать контент.\n\n"
        "Команды:\n/start — меню\n/help — помощь\n/post тема — пост\n"
        "/ad товар или услуга — рекламный текст\n/product товар — описание товара\n\n"
        "Это стартовая версия; платные подписки пока не подключены.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши вопрос обычным сообщением. Для контента используй /post тема, /ad товар или услуга, /product товар.")

async def ask_ai(prompt: str) -> str:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=900,
    )
    return response.choices[0].message.content or "Не удалось подготовить ответ."

async def send_long(update: Update, text: str):
    chunks = [text[i:i+3900] for i in range(0, len(text), 3900)] or ["Нет ответа."]
    for chunk in chunks:
        await update.effective_message.reply_text(chunk)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = (update.message.text or "").strip()
    if not user_text:
        return
    await update.message.chat.send_action("typing")
    try:
        await send_long(update, await ask_ai(user_text))
    except Exception:
        logging.exception("AI request failed")
        await update.message.reply_text("Не получилось ответить. Проверь ключ Groq, интернет и лимит API.")

async def content_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.split()[0].split("@")[0].lower()
    topic = " ".join(context.args).strip()
    if not topic:
        examples = {
            "/post": "Например: /post преимущества кофейни",
            "/ad": "Например: /ad уборка квартир",
            "/product": "Например: /product беспроводные наушники",
        }
        await update.message.reply_text(examples.get(command, "Добавь тему после команды."))
        return
    prompts = {
        "/post": f"Напиши готовый пост для соцсетей на тему: {topic}. Добавь цепляющее начало и призыв к действию.",
        "/ad": f"Создай честный рекламный текст для товара или услуги: {topic}. Не придумывай цены и неподтверждённые свойства.",
        "/product": f"Напиши привлекательное описание товара: {topic}. Не выдумывай неизвестные характеристики.",
    }
    await update.message.chat.send_action("typing")
    try:
        await send_long(update, await ask_ai(prompts[command]))
    except Exception:
        logging.exception("Content generation failed")
        await update.message.reply_text("Не удалось создать текст. Проверь ключ Groq и лимит API.")

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    actions = {
        "chat": "Напиши мне любой вопрос — я отвечу.",
        "post": "Чтобы создать пост, отправь: /post тема",
        "ad": "Чтобы создать рекламу, отправь: /ad товар или услуга",
        "product": "Чтобы описать товар, отправь: /product название товара",
    }
    await query.message.reply_text(actions.get(query.data, "Напиши мне сообщение."))

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("post", content_command))
    app.add_handler(CommandHandler("ad", content_command))
    app.add_handler(CommandHandler("product", content_command))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running. Keep this process running to keep the bot online.")
    app.run_polling()

if __name__ == "__main__":
    main()
