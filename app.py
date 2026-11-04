import feedparser
import requests
import json
import datetime
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = "9212232704:AAGQ51JFrENU8ICQ9BFq6bMqUsGj1_lKRek"
OPENROUTER_KEY = "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"
FINNHUB_KEY = "dbl0299r01qjsmfsau9g"

CRYPTO_FEEDS = ["https://cointelegraph.com/rss", "https://www.coindesk.com/rss"]
STOCK_FEEDS = ["https://www.marketwatch.com/rss/topstories", "https://www.cnbc.com/id/100003114/device/rss/rss.html"]

keyboard = [
    [KeyboardButton("📈 Анализ BTC"), KeyboardButton("📉 Анализ SPY")],
    [KeyboardButton("💰 Цена BTC"), KeyboardButton("🔄 Помощь")]
]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_news(feeds):
    news = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:4]:
                title = entry.get("title", "")
                if title: news.append(title)
        except: pass
    return news[:8]

def get_economic_events():
    today = datetime.date.today().strftime('%Y-%m-%d')
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        url = f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={tomorrow}&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=10)
        events = r.json().get("economicCalendar", [])
        return [e for e in events if e.get("impact", 0) > 0][:6]
    except: return []

def get_ai_analysis(asset_type, news_titles, events):
    if asset_type == "BTC":
        prompt = "Ты крипто-аналитик. Дай прогноз по BTC на русском.\n\n"
    else:
        prompt = "Ты трейдер по S&P 500. Пользователь в ШОРТЕ по SPYUSDT 25x. Дай прогноз на русском.\n\n"
    if news_titles: prompt += "Новости:\n" + "\n".join(f"- {t}" for t in news_titles) + "\n\n"
    if events:
        prompt += "Макроэкономика:\n"
        for e in events:
            prompt += f"- {e.get('time')} {e.get('event')} (Прогноз: {e.get('estimate')}, Прошлое: {e.get('prev')})\n"
    prompt += "\n1) Настрой. 2) Влияние событий. 3) Итог: рост/падение/боковик."
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            data=json.dumps({"model": "openrouter/free", "messages": [{"role": "user", "content": prompt}], "max_tokens": 700}),
            timeout=40
        )
        res_json = response.json()
        return res_json['choices'][0]['message']['content'] if "choices" in res_json else f"Ошибка: {res_json}"
    except Exception as e: return f"Ошибка сети: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот запущен! Используйте кнопки внизу для анализа.", reply_markup=reply_markup)

async def btc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 Анализирую BTC...")
    analysis = get_ai_analysis("BTC", get_news(CRYPTO_FEEDS), get_economic_events())
    await update.message.reply_text(f"📈 **Анализ BTC:**\n\n{analysis}")

async def spy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 Анализирую SPY...")
    analysis = get_ai_analysis("SPY", get_news(STOCK_FEEDS), get_economic_events())
    await update.message.reply_text(f"📉 **Анализ SPY:**\n\n{analysis}")

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true", timeout=10)
        d = r.json()["bitcoin"]
        emoji = "🟢" if d.get("usd_24h_change", 0) > 0 else "🔴"
        await update.message.reply_text(f"💰 BTC: ${d['usd']:,.0f}\n{emoji} 24ч: {d.get('usd_24h_change', 0):+.2f}%", reply_markup=reply_markup)
    except: await update.message.reply_text("Ошибка цены.")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📈 Анализ BTC": await btc_cmd(update, context)
    elif text == "📉 Анализ SPY": await spy_cmd(update, context)
    elif text == "💰 Цена BTC": await price_cmd(update, context)
    elif text == "🔄 Помощь": await start(update, context)

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

def self_ping():
    url = os.environ.get('RENDER_EXTERNAL_URL')
    if url:
        while True:
            time.sleep(600)
            try: requests.get(url, timeout=10)
            except: pass

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("btc", btc_cmd))
    app.add_handler(CommandHandler("spy", spy_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    print("Бот запущен на сервере!")
    app.run_polling()
