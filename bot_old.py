import json
import logging
import os
import time
from datetime import datetime
from threading import Thread

import google.generativeai as genai
import gspread
import telebot
from flask import Flask
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIG ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TELE_TOKEN = os.getenv("TELE_TOKEN", "")
GEMINI_KEY = os.getenv("GEMINI_KEY", "")
SHEET_NAME = os.getenv("SHEET_NAME", "expensebro")
PORT = int(os.getenv("PORT", "8080"))

if not TELE_TOKEN:
    raise RuntimeError("Missing TELE_TOKEN environment variable.")

if not GEMINI_KEY:
    raise RuntimeError("Missing GEMINI_KEY environment variable.")

# 1. FLASK SETUP (The "Stay Awake" Trick)
app = Flask('')

@app.route('/')
def home():
    return "irfan's expense bot is online."

def run_web():
    app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)

# 2. BRAIN & DATABASE SETUP
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def get_credentials():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    if raw_json:
        return ServiceAccountCredentials.from_json_keyfile_dict(json.loads(raw_json), scope)

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "creds.json")
    if os.path.exists(creds_path):
        return ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)

    raise RuntimeError(
        "Missing Google credentials. Set GOOGLE_SERVICE_ACCOUNT_JSON or provide creds.json."
    )

def get_sheet():
    creds = get_credentials()
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

# initialize bot
bot = telebot.TeleBot(TELE_TOKEN)

@bot.message_handler(commands=["start", "help"])
def show_help(message):
    bot.reply_to(
        message,
        "Send an expense like 'coffee 25k' or 'grab 42000'. I will log it to your sheet.",
    )

@bot.message_handler(content_types=["text"], func=lambda m: True)
def process_expense(message):
    # engineer-grade prompt: strict formatting is key
    prompt = f"""
    you are a financial assistant for najih. 
    extract data from: "{message.text}"
    convert all currency to pure numbers (e.g., 50k -> 50000).
    categories: [food, transport, gym, coffee, bills, misc].
    return ONLY in this exact format: item, amount, category
    if it is not a clear expense, return exactly: none
    """
    
    try:
        response = model.generate_content(prompt)
        raw_res = (getattr(response, "text", "") or "").strip()
        
        if raw_res and "none" not in raw_res.lower():
            # splitting by comma to match the prompt's requested format
            parts = [x.strip() for x in raw_res.split(",")]
            
            if len(parts) == 3:
                item, price, cat = parts
                date = datetime.now().strftime("%d/%m/%Y")
                
                # re-authorize every time to prevent session timeout
                current_sheet = get_sheet()
                current_sheet.append_row([date, item, price, cat])
                
                bot.reply_to(message, f"Logged: {item} | Rp{price} | [{cat.upper()}]")
            else:
                logger.warning("Unexpected model output: %s", raw_res)
                bot.reply_to(message, "I could not parse that cleanly. Try 'coffee 25k' or 'grab 42000'.")
        else:
            bot.reply_to(message, "Send me an expense and I will log it.")
            
    except Exception as e:
        logger.exception("Expense processing failed: %s", e)
        bot.reply_to(message, "Something broke while saving that expense. Check the Render logs.")

def run_bot():
    while True:
        try:
            logger.info("Starting Telegram polling")
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as exc:
            logger.exception("Polling crashed: %s", exc)
            time.sleep(5)

# 3. EXECUTION
if __name__ == "__main__":
    # start the web server in a background thread
    server_thread = Thread(target=run_web)
    server_thread.start()
    
    logger.info("Starting expense bot")
    run_bot()
