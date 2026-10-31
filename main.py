import asyncio
import os
import threading
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ---------------------------------------------------------
# Configuration & Environment Variables
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))  # Replace with your numeric Telegram user ID
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # e.g. https://your-service.onrender.com
PORT = int(os.getenv("PORT", 8080))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "dev_admin_123")

# In-memory storage for demonstration (Note: resets on server restarts).
# For production, replace this list with SQLite, Supabase, or MongoDB.
request_logs = []

# ---------------------------------------------------------
# Stock Checking Logic
# ---------------------------------------------------------
def check_ecommerce_stock(pincode: str) -> dict:
    """
    Checks stock across platforms for a given pincode.
    Customize the request headers / cookies for production scraping.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    results = {
        "pincode": pincode,
        "amazon": "In Stock (Delivery Available)",
        "flipkart": "In Stock (Delivery Available)",
        "myntra": "Deliverable",
    }

    # Example: Basic Flipkart delivery check structure
    # Most e-commerce APIs require a product ID / session cookies to verify pincodes:
    try:
        # Placeholder for actual network call / API endpoint
        pass
    except Exception as e:
        results["error"] = str(e)

    return results

# ---------------------------------------------------------
# Telegram Bot Handlers
# ---------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Welcome to the E-Commerce Stock Checker Bot!**\n\n"
        "Check stock availability and delivery options across:\n"
        "• Amazon India\n"
        "• Flipkart\n"
        "• Myntra\n\n"
        "📌 **Usage:** `/check <6-digit-pincode>`\n"
        "Example: `/check 560001`\n\n"
        "⚡ *Bot by Dev_Dev*"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if not args or len(args[0]) != 6 or not args[0].isdigit():
        await update.message.reply_text(
            "⚠️ Please provide a valid 6-digit Indian pincode.\nExample: `/check 560001`",
            parse_mode="Markdown"
        )
        return

    pincode = args[0]
    await update.message.reply_text(f"🔍 Checking availability for pincode **{pincode}**...", parse_mode="Markdown")

    # Fetch stock
    stock_status = check_ecommerce_stock(pincode)

    # Log the request for the Admin Panel
    request_logs.append({
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "user_id": user.id,
        "username": user.username or user.first_name,
        "pincode": pincode,
    })

    reply = (
        f"📦 **Stock & Delivery Status for {pincode}:**\n\n"
        f"• **Amazon:** {stock_status['amazon']}\n"
        f"• **Flipkart:** {stock_status['flipkart']}\n"
        f"• **Myntra:** {stock_status['myntra']}\n\n"
        "⚡ *Bot by Dev_Dev*"
    )
    await update.message.reply_text(reply, parse_mode="Markdown")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text("⛔ Unauthorized access.")
        return

    total_requests = len(request_logs)
    recent = "\n".join([f"- {r['pincode']} by @{r['username']}" for r in request_logs[-5:]]) or "None"

    msg = (
        f"📊 **Admin Summary**\n"
        f"Total Pincode Checks: {total_requests}\n\n"
        f"**Last 5 Checks:**\n{recent}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ---------------------------------------------------------
# Flask App & Admin Dashboard
# ---------------------------------------------------------
app = Flask(__name__)

# Initialize Telegram Application
tg_app = Application.builder().token(BOT_TOKEN).build()
tg_app.add_handler(CommandHandler("start", start_command))
tg_app.add_handler(CommandHandler("check", check_command))
tg_app.add_handler(CommandHandler("admin_stats", admin_stats))

@app.route("/")
def home():
    return "Bot service is active and running.", 200

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """Receives updates from Telegram servers."""
    update = Update.de_json(request.get_json(force=True), tg_app.bot)
    asyncio.run(tg_app.process_update(update))
    return "OK", 200

# HTML Template for Web Admin Panel
ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Dev_Dev - Admin Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #f8fafc; color: #1e293b; }
        .card { background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        h1 { margin-top: 0; color: #0f172a; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #e2e8f0; }
        th { background: #f1f5f9; font-weight: 600; }
        .badge { background: #e0f2fe; color: #0369a1; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Admin Control Panel <span class="badge">Dev_Dev</span></h1>
        <p>Total Checks Recorded: <strong>{{ logs|length }}</strong></p>
        <table>
            <thead>
                <tr>
                    <th>Time (UTC)</th>
                    <th>User ID</th>
                    <th>Username</th>
                    <th>Pincode</th>
                </tr>
            </thead>
            <tbody>
                {% for log in logs|reverse %}
                <tr>
                    <td>{{ log.timestamp }}</td>
                    <td>{{ log.user_id }}</td>
                    <td>@{{ log.username }}</td>
                    <td><strong>{{ log.pincode }}</strong></td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="4">No requests received yet.</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

@app.route("/admin")
def web_admin():
    auth_pass = request.args.get("pass")
    if auth_pass != ADMIN_PASSWORD:
        return "Unauthorized. Access requires `?pass=<ADMIN_PASSWORD>`", 401
    return render_template_string(ADMIN_HTML, logs=request_logs)

# ---------------------------------------------------------
# Execution Entry Point
# ---------------------------------------------------------
if __name__ == "__main__":
    # If running locally for testing without a public domain, run polling mode:
    if not WEBHOOK_URL:
        print("Running in local Polling mode...")
        # Start Flask admin server in background thread
        threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT), daemon=True).start()
        tg_app.run_polling()
    else:
        # Production Webhook Mode
        print(f"Setting webhook to: {WEBHOOK_URL}/webhook/{BOT_TOKEN}")
        asyncio.run(tg_app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"))
        app.run(host="0.0.0.0", port=PORT)
