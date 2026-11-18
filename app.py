import sqlite3
import time
import logging
import io
import threading
import qrcode
import os
import asyncio
import random
import string
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from moviepy import TextClip, ColorClip, CompositeVideoClip, AudioFileClip
from gtts import gTTS
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
import libsql_client

# Logging configuration
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "9025362287:AAFZ2bN485I7QG_Upu_hy9CCM8mOWqpk68I")
ADMIN_ID = int(os.getenv("ADMIN_ID", 8122669942))

TURSO_URL = os.getenv("TURSO_URL", "libsql://mybotdb-gaganllc.aws-ap-south-1.turso.io")
TURSO_TOKEN = os.getenv("TURSO_TOKEN", "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTQ5NDc4MjUsImlkIjoiMDFhMWViMzEtM2QwMS03YThlLWJlMWQtOGE1ZjhiNTYyNjc4Iiwia2lkIjoiNTRfWjhvUlpPbUFmTEZuSzRRS1I2dlhMcE5IbzRXQVRDRFFMSW55QkpQUSIsInJpZCI6ImU4YmUwNjA0LTgxZDYtNDU2MC05ODkwLWM3MjkyMDU2NGQ1YiJ9._CTAZghoZEiOvnP8OMyAZZWJj7_eMyjW4Ew12FdPZLJMB1604LqXL5Ge5hkRKblxmrWpYXFE7rkVrn6fB-SDCw")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

HOOK_FORMULAS = [
    {"type": "Question Hook", "template": "Did you know that {niche_topic} is completely changing how people succeed?"},
    {"type": "Negative/Warning", "template": "Stop doing this in {niche_topic} if you don't want to waste your time!"},
    {"type": "Curiosity/Secret", "template": "This simple {niche_topic} secret will save you 100s of hours."},
    {"type": "Transformation", "template": "How 1 minute of {niche_topic} daily completely changes your perspective."},
    {"type": "Stat/Fact", "template": "95% of people fail at {niche_topic} because they miss this core principle."}
]

def calculate_hook_score(text):
    score = 5.0
    words = text.split()
    if len(words) < 15: score += 2.0  
    if any(kw in text.lower() for kw in ["secret", "stop", "never", "proven", "change", "fast"]): score += 1.5  
    if "?" in text or "!" in text: score += 1.0  
    return min(score, 9.8)

def generate_viral_script_with_agent(niche):
    hook_data = random.choice(HOOK_FORMULAS)
    hook_text = hook_data["template"].format(niche_topic=niche)
    body_scripts = {
        "Motivation & Mindset": "Your mind creates your reality. Every obstacle is an invitation to build resilience. Keep pushing.",
        "Tech & AI Gadgets": "AI automation is replacing repetitive work. Leverage these smart workflows to stay ahead of everyone.",
        "Fitness & Gym": "Consistency beats intensity every time. Show up daily, master your routine, and watch the results follow.",
        "Business & Startup": "Focus on solving real problems. Value creation always leads to sustainable authority and high growth."
    }
    main_body = body_scripts.get(niche, f"Mastering {niche} requires focus, discipline, and daily execution.")
    cta = f"Follow for more {niche} secrets!"
    return f"{hook_text} {main_body} {cta}", calculate_hook_score(hook_text), hook_data["type"]

def generate_title_and_tags(niche, script_text):
    clean_niche = niche.replace(" ", "")
    title = f"{niche} - {' '.join(script_text.split()[:4])}... #shorts"
    if len(title) > 90: title = title[:87] + "..."
    return title, [niche.lower(), "shorts", "viral", "automation", "ytagent", clean_niche.lower()]

