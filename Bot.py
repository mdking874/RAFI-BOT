import logging
import random
import re
import requests
import json
import os
import time
import threading
import psutil
import certifi
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pymongo import MongoClient
from flask import Flask, render_template_string, request, redirect, url_for, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ---------------------------------------------------------
# ১. কনফিগারেশন
BOT_TOKEN = "7847611701:AAEhNlrD0gvYA-qX2gdKYoMDcmDBTN8GuvY"
ADMIN_ID = 1933498659
ADMIN_USERNAME = "@bijai_com"
WEB_PASSWORD = "bijai_admin" # ওয়েবসাইটের পাসওয়ার্ড

# আপনার MongoDB লিঙ্ক এখানে দিন (Atlas থেকে পাবেন)
MONGO_URI = "mongodb+srv://আপনার_ইউজার:পাসওয়ার্ড@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority"

# আপনার Koyeb লিঙ্কটি এখানে বসান (Deployment এর পর পাবেন)
MINI_APP_URL = "https://your-app-name.koyeb.app" 

CLEAN_PLAYER_URL = "https://hlsjs.video-dev.org/demo/?src="
START_TIME = time.time()

# ১২০টি পেজের ভল্ট
REGULAR_SITES = []
for i in range(1, 31):
    REGULAR_SITES.append(f"https://fry99.cc/page/{i}/")
    REGULAR_SITES.append(f"https://desibp1.com/page/{i}/")
    REGULAR_SITES.append(f"https://desibf.com/tag/desi-49/page/{i}/")
    REGULAR_SITES.append(f"https://www.desitales2.com/videos/tag/desi49/page/{i}/")

# ফিক্সড ডেমো ভিডিও
DEMO_VIDEOS = [
    {"t": "🎬 Demo Bangla", "u": "https://desibp1.com/6090/desi-tales-bengali-village-scandal/"},
    {"t": "🔥 Demo Desi", "u": "https://fry99.cc/7253/indian-bhabhi-hot-video/"}
]
# ---------------------------------------------------------

# --- ২. ডাটাবেস কানেকশন (MongoDB) ---
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['bijai_vault_db']
col_users = db['users']
col_keys = db['keys']
col_managers = db['managers']
col_history = db['history']

async def check_vip(uid):
    user = col_users.find_one({"uid": str(uid)})
    if user:
        exp = datetime.strptime(user['exp'], "%Y-%m-%d %H:%M:%S")
        if exp > datetime.now(): return True, exp
    return False, None

def is_staff(uid):
    return col_managers.find_one({"uid": str(uid)}) or uid == ADMIN_ID

# --- ৩. ভিডিও স্ক্র্যাপার ---
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
                    results.append({'t': img.get('alt') or "Hot Video", 'u': a.get('href'), 'i': img.get('src') or img.get('data-src')})
        except: continue
    return results

# --- ৪. অ্যাডমিন ওয়েবসাইট (HTML) ---
web_app = Flask(__name__)
web_app.secret_key = "bijai_pro_secret"

@web_app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form.get('p') == WEB_PASSWORD:
        session['adm'] = True; return redirect(url_for('dashboard'))
    return '<body style="background:#0f172a;color:white;text-align:center;padding-top:100px;"><h2>🔐 LOGIN</h2><form method="POST"><input type="password" name="p"><button>Go</button></form></body>'

@web_app.route('/')
def dashboard():
    if not session.get('adm'): return redirect(url_for('login'))
    users = list(col_users.find()); keys = list(col_keys.find())
    uptime = str(timedelta(seconds=int(time.time() - START_TIME)))
    return render_template_string("""
    <!DOCTYPE html><html><head><title>Admin</title><script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-900 text-white p-5 font-sans">
        <div class="max-w-4xl mx-auto">
            <h1 class="text-3xl font-bold text-indigo-400 mb-6">🚀 BIJAI ADMIN CONSOLE</h1>
            <div class="grid grid-cols-2 gap-4 mb-8">
                <div class="bg-slate-800 p-4 rounded-xl">Users: {{total_u}}</div>
                <div class="bg-slate-800 p-4 rounded-xl">CPU: {{cpu}}%</div>
            </div>
            <form action="/gen" method="POST" class="bg-slate-800 p-6 rounded-xl mb-8">
                <h2 class="font-bold mb-3">🔑 Generate VIP Key</h2>
                <input type="number" name="d" placeholder="Days" class="bg-slate-700 p-2 rounded w-full mb-3" required>
                <button class="bg-indigo-600 w-full py-2 rounded font-bold">GENERATE</button>
            </form>
            <div class="bg-slate-800 p-6 rounded-xl">
                <h2 class="font-bold mb-3">👤 VIP Users</h2>
                <table class="w-full text-left text-sm">
                    <tr class="border-b border-slate-700"><th>UID</th><th>Expiry</th></tr>
                    {% for u in users %}
                    <tr class="border-b border-slate-700/50"><td class="py-2">{{u.uid}}</td><td>{{u.exp}}</td></tr>
                    {% endfor %}
                </table>
            </div>
        </div>
    </body></html>
    """, total_u=len(users), cpu=psutil.cpu_percent(), users=users, uptime=uptime)

