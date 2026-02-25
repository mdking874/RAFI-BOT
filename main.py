import logging
import random
import re
import requests
import json
import os
import time
import threading
import psutil
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ---------------------------------------------------------
# ১. কনফিগারেশন
BOT_TOKEN = "7847611701:AAEhNlrD0gvYA-qX2gdKYoMDcmDBTN8GuvY"
ADMIN_ID = 1933498659
ADMIN_USERNAME = "@bijai_com"
WEB_PASSWORD = "bijai_admin" 

# খুবই জরুরি: Render থেকে পাওয়া লিঙ্কটি এখানে বসান।
# উদাহরণ: MINI_APP_URL = "https://bijai-bot.onrender.com"
MINI_APP_URL = "আপনার_রেন্ডার_লিঙ্ক_এখানে_দিন" 

# ডাটাবেস ফাইল
USERS_FILE = "users_db.json"
KEYS_FILE = "keys_db.json"
HISTORY_FILE = "video_history.json"

CLEAN_PLAYER_URL = "https://hlsjs.video-dev.org/demo/?src="
START_TIME = time.time()

# সাইট লিস্ট
SITES = ["https://fry99.cc/", "https://desibp1.com/", "https://desibf.com/tag/desi-49/", "https://www.desitales2.com/videos/tag/desi49/"]
# ---------------------------------------------------------

# ডাটাবেস ফাংশন
def load_db(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, 'r') as f: return json.load(f)
    except: return {}

