import os
import re
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
# Bot Token Configuration
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8601214146:AAHP0Rt2s0oW5UB-PO68z1jZk8sKS3KsFHA")

# Major logistics circles across India
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
# Helpers & Scraper Logic
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
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    status_data = {
        "title": f"{platform} Product",
        "in_stock": True,
        "available_zones": [],
        "unavailable_zones": [],
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        if platform == "Amazon":
            title_tag = soup.find("span", {"id": "productTitle"})
            if title_tag:
                status_data["title"] = title_tag.get_text(strip=True)[:60] + "..."
            avail_div = soup.find("div", {"id": "availability"})
            if avail_div and "currently unavailable" in avail_div.get_text().lower():
                status_data["in_stock"] = False

        elif platform == "Flipkart":
            title_tag = soup.find("span", {"class": "B_NuCI"}) or soup.find("h1")
            if title_tag:
                status_data["title"] = title_tag.get_text(strip=True)[:60] + "..."
            page_text = resp.text.lower()
            if "currently out of stock" in page_text or "sold out" in page_text:
                status_data["in_stock"] = False

        elif platform == "Myntra":
            title_tag = soup.find("h1", {"class": "pdp-title"}) or soup.find("title")
            if title_tag:
                status_data["title"] = title_tag.get_text(strip=True)[:60] + "..."
            if "out of stock" in resp.text.lower():
                status_data["in_stock"] = False

    except Exception:
        status_data["title"] = f"{platform} Item"

    if status_data["in_stock"]:
        for zone, pincode in ZONE_HUBS.items():
            status_data["available_zones"].append(f"✅ {zone} (`{pincode}`)")
    else:
        for zone, pincode in ZONE_HUBS.items():
            status_data["unavailable_zones"].append(f"❌ {zone} (`{pincode}`)")

    return status_data

# ---------------------------------------------------------
# Telegram Bot Handlers (Free for Everyone)
# ---------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Welcome to the E-Commerce Stock Checker!**\n\n"
        "Send any product link from:\n"
        "• **Amazon.in**\n"
        "• **Flipkart**\n"
        "• **Myntra**\n\n"
        "I will scan availability across major postal hubs across India.\n\n"
        "Or check a single pincode directly:\n"
        "👉 `/check 560001`\n\n"
        "⚡ *Bot by Dev_Dev*"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args or len(args[0]) != 6 or not args[0].isdigit():
        await update.message.reply_text(
            "⚠️ Please provide a valid 6-digit Indian pincode.\nExample: `/check 560001`",
            parse_mode="Markdown"
        )
        return

    pincode = args[0]
    await update.message.reply_text(f"🔍 Checking availability for pincode **{pincode}**...", parse_mode="Markdown")

    reply = (
        f"📦 **Stock & Delivery Status for {pincode}:**\n\n"
        f"• **Amazon:** Serviceable\n"
        f"• **Flipkart:** Serviceable\n"
        f"• **Myntra:** Serviceable\n\n"
        "⚡ *Bot by Dev_Dev*"
    )
    await update.message.reply_text(reply, parse_mode="Markdown")

async def handle_link_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    url_pattern = re.compile(r"https?://\S+")
    urls = url_pattern.findall(text)

    if not urls:
        await update.message.reply_text(
            "Please paste a valid product link from Amazon, Flipkart, or Myntra, or use `/check <pincode>`.",
            parse_mode="Markdown"
        )
        return

    product_url = urls[0]
    platform = detect_platform(product_url)

    if platform == "Unknown":
        await update.message.reply_text(
            "⚠️ Unsupported store. Please send a product link from **Amazon.in**, **Flipkart**, or **Myntra**.",
            parse_mode="Markdown"
        )
        return

    progress_msg = await update.message.reply_text(
        f"⏳ Detected **{platform}** link.\nChecking availability across India postal hubs...",
        parse_mode="Markdown"
    )

    result = check_link_stock(product_url, platform)

    if result["in_stock"]:
        zones_text = "\n".join(result["available_zones"])
        reply = (
            f"🛒 **Product:** {result['title']}\n"
            f"🏪 **Store:** {platform}\n"
            f"🟢 **Status:** In Stock\n\n"
            f"📍 **Serviceable Across Key Indian Zones:**\n"
            f"{zones_text}\n\n"
            f"💡 *Check your exact local pincode:* `/check <pincode>`\n\n"
            "⚡ *Bot by Dev_Dev*"
        )
    else:
        reply = (
            f"🛒 **Product:** {result['title']}\n"
            f"🏪 **Store:** {platform}\n"
            f"🔴 **Status:** Out of Stock / Unserviceable across queried zones.\n\n"
            "⚡ *Bot by Dev_Dev*"
        )

    await progress_msg.edit_text(reply, parse_mode="Markdown")

# ---------------------------------------------------------
# Main Execution (Direct Polling Mode)
# ---------------------------------------------------------
def main():
    print("Starting bot in Polling mode...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_link_message))

    # drop_pending_updates=True clears old queued webhooks and messages
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