@web_app.route('/gen', methods=['POST'])
def web_gen():
    if not session.get('adm'): return redirect(url_for('login'))
    days = int(request.form.get('d', 30))
    key = f"VIP-{random.randint(100,999)}-{random.randint(100,999)}"
    col_keys.insert_one({"key": key, "days": days, "slots": 1})
    return f"<h3>Key: {key}</h3><a href='/'>Back</a>"

# --- ৫. টেলিগ্রাম বট হ্যান্ডলার ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_staff(uid):
        kb = [[InlineKeyboardButton("📱 Open Admin Web-App", web_app=WebAppInfo(url=MINI_APP_URL))]]
        await update.message.reply_text("🖥 **ADMIN PANEL ACTIVATED**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    is_v, exp = await check_vip(uid)
    if is_v:
        await update.message.reply_text(f"✅ **VIP ACTIVE**\n⏳ Expiry: `{exp.strftime('%Y-%m-%d')}`\nType `video`", parse_mode='Markdown')
    else:
        kb = [[InlineKeyboardButton("🔞 Watch Demos", callback_data="demos")],
              [InlineKeyboardButton("💳 Buy VIP Key", url=f"https://t.me/{ADMIN_USERNAME[1:]}")]]
        await update.message.reply_photo(photo="https://files.catbox.moe/r4z7sh.jpg", 
                                         caption="👑 **BIJAI PREMIUM**\n\n১০,০০০+ ভিডিও দেখতে VIP কি প্রয়োজন।", reply_markup=InlineKeyboardMarkup(kb))

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    is_v, _ = await check_vip(uid)
    if not is_v and not is_staff(uid): await start(update, context); return

    msg = await update.message.reply_text("🎥 খোঁজা হচ্ছে...")
    batch = scrape_batch()
    random.shuffle(batch)
    
    for v in batch:
        hist = col_history.find_one({"uid": uid, "url": v['u']})
        if hist and time.time() - hist['t'] < 172800: continue
        
        clean = get_clean_link(v['u'])
        if clean:
            col_history.update_one({"uid": uid, "url": v['u']}, {"$set": {"t": time.time()}}, upsert=True)
            caption = f"🎬 **{v['t']}**\n🛡️ VIP Ad-Free ✅\n\n▶️ [Watch Now]({clean})"
            try:
                await update.message.reply_photo(photo=v['i'] or "https://via.placeholder.com/400", caption=caption, parse_mode='Markdown')
                await msg.delete(); return
            except:
                await update.message.reply_text(caption, parse_mode='Markdown'); return
    await msg.edit_text("🕒 পরে চেষ্টা করুন।")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data == "demos":
        for d in DEMO_VIDEOS:
            clean = get_clean_link(d['u'])
            if clean: await query.message.reply_text(f"🎬 **{d['t']}**\n▶️ [Watch Demo]({clean})", parse_mode='Markdown')

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ki = context.args[0]
        key_data = col_keys.find_one({"key": ki})
        if key_data:
            exp = (datetime.now() + timedelta(days=key_data['days'])).strftime("%Y-%m-%d %H:%M:%S")
            col_users.update_one({"uid": str(update.effective_user.id)}, {"$set": {"exp": exp}}, upsert=True)
            col_keys.delete_one({"key": ki})
            await update.message.reply_text("🎉 VIP Activated!")
        else: await update.message.reply_text("❌ Invalid Key!")
    except: await update.message.reply_text("/redeem KEY")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    threading.Thread(target=lambda: web_app.run(host='0.0.0.0', port=port)).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("video", video_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), video_handler))
    app.run_polling()