def save_db(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

async def check_vip(uid):
    users = load_db(USERS_FILE); uid = str(uid)
    if uid in users:
        exp = datetime.strptime(users[uid], "%Y-%m-%d %H:%M:%S")
        if exp > datetime.now(): return True, exp
    return False, None

# --- ৪. এডমিন ওয়েবসাইট (আধুনিক ডিজাইন) ---
web_app = Flask(__name__)
web_app.secret_key = "bijai_pro_vault_secret"

@web_app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form.get('p') == WEB_PASSWORD:
        session['adm'] = True; return redirect(url_for('dashboard'))
    return '''
    <body style="background:#0f172a; color:white; font-family:sans-serif; text-align:center; padding-top:100px;">
        <div style="background:#1e293b; display:inline-block; padding:30px; border-radius:15px; box-shadow:0 10px 20px rgba(0,0,0,0.5);">
            <h2 style="color:#6366f1;">🔐 BIJAI ADMIN LOGIN</h2>
            <form method="POST">
                <input type="password" name="p" placeholder="Enter Password" style="padding:10px; border-radius:5px; border:none;"><br><br>
                <button type="submit" style="background:#6366f1; color:white; border:none; padding:10px 30px; border-radius:5px; cursor:pointer;">Login</button>
            </form>
        </div>
    </body>
    '''

@web_app.route('/')
def dashboard():
    if not session.get('adm'): return redirect(url_for('login'))
    users = load_db(USERS_FILE); keys = load_db(KEYS_FILE)
    uptime = str(timedelta(seconds=int(time.time() - START_TIME)))
    return render_template_string("""
    <!DOCTYPE html><html><head><title>Admin Console</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 text-white p-5 font-sans">
        <div class="max-w-6xl mx-auto">
            <div class="flex justify-between items-center mb-10 bg-slate-800 p-6 rounded-2xl">
                <h1 class="text-3xl font-bold text-indigo-400">🚀 BIJAI ADMIN WEB</h1>
                <div class="text-sm">Uptime: <span class="text-yellow-400">{{uptime}}</span></div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="bg-slate-800 p-6 rounded-2xl border border-slate-700">Total Users: <b class="text-2xl">{{u_count}}</b></div>
                <div class="bg-slate-800 p-6 rounded-2xl border border-slate-700">Keys Ready: <b class="text-2xl text-green-400">{{k_count}}</b></div>
                <div class="bg-slate-800 p-6 rounded-2xl border border-slate-700">Server Load: <b class="text-2xl text-indigo-400">{{cpu}}%</b></div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div class="bg-slate-800 p-8 rounded-2xl">
                    <h2 class="text-xl font-bold mb-4 text-indigo-400">🔑 Generate VIP Key</h2>
                    <form action="/gen" method="POST" class="space-y-4">
                        <input type="number" name="d" placeholder="Days (e.g. 30)" class="w-full bg-slate-700 p-3 rounded-xl outline-none" required>
                        <button class="w-full bg-indigo-600 py-3 rounded-xl font-bold hover:bg-indigo-500">Create Key</button>
                    </form>
                </div>

                <div class="bg-slate-800 p-8 rounded-2xl overflow-x-auto">
                    <h2 class="text-xl font-bold mb-4 text-indigo-400">👤 VIP User Management</h2>
                    <table class="w-full text-left text-sm">
                        <tr class="text-gray-400 border-b border-slate-700"><th>UID</th><th>Expiry</th></tr>
                        {% for uid, exp in users.items() %}
                        <tr class="border-b border-slate-700/50"><td class="py-2">{{uid}}</td><td>{{exp}}</td></tr>
                        {% endfor %}
                    </table>
                </div>
            </div>
        </div>
    </body></html>
    """, u_count=len(users), k_count=len(keys), cpu=psutil.cpu_percent(), uptime=uptime, users=users)

@web_app.route('/gen', methods=['POST'])
def web_gen():
    if not session.get('adm'): return "Access Denied"
    days = int(request.form.get('d', 30))
    key = f"VIP-{random.randint(100,999)}-{random.randint(100,999)}"
    k_db = load_db(KEYS_FILE); k_db[key] = {"days": days}; save_db(KEYS_FILE, k_db)
    return f'<body style="background:#0f172a;color:white;text-align:center;padding-top:100px;"><h2>Key: <span style="color:yellow;">{key}</span></h2><a href="/" style="color:cyan;text-decoration:none;">Go Back</a></body>'

# --- ৫. টেলিগ্রাম বত হ্যান্ডলারস ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        kb = [[InlineKeyboardButton("📱 Open Admin Web-Panel", web_app=WebAppInfo(url=MINI_APP_URL))]]
        await update.message.reply_text("🖥 **BIJAI ADMIN CONTROL CENTER**\nনিচের বাটনটি ক্লিক করলে আপনার এডমিন ওয়েবসাইটটি টেলিগ্রামের ভেতরেই ওপেন হবে।", 
                                         reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    is_v, exp = await check_vip(uid)
    if is_v:
        await update.message.reply_text(f"✅ **WELCOME VIP!**\n⏳ মেয়াদ: `{exp.strftime('%Y-%m-%d')}`\n\nভিডিওর জন্য `video` লিখুন।", parse_mode='Markdown')
    else:
        # স্টাইলিশ ওয়েলকাম ফটো মেসেজ
        kb = [[InlineKeyboardButton("🔞 Watch Demo Video", url="https://desibf.com/live/")],
              [InlineKeyboardButton("💳 Buy VIP Key (Admin)", url=f"https://t.me/{ADMIN_USERNAME[1:]}")]]
        await update.message.reply_photo(photo="https://files.catbox.moe/r4z7sh.jpg", 
                                         caption="👑 **BIJAI PREMIUM VAULT** 👑\n\n১০,০০০+ আনলিমিটেড হট ভিডিও দেখতে VIP মেম্বারশিপ প্রয়োজন।\n\nঅ্যাডমিন: " + ADMIN_USERNAME, 
                                         reply_markup=InlineKeyboardMarkup(kb))

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    is_v, _ = await check_vip(uid)
    
    if not is_v and int(uid) != ADMIN_ID:
        await start_cmd(update, context); return

    msg = await update.message.reply_text("🎥 ভিডিও খোঁজা হচ্ছে...")
    # স্ক্র্যাপিং লজিক
    try:
        random_site = random.choice(SITES)
        res = requests.get(random_site, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        videos = []
        for a in soup.find_all('a'):
            img = a.find('img')
            if img and a.get('href') and len(a.get('href')) > 25:
                videos.append({'t': img.get('alt'), 'u': a.get('href'), 'i': img.get('src')})
        
        v = random.choice(videos)
        v_res = requests.get(v['u'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        m3u8 = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', v_res.text)
        
        if m3u8:
            caption = f"🎬 **{v['t']}**\n🛡️ VIP Ad-Free Ready ✅\n\n▶️ [Watch Now]({CLEAN_PLAYER_URL + m3u8[0]})"
            await update.message.reply_photo(photo=v['i'], caption=caption, parse_mode='Markdown')
            await msg.delete()
        else:
            await msg.edit_text("🕒 পরে চেষ্টা করুন।")
    except:
        await msg.edit_text("❌ নেটওয়ার্ক এরর। আবার চেষ্টা করুন।")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ki = context.args[0]; k_db = load_db(KEYS_FILE)
        if ki in k_db:
            exp = (datetime.now() + timedelta(days=k_db[ki]['days'])).strftime("%Y-%m-%d %H:%M:%S")
            u_db = load_db(USERS_FILE); u_db[str(update.effective_user.id)] = exp; save_db(USERS_FILE, u_db)
            del k_db[ki]; save_db(KEYS_FILE, k_db)
            await update.message.reply_text("🎉 অভিনন্দন! প্রিমিয়াম চালু হয়েছে।")
        else: await update.message.reply_text("❌ ভুল কি!")
    except: await update.message.reply_text("সঠিক নিয়ম: `/redeem KEY`")

# --- ৬. রানার ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: web_app.run(host='0.0.0.0', port=port)).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("video", video_handler))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), video_handler))
    print("Bot & Web Admin is running...")
    app.run_polling()
