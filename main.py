import os
import requests
import time
import json
import datetime
import threading
import traceback
from zoneinfo import ZoneInfo
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is running."

def run_web():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_web, daemon=True).start()

# ========== Bot config ==========
TOKEN = os.environ.get('TOKEN')
URL = f'https://api.telegram.org/bot{TOKEN}/'
SCHEDULE_FILE = 'schedule.json'
VERSION_FILE = 'version.txt'

LAST_UPDATE_ID = 0
CHAT_ID = None
START_TIME = time.time()
MAX_RUNTIME_MIN = 29400  # 490 ชั่วโมง

LAST_VERSION = ''
VERSION_CHECKED = False

# ========== Functions ==========

def get_updates():
    global LAST_UPDATE_ID
    try:
        resp = requests.get(URL + 'getUpdates', params={'offset': LAST_UPDATE_ID + 1}, timeout=5)
        data = resp.json()
        if data.get('ok'):
            for update in data['result']:
                if 'message' in update:
                    LAST_UPDATE_ID = update['update_id']
                    handle_message(update['message'])
    except Exception as e:
        print("get_updates error:", e)

def send_message(chat_id, text):
    try:
        requests.post(URL + 'sendMessage', data={'chat_id': chat_id, 'text': text})
    except Exception as e:
        print("send_message error:", e)

def load_schedule():
    try:
        with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            data = json.loads(content) if content else []
            for d in data:
                if 'notified' not in d:
                    d['notified'] = False
            return data
    except:
        save_schedule([])
        return []

def save_schedule(lst):
    with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        json.dump(lst, f, ensure_ascii=False)

def add_schedule(time_str, message):
    lst = load_schedule()
    lst.append({'time': time_str, 'message': message, 'notified': False})
    save_schedule(lst)

def check_and_notify():
    global CHAT_ID
    if not CHAT_ID:
        return
    now = datetime.datetime.now(ZoneInfo("Asia/Bangkok")).strftime('%H:%M')
    lst = load_schedule()
    updated = False
    for event in lst:
        if event['time'] == now and not event.get('notified', False):
            send_message(CHAT_ID, f"🔔 แจ้งเตือน: {event['message']}")
            event['notified'] = True
            updated = True
    if updated:
        save_schedule(lst)

def load_version():
    global LAST_VERSION
    try:
        with open(VERSION_FILE, 'r') as f:
            version = f.read().strip()
            if version != LAST_VERSION:
                LAST_VERSION = version
                return version
    except:
        return None

def handle_message(msg):
    global CHAT_ID, VERSION_CHECKED
    text = msg.get('text', '')
    CHAT_ID = msg['chat']['id']

    if not VERSION_CHECKED:
        version = load_version()
        if version:
            send_message(CHAT_ID, f"[ 🆕 ] 9CharnBot อัปเดตเป็นเวอร์ชัน {version} แล้ว!\n• ตรวจสอบฟีเจอร์ใหม่ด้วย /start")
        VERSION_CHECKED = True

    if text == '/start':
        send_message(CHAT_ID, "[ 🤖 ] 9CharnBot \n 👋 ยินดีต้อนรับ! บอทตารางงานพร้อมใช้งานแล้ว\n\n📝 ใช้คำสั่ง:\n• `/add HH:MM ข้อความ`\n• `/list`\n• `/remove N`\n• `/clear`\n• `/status_list`\n\nBot Delay 5 s")
    elif text.startswith('/add '):
        try:
            parts = text[5:].split(' ', 1)
            t, m = parts[0], parts[1]
            datetime.datetime.strptime(t, '%H:%M')
            add_schedule(t, m)
            send_message(CHAT_ID, f"✅ เพิ่มงาน: {t} → {m}")
        except:
            send_message(CHAT_ID, "[ 🤖 ] 9CharnBot : ❌ ใช้รูปแบบ /add HH:MM ข้อความ")
    elif text == '/list':
        lst = load_schedule()
        if lst:
            lines = [f"{i+1}. {e['time']} → {e['message']}" for i, e in enumerate(lst)]
            send_message(CHAT_ID, "[ 🤖 ] 9CharnBot : 📋 ตารางงาน:\n" + "\n".join(lines))
        else:
            send_message(CHAT_ID, "[ 🤖 ] 9CharnBot : 📭 ยังไม่มีตารางงาน")
    elif text == '/status_list':
        lst = load_schedule()
        if lst:
            lines = [f"{i+1}. {e['time']} → {e['message']} ✅" if e.get('notified') else f"{i+1}. {e['time']} → {e['message']} ⏳" for i, e in enumerate(lst)]
            send_message(CHAT_ID, "[ 🤖 ] 9CharnBot : ⏱️ สถานะแจ้งเตือน:\n" + "\n".join(lines))
        else:
            send_message(CHAT_ID, "[ 🤖 ] 9CharnBot : 📭 ยังไม่มีตารางงาน")
    elif text.startswith('/remove '):
        try:
            idx = int(text.split()[1]) - 1
            lst = load_schedule()
            if 0 <= idx < len(lst):
                removed = lst.pop(idx)
                save_schedule(lst)
                send_message(CHAT_ID, f"🗑️ ลบ: {removed['time']} → {removed['message']}")
            else:
                send_message(CHAT_ID, "[ 🤖 ] 9CharnBot : ❌ ไม่พบลำดับนั้น")
        except:
            send_message(CHAT_ID, "[ 🤖 ] 9CharnBot : ❌ ใช้รูปแบบ /remove N")
    elif text == '/clear':
        save_schedule([])
        send_message(CHAT_ID, "[ 🤖 ] 9CharnBot : 🧹 ล้างตารางงานทั้งหมดเรียบร้อยแล้ว")

# ========== Main Loop ==========
def main_loop():
    global CHAT_ID
    print("🤖 Bot started...")
    while True:
        try:
            get_updates()
            check_and_notify()

            lst = load_schedule()
            new_lst = [e for e in lst if not e.get('notified', False)]
            if len(new_lst) != len(lst):
                save_schedule(new_lst)

            runtime_min = (time.time() - START_TIME) / 60
            if runtime_min > MAX_RUNTIME_MIN:
                if CHAT_ID:
                    send_message(CHAT_ID, "[ ⚠️ ] 9CharnBot : บอทกำลังจะหยุดเพื่อประหยัด Railway hours")
                print("⌛ ปิดบอทเพื่อประหยัด Railway hours")
                os._exit(0)

            time.sleep(5)
        except Exception:
            print("❌ Error in main loop:\n" + traceback.format_exc())
            time.sleep(5)

threading.Thread(target=main_loop, daemon=True).start()
