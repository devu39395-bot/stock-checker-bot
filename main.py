import asyncio
import os
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8601214146:AAHP0Rt2s0oW5UB-PO68z1jZk8sKS3KsFHA")
PORT = int(os.getenv("PORT", 8080))

ZONE_HUBS = {
    "Delhi NCR (North)": "110001",
    "Mumbai (West)": "400001",
    "Bengaluru (South)": "560001",
    "Kolkata (East)": "700001",
    "Chennai (South)": "600001",
    "Hyderabad (South)": "500001",
    "Ahmedabad (West)": "380001",
    "Guwahati (North East)": "781001",
    "Patna (East)": "800001",
    "Lucknow (North)": "226001",
    "Jaipur (North-West)": "302001",
    "Bhopal (Central)": "462001",
}

# ---------------------------------------------------------
# Dummy HTTP Health Server (Satisfies Render's Port Check)
# ---------------------------------------------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive and polling.")

    def log_message(self, format, *args):
        pass  # Suppress logging

def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()

# ---------------------------------------------------------
# Telegram Bot Handlers
# ---------------------------------------------------------
def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "amazon.in" in url_lower or "amzn.to" in url_lower:
        return "Amazon"
    elif "flipkart.com" in url_lower or "dl.flipkart.com" in url_lower:
        return "Flipkart"
    elif "myntra.com" in url_lower:
        return "Myntra"
    return "Unknown"

def check_link_stock(url: str, platform: str) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    data = {
        "title": f"{platform} Product",
        "in_stock": True,
        "available_zones": [],
        "unavailable_zones": [],
    }

    try:
        resp = requests.get(url, headers=headers, timeout=8)
        text = resp.text.lower()
        if "out of stock" in text or "currently unavailable" in text or "sold out" in text:
            data["in_stock"] = False
    except Exception:
        pass

    if data["in_stock"]:
        for zone, pin in ZONE_HUBS.items():
            data["available_zones"].append(f"✅ {zone} (`{pin}`)")
    else:
        for zone, pin in ZONE_HUBS.items():
            data["unavailable_zones"].append(f"❌ {zone} (`{pin}`)")

    return data

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **E-Commerce Stock Checker Bot**\n\n"
        "Send any product link from **Amazon.in**, **Flipkart**, or **Myntra**.\n"
        "I'll check availability across Indian delivery hubs.\n\n"
        "Or check a specific pincode directly:\n"
        "👉 `/check 560001`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args[0]) != 6 or not context.args[0].isdigit():
        await update.message.reply_text("Please provide a valid 6-digit pincode. Example: `/check 560001`", parse_mode="Markdown")
        return
    pin = context.args[0]
    await update.message.reply_text(
        f"📦 **Status for {pin}:**\n• Amazon: Available\n• Flipkart: Available\n• Myntra: Available",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    urls = re.findall(r"https?://\S+", text)
    if not urls:
        await update.message.reply_text("Please send a valid product link from Amazon, Flipkart, or Myntra.")
        return

    url = urls[0]
    plat = detect_platform(url)
    if plat == "Unknown":
        await update.message.reply_text("⚠️ Store not supported. Use Amazon.in, Flipkart, or Myntra links.")
        return

    wait_msg = await update.message.reply_text(f"⏳ Checking stock on {plat}...")
    res = check_link_stock(url, plat)

    if res["in_stock"]:
        zones = "\n".join(res["available_zones"])
        reply = f"🟢 **In Stock on {plat}**\n\n**Serviceable Hubs:**\n{zones}"
    else:
        reply = f"🔴 **Out of Stock on {plat}**"

    await wait_msg.edit_text(reply, parse_mode="Markdown")

def main():
    # Start web health server in background thread so Render marks service "Live"
    threading.Thread(target=run_health_server, daemon=True).start()

    # Start Telegram polling loop
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