NICHE_LIST = [
    "Motivation & Mindset", "Tech & AI Gadgets", "Fitness & Gym", "Business & Startup",
    "Personal Finance", "Life Hacks & DIY", "Psychology Facts", "Historical Events",
    "Sci-Fi & Space", "Health & Nutrition", "Cooking & Recipes", "Travel & Adventure",
    "Fashion & Style", "Book Summaries", "Self Improvement", "Cryptocurrency",
    "Gaming Tips", "Car & Supercars", "Filmmaking & Edit", "Luxury Lifestyle",
    "Stoicism Philosophy", "Mythology Stories", "Productivity Hacks", "Coding Tips", "English Learning"
]

def get_db():
    return libsql_client.create_client(url=TURSO_URL, auth_token=TURSO_TOKEN)

async def ensure_tables_exist():
    client = get_db()
    await client.execute('CREATE TABLE IF NOT EXISTS payment_configs (plan_key TEXT PRIMARY KEY, upi_id TEXT, qr_image_file_id TEXT)')
    await client.execute('CREATE TABLE IF NOT EXISTS connected_channels (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, platform TEXT DEFAULT \'YouTube\', channel_info TEXT, active_mode TEXT DEFAULT \'none\', selected_niche TEXT DEFAULT \'none\', bundle_url TEXT DEFAULT \'none\', custom_prompt TEXT DEFAULT \'none\')')
    await client.execute('CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, plan_name TEXT DEFAULT \'Free Trial\', buy_date TEXT, expire_date TEXT)')
    await client.execute('CREATE TABLE IF NOT EXISTS gift_codes (code TEXT PRIMARY KEY, plan_name TEXT, discount_type TEXT, discount_value REAL)')
    await client.execute('CREATE TABLE IF NOT EXISTS subscription_prices (plan_key TEXT PRIMARY KEY, price REAL)')
    await client.execute('CREATE TABLE IF NOT EXISTS upload_schedules (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, slot_1 TEXT DEFAULT \'09:00\', slot_2 TEXT DEFAULT \'12:00\', slot_3 TEXT DEFAULT \'15:00\', slot_4 TEXT DEFAULT \'18:00\', slot_5 TEXT DEFAULT \'21:00\', slot_6 TEXT DEFAULT \'23:00\')')
    await client.execute('CREATE TABLE IF NOT EXISTS pending_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan_key TEXT, amount REAL, created_at TEXT)')
    await client.execute('CREATE TABLE IF NOT EXISTS received_payments (utr TEXT PRIMARY KEY, raw_text TEXT, is_used INTEGER DEFAULT 0, received_at TEXT)')
    await client.execute('CREATE TABLE IF NOT EXISTS feature_controls (feature_key TEXT PRIMARY KEY, is_enabled INTEGER DEFAULT 1)')
    await client.close()

def is_feature_enabled(key):
    try:
        client = get_db()
        res = client.execute("SELECT is_enabled FROM feature_controls WHERE feature_key = ?", (key,))
        client.close()
        row = res.rows if hasattr(res, 'rows') else res
        return (row[0][0] == 1) if row else True
    except:
        return True

def get_payment_config(plan_key):
    client = get_db()
    res = client.execute("SELECT upi_id, qr_image_file_id FROM payment_configs WHERE plan_key = ?", (plan_key,))
    result = res.rows if hasattr(res, 'rows') else res
    if result and result[0][0] and result[0][0] != 'your_merchant_upi@paytm':
        client.close()
        return result[0]
    res2 = client.execute("SELECT upi_id, qr_image_file_id FROM payment_configs WHERE upi_id != 'your_merchant_upi@paytm' LIMIT 1")
    fallback = res2.rows if hasattr(res2, 'rows') else res2
    client.close()
    return fallback[0] if fallback else ("your_merchant_upi@paytm", None)

def save_payment_config(plan_key, upi_id, qr_image_file_id=None):
    client = get_db()
    client.execute('''
        INSERT INTO payment_configs (plan_key, upi_id, qr_image_file_id)
        VALUES (?, ?, ?)
        ON CONFLICT(plan_key) DO UPDATE SET upi_id = excluded.upi_id, qr_image_file_id = COALESCE(excluded.qr_image_file_id, qr_image_file_id)
    ''', (plan_key, upi_id, qr_image_file_id))
    client.close()

