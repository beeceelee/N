import os
import telebot
import sqlite3
import datetime
import logging
from telebot import types

# ========================
# Setup Logging
# ========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ========================
# Environment Variables
# ========================
TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN or not ADMIN_ID:
    logging.error("Missing TOKEN or ADMIN_ID environment variable.")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# ========================
# Database Setup
# ========================
conn = sqlite3.connect('Neiokxbot.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0,
                tasks_completed INTEGER DEFAULT 0,
                last_reset DATE,
                referrals INTEGER DEFAULT 0
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT
            )''')
conn.commit()

# ========================
# Bot Settings
# ========================
DAILY_TASKS = 30
TASK_REWARD = 2.0
REFERRAL_REWARD = 5.0

# ========================
# Helper Functions
# ========================
def reset_daily_tasks(user_id):
    today = datetime.date.today()
    c.execute("SELECT last_reset FROM users WHERE user_id=?", (user_id,))
    data = c.fetchone()
    if not data or data[0] != str(today):
        c.execute("UPDATE users SET tasks_completed=?, last_reset=? WHERE user_id=?", (0, today, user_id))
        conn.commit()

def send_dashboard(chat_id):
    c.execute("SELECT balance, tasks_completed FROM users WHERE user_id=?", (chat_id,))
    user = c.fetchone()
    reset_daily_tasks(chat_id)

    if user:
        balance, completed = user
        remaining = DAILY_TASKS - completed
        progress = int((completed / DAILY_TASKS) * 10)
        progress_bar = "█" * progress + "░" * (10 - progress)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("▶ Start Task", callback_data="start_task"))
        markup.add(types.InlineKeyboardButton("👥 Refer & Earn", callback_data="refer"))
        markup.add(types.InlineKeyboardButton("💰 Withdraw", callback_data="withdraw"))

        bot.send_message(chat_id,
                         f"💰 Balance: {balance:.1f} VET\n\n"
                         f"📅 Today's Ad Tasks:\n"
                         f"Total: {DAILY_TASKS}\n"
                         f"✅ Completed: {completed}\n"
                         f"⏳ Remaining: {remaining}\n\n"
                         f"{progress_bar} {int((completed / DAILY_TASKS) * 100)}%",
                         reply_markup=markup)

# ========================
# Commands
# ========================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()

    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, last_reset) VALUES (?, ?)", (user_id, str(datetime.date.today())))
        conn.commit()

        # Handle referral
        if len(args) > 1 and args[1].startswith("ref"):
            ref_id = int(args[1][3:])
            if ref_id != user_id:
                c.execute("UPDATE users SET balance=balance+?, referrals=referrals+1 WHERE user_id=?",
                          (REFERRAL_REWARD, ref_id))
                conn.commit()
                bot.send_message(ref_id, f"🎉 You got {REFERRAL_REWARD} VET for referring a friend!")

    send_dashboard(message.chat.id)

@bot.message_handler(commands=['addad'])
def add_ad(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        try:
            url = message.text.split(maxsplit=1)[1]
            c.execute("INSERT INTO ads (url) VALUES (?)", (url,))
            conn.commit()
            bot.send_message(message.chat.id, "✅ Ad added successfully!")
        except:
            bot.send_message(message.chat.id, "⚠ Usage: /addad <ad_url>")
    else:
        bot.send_message(message.chat.id, "❌ You are not authorized.")

# ========================
# Callback Handlers
# ========================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "start_task":
        start_task(call.message.chat.id)
    elif call.data == "refer":
        bot.send_message(call.message.chat.id,
                         f"👥 Share your referral link:\nhttps://t.me/{bot.get_me().username}?start=ref{call.message.chat.id}")
    elif call.data == "withdraw":
        bot.send_message(call.message.chat.id, "💸 Withdrawals are processed manually. Contact admin.")

# ========================
# Task Logic
# ========================
def start_task(user_id):
    reset_daily_tasks(user_id)
    c.execute("SELECT tasks_completed FROM users WHERE user_id=?", (user_id,))
    completed = c.fetchone()[0]

    if completed >= DAILY_TASKS:
        bot.send_message(user_id, "✅ You've completed all your daily tasks!")
        return

    c.execute("SELECT url FROM ads ORDER BY RANDOM() LIMIT 1")
    ad = c.fetchone()
    if ad:
        bot.send_message(user_id, f"📺 Watch this ad:\n{ad[0]}")
    else:
        bot.send_message(user_id, "❌ No ads available right now.")
        return

    c.execute("UPDATE users SET balance=balance+?, tasks_completed=tasks_completed+1 WHERE user_id=?",
              (TASK_REWARD, user_id))
    conn.commit()
    send_dashboard(user_id)

# ========================
# Start Bot
# ========================
if __name__ == "__main__":
    logging.info("🤖 Bot is running...")
    bot.polling()
