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

# Render-এ ডিপ্লয় করার পর যে লিঙ্কটি পাবেন সেটি এখানে দিন
# উদা: "https://my-bot.onrender.com"
MINI_APP_URL = "আপনার_রেন্ডার_লিঙ্ক_এখানে_দিন" 

# ডাটাবেস ফাইল পাথ (Render-এর জন্য /tmp/ ব্যবহার করা নিরাপদ)
USERS_FILE = "users_db.json"
KEYS_FILE = "keys_db.json"
HISTORY_FILE = "video_history.json"

CLEAN_PLAYER_URL = "https://hlsjs.video-dev.org/demo/?src="
START_TIME = time.time()

# ১২০টি পেজের ভল্ট সেটআপ
REGULAR_SITES = []
for i in range(1, 31):
    REGULAR_SITES.append(f"https://fry99.cc/page/{i}/")
    REGULAR_SITES.append(f"https://desibp1.com/page/{i}/")
    REGULAR_SITES.append(f"https://desibf.com/tag/desi-49/page/{i}/")
    REGULAR_SITES.append(f"https://www.desitales2.com/videos/tag/desi49/page/{i}/")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
# ---------------------------------------------------------

# --- ২. ডাটাবেস ফাংশন ---
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

# --- ৩. ভিডিও ইঞ্জিন ---
def get_clean_link(url):
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        m3u8 = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', res.text)
        return CLEAN_PLAYER_URL + m3u8[0] if m3u8 else None
    except: return None

def scrape_batch():
    results = []
    sampled = random.sample(REGULAR_SITES, 6)
    for site in sampled:
        try:
            res = requests.get(site, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.find_all('a'):
                img = a.find('img')
                if img and a.get('href') and len(a.get('href')) > 25:
                    results.append({'t': img.get('alt') or "Video", 'u': a.get('href'), 'i': img.get('src') or img.get('data-src')})
        except: continue
    return results

# --- ৪. এডমিন ড্যাশবোর্ড (Web) ---
web_app = Flask(__name__)
web_app.secret_key = "bijai_render_secret"

@web_app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form.get('p') == WEB_PASSWORD:
        session['adm'] = True; return redirect(url_for('dashboard'))
    return '<body style="background:#0f172a;color:white;text-align:center;padding:100px;"><h2>🔐 LOGIN</h2><form method="POST"><input type="password" name="p" style="padding:10px;"><button style="padding:10px;">Go</button></form></body>'

@web_app.route('/')
def dashboard():
    if not session.get('adm'): return redirect(url_for('login'))
    users = load_db(USERS_FILE); keys = load_db(KEYS_FILE)
    uptime = str(timedelta(seconds=int(time.time() - START_TIME)))
    return render_template_string("""
    <!DOCTYPE html><html><head><title>BIJAI Admin</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 text-white p-5">
        <h1 class="text-3xl font-bold text-indigo-400 mb-6 text-center">🚀 ADMIN DASHBOARD</h1>
        <div class="grid grid-cols-2 gap-4 mb-6">
            <div class="bg-slate-800 p-4 rounded-xl">Users: {{u_count}}</div>
            <div class="bg-slate-800 p-4 rounded-xl">CPU: {{cpu}}%</div>
        </div>
        <form action="/gen" method="POST" class="bg-slate-800 p-6 rounded-xl mb-6">
            <h2 class="font-bold mb-3">🔑 Generate Key</h2>
            <input type="number" name="d" placeholder="Days" class="bg-slate-700 p-2 w-full rounded mb-3" required>
            <button class="bg-indigo-600 w-full py-2 rounded font-bold">GENERATE</button>
        </form>
        <div class="bg-slate-800 p-6 rounded-xl overflow-x-auto">
            <h2 class="font-bold mb-3">👤 Active Users</h2>
            <table class="w-full text-left text-sm">
                <tr class="border-b border-slate-700"><th>UID</th><th>Expiry</th></tr>
                {% for uid, exp in users.items() %}
                <tr class="border-b border-slate-700/50"><td class="py-2">{{uid}}</td><td>{{exp}}</td></tr>
                {% endfor %}
            </table>
        </div>
    </body></html>
    """, u_count=len(users), cpu=psutil.cpu_percent(), users=users, uptime=uptime)

@web_app.route('/gen', methods=['POST'])
def web_gen():
    if not session.get('adm'): return "Unauthorized"
    days = int(request.form.get('d', 30))
    key = f"VIP-{random.randint(100,999)}-{random.randint(100,999)}"
    k_db = load_db(KEYS_FILE); k_db[key] = {"days": days}; save_db(KEYS_FILE, k_db)
    return f"<h3>Key: {key}</h3><a href='/'>Back</a>"

# --- ৫. টেলিগ্রাম বত হ্যান্ডলারস ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        kb = [[InlineKeyboardButton("📱 Open Dashboard", web_app=WebAppInfo(url=MINI_APP_URL))]]
        await update.message.reply_text("🖥 **ADMIN PANEL**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    is_v, exp = await check_vip(uid)
    if is_v:
        await update.message.reply_text(f"✅ VIP সক্রিয়! মেয়াদ: `{exp.strftime('%Y-%m-%d')}`", parse_mode='Markdown')
    else:
        kb = [[InlineKeyboardButton("💳 Buy VIP Key", url=f"https://t.me/{ADMIN_USERNAME[1:]}")]]
        await update.message.reply_photo(photo="https://files.catbox.moe/r4z7sh.jpg", 
                                         caption="👑 **BIJAI PREMIUM**\n\nভিডিও দেখতে VIP কি প্রয়োজন।", reply_markup=InlineKeyboardMarkup(kb))

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    is_v, _ = await check_vip(uid)
    if not is_v and int(uid) != ADMIN_ID: await start(update, context); return

    msg = await update.message.reply_text("🎥 খোঁজা হচ্ছে...")
    batch = scrape_batch(); random.shuffle(batch)
    history = load_db(HISTORY_FILE); user_hist = history.get(uid, [])

    for v in batch:
        if v['u'] in user_hist: continue
        clean = get_clean_link(v['u'])
        if clean:
            user_hist.append(v['u']); history[uid] = user_hist[-50:]; save_db(HISTORY_FILE, history)
            caption = f"🎬 **{v['t']}**\n▶️ [Watch Now]({clean})"
            try:
                await update.message.reply_photo(photo=v['i'] or "https://via.placeholder.com/400", caption=caption, parse_mode='Markdown')
                await msg.delete(); return
            except:
                await update.message.reply_text(caption, parse_mode='Markdown'); return
    await msg.edit_text("🕒 নতুন ভিডিও নেই। আবার চেষ্টা করুন।")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ki = context.args[0]; k_db = load_db(KEYS_FILE)
        if ki in k_db:
            exp = (datetime.now() + timedelta(days=k_db[ki]['days'])).strftime("%Y-%m-%d %H:%M:%S")
            u_db = load_db(USERS_FILE); u_db[str(update.effective_user.id)] = exp; save_db(USERS_FILE, u_db)
            del k_db[ki]; save_db(KEYS_FILE, k_db)
            await update.message.reply_text("🎉 VIP সক্রিয় হয়েছে!")
        else: await update.message.reply_text("❌ ভুল কি!")
    except: await update.message.reply_text("/redeem KEY")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000)) # Render-এর জন্য ডিফল্ট পোর্ট
    threading.Thread(target=lambda: web_app.run(host='0.0.0.0', port=port)).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), video_handler))
    app.run_polling()