def get_main_menu(is_admin=False):
    keyboard = []
    row1 = []
    if is_feature_enabled('profile'): row1.append(InlineKeyboardButton("👤 Profile", callback_data="menu_profile"))
    if is_feature_enabled('channels'): row1.append(InlineKeyboardButton("📺 My Channels", callback_data="menu_channels"))
    if row1: keyboard.append(row1)
    row2 = []
    if is_feature_enabled('status'): row2.append(InlineKeyboardButton("📊 Status", callback_data="menu_status"))
    if is_feature_enabled('subscription'): row2.append(InlineKeyboardButton("💎 My Subscription", callback_data="menu_subscription"))
    if row2: keyboard.append(row2)
    row3 = []
    if is_feature_enabled('help'): row3.append(InlineKeyboardButton("❓ Help/Support", callback_data="menu_help"))
    if row3: keyboard.append(row3)
    if is_admin: keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="menu_admin")])
    return InlineKeyboardMarkup(keyboard)

async def check_user_subscription_active(user_id):
    client = get_db()
    res = client.execute("SELECT expire_date FROM subscriptions WHERE user_id = ?", (user_id,))
    client.close()
    row = res.rows if hasattr(res, 'rows') else res
    if not row: return False
    try:
        return datetime.now() <= datetime.strptime(row[0][0], "%Y-%m-%d")
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)
    client = get_db()
    res = client.execute("SELECT user_id FROM subscriptions WHERE user_id = ?", (user.id,))
    if not (res.rows if hasattr(res, 'rows') else res):
        client.execute("INSERT INTO subscriptions (user_id, plan_name, buy_date, expire_date) VALUES (?, ?, ?, ?)", 
                       (user.id, "Free Trial", datetime.now().strftime("%Y-%m-%d"), (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")))
    client.close()
    text = f"👋 Welcome to **Blinkeyes Automation Bot**, {user.first_name}!\n\nAap apne YouTube channels ko connect karke automated videos schedule aur publish kar sakte hain."
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=get_main_menu(is_admin), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=get_main_menu(is_admin), parse_mode="Markdown")

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    client = get_db()
    res = client.execute("SELECT plan_name, buy_date, expire_date FROM subscriptions WHERE user_id = ?", (user.id,))
    client.close()
    sub = (res.rows if hasattr(res, 'rows') else res)
    sub = sub[0] if sub else ("Free Trial", "N/A", "N/A")
    text = f"👤 **User Profile:**\n\n🆔 **User ID:** `{user.id}`\n👤 **Name:** {user.full_name}\n💎 **Active Plan:** {sub[0]}\n📅 **Buy Date:** {sub[1]}\n⏳ **Expire Date:** {sub[2]}"
    keyboard = [[InlineKeyboardButton("💳 Buy / Upgrade Subscription", callback_data="sub_plans")], [InlineKeyboardButton("« Back to Home", callback_data="back_home")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def subscription_status_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    client = get_db()
    res = client.execute("SELECT plan_name, buy_date, expire_date FROM subscriptions WHERE user_id = ?", (user.id,))
    client.close()
    sub = (res.rows if hasattr(res, 'rows') else res)
    sub = sub[0] if sub else ("Free Trial", "N/A", "N/A")
    text = f"💎 **Your Subscription Status:**\n\n📦 **Current Plan:** `{sub[0]}`\n📅 **Activation Date:** {sub[1]}\n⏳ **Expiry Date:** {sub[2]}\n\nAap yahan se apna plan upgrade ya renew kar sakte hain:"
    keyboard = [[InlineKeyboardButton("💳 Upgrade / Buy Plan", callback_data="sub_plans")], [InlineKeyboardButton("« Back to Home", callback_data="back_home")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def sub_plans_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    client = get_db()
    res = client.execute("SELECT plan_key, price FROM subscription_prices")
    client.close()
    prices = {row[0]: row[1] for row in (res.rows if hasattr(res, 'rows') else res)}
    text = "💳 **Choose Your Subscription Plan & Duration:**\n\n🔹 **Silver Plan** (1 Channel - 3 Reels/day)\n🔸 **Gold Plan** (4 Channels - 6 Reels/day)\n💎 **Platinum Plan** (8 Channels - 10 Reels/day)\n\nKripya niche diye gaye plan me se apna duration select karein:"
    keyboard = [
        [InlineKeyboardButton(f"🥈 Silver ₹{prices.get('silver_99', 99)} (1M)", callback_data="pay_silver_99"), InlineKeyboardButton(f"🥈 Silver ₹{prices.get('silver_499', 499)} (6M)", callback_data="pay_silver_499")],
        [InlineKeyboardButton(f"🥇 Gold ₹{prices.get('gold_249', 249)} (1M)", callback_data="pay_gold_249"), InlineKeyboardButton(f"🥇 Gold ₹{prices.get('gold_1299', 1299)} (6M)", callback_data="pay_gold_1299")],
        [InlineKeyboardButton(f"💎 Platinum ₹{prices.get('platinum_399', 399)} (1M)", callback_data="pay_platinum_399"), InlineKeyboardButton(f"💎 Platinum ₹{prices.get('platinum_2199', 2199)} (6M)", callback_data="pay_platinum_2199")],
        [InlineKeyboardButton("« Back to Profile", callback_data="menu_profile")]
    ]
    try: await query.message.delete()
    except: pass
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def select_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    plan_key = f"{parts[1]}_{parts[2]}"
    context.user_data['pending_plan_key'] = plan_key
    client = get_db()
    res = client.execute("SELECT price FROM subscription_prices WHERE plan_key = ?", (plan_key,))
    client.close()
    row = (res.rows if hasattr(res, 'rows') else res)
    base_price = row[0][0] if row else 99
    final_price = base_price
    if 'applied_coupon' in context.user_data:
        g_code, g_plan, d_type, d_val = context.user_data['applied_coupon']
        if d_type == "PERCENT": final_price = base_price - (base_price * (d_val / 100))
        else: final_price = max(0, base_price - d_val)
    upi_id, qr_file_id = get_payment_config(plan_key)
    text = f"💳 **Pay via QR / UPI ({parts[1].upper()} - ₹{final_price})**\n\n1. Is QR Code ko apne kisi bhi UPI App se scan karein.\n2. UPI ID: `{upi_id}`\n3. UTR yahan bhej dein."
    keyboard = [[InlineKeyboardButton("✅ I Have Paid (Submit UTR)", callback_data=f"submit_utr_{plan_key}")], [InlineKeyboardButton("« Back to Plans", callback_data="sub_plans")]]
    try: await query.message.delete()
    except: pass
    img = qrcode.make(f"upi://pay?pa={upi_id}&pn=BlinkeyesAutomation&am={final_price}&cu=INR")
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=bio, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def submit_utr_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    context.user_data['pending_plan_key'] = f"{parts[2]}_{parts[3]}"
    await query.message.reply_text("📝 Kripya apni **12-digit UPI Transaction ID (UTR)** yahan chat mein bhej dein:", parse_mode="Markdown")

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text_content = update.message.text.strip() if update.message.text else ""
    if 'pending_plan_key' in context.user_data:
        plan_key = context.user_data.get('pending_plan_key')
        utr_input = re.sub(r'\D', '', text_content)
        if len(utr_input) != 12:
            await update.message.reply_text("⚠️ Kripya apni sahi **12-digit UTR** enter karein:")
            return
        client = get_db()
        res = client.execute("SELECT is_used FROM received_payments WHERE utr = ?", (utr_input,))
        pay = (res.rows if hasattr(res, 'rows') else res)
        if pay and pay[0][0] == 0:
            client.execute("UPDATE received_payments SET is_used = 1 WHERE utr = ?", (utr_input,))
            days = 180 if any(x in plan_key for x in ["499", "1299", "2199"]) else 30
            client.execute("INSERT OR REPLACE INTO subscriptions (user_id, plan_name, buy_date, expire_date) VALUES (?, ?, ?, ?)", 
                           (user.id, plan_key.replace("_", " ").title(), datetime.now().strftime("%Y-%m-%d"), (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")))
            client.close()
            context.user_data.pop('pending_plan_key', None)
            await update.message.reply_text("✅ **Payment Verified & Subscription Activated!**", parse_mode="Markdown")
            return
        client.close()
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **Manual UTR Check Needed!**\nUser: `{user.id}`\nUTR: `{utr_input}`")
        await update.message.reply_text("⏳ UTR verify ki ja rahi hai.")
        context.user_data.pop('pending_plan_key', None)
        return

async def channels_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "📺 **Connected Channels & Pages:**\n\n"
    keyboard = [
        [InlineKeyboardButton("📺 YouTube Management", callback_data="yt_manage")],
        [InlineKeyboardButton("🔗 Connect YouTube (OAuth)", callback_data="auth_youtube")],
        [InlineKeyboardButton("« Back to Home", callback_data="back_home")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def channel_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "📺 **YouTube Management:**\n\nSelect a channel below:"
    keyboard = [[InlineKeyboardButton("🔗 Connect YouTube (OAuth)", callback_data="auth_youtube")], [InlineKeyboardButton("« Back to Channels", callback_data="menu_channels")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def start_youtube_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_secrets_file('client_secret.json', scopes=SCOPES, redirect_uri='http://localhost/')
        url, _ = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
        context.user_data['oauth_flow'] = flow
        context.user_data['waiting_for_auth_code'] = True
        keyboard = [[InlineKeyboardButton("🔗 1. Login & Get Code", url=url)], [InlineKeyboardButton("« Back", callback_data="menu_channels")]]
        await query.message.edit_text("📺 **YouTube Auth:** Click the link, authorize, and send the final redirected URL here.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {e}")

async def status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("📊 **System Status:** Running smoothly!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="back_home")]]), parse_mode="Markdown")

async def help_support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("❓ **Help Center:** Contact admin for assistance.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="back_home")]]), parse_mode="Markdown")

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID: return
    await query.message.edit_text("⚙️ **Admin Panel**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="back_home")]]), parse_mode="Markdown")

async def background_scheduler_loop(bot):
    while True:
        await asyncio.sleep(60)

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Blinkeyes Bot is Alive & Running!"

def run_web():
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(profile_callback, pattern="^menu_profile$"))
    app.add_handler(CallbackQueryHandler(sub_plans_callback, pattern="^sub_plans$"))
    app.add_handler(CallbackQueryHandler(subscription_status_menu, pattern="^menu_subscription$"))
    app.add_handler(CallbackQueryHandler(status_callback, pattern="^menu_status$"))
    app.add_handler(CallbackQueryHandler(help_support_callback, pattern="^menu_help$"))
    app.add_handler(CallbackQueryHandler(channels_callback, pattern="^menu_channels$"))
    app.add_handler(CallbackQueryHandler(select_plan_callback, pattern="^pay_(silver|gold|platinum)_(99|499|249|1299|399|2199)$"))
    app.add_handler(CallbackQueryHandler(submit_utr_prompt, pattern="^submit_utr_"))
    app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern="^menu_admin$"))
    app.add_handler(CallbackQueryHandler(channel_management_callback, pattern="^yt_manage$"))
    app.add_handler(CallbackQueryHandler(start_youtube_auth, pattern="^auth_youtube$"))
    app.add_handler(MessageHandler((filters.TEXT | filters.VIDEO | filters.Document.ALL) & (~filters.COMMAND), handle_text_messages))

    async def post_init(application):
        await ensure_tables_exist()
        asyncio.create_task(background_scheduler_loop(application.bot))

    app.post_init = post_init
    print("🤖 Bot is running smoothly with Turso Cloud DB...")
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    main()
