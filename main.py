import os
import time
import json
import threading
import requests
from flask import Flask

# =============================
# CONFIG
# =============================

API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies.json"
WEBHOOK = os.getenv("https://discordapp.com/api/webhooks/1436023355353600031/6VYyhrMeMSVk7H2AVczTI3UyI94GtBdUhdLqpp8HT3qF0s0QEOA--oJQL2VB98cD33p1")
POLL_SEC = 5
STATE_FILE = "last_state.json"

# =============================
# FLASK KEEPALIVE SERVER
# =============================

app = Flask(__name__)

@app.route("/")
def home():
    return "AutoPing alive"

# =============================
# STATE LOAD/SAVE
# =============================

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last": []}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except:
        pass

# =============================
# FETCH LOBBIES FROM API
# =============================

def fetch_lobbies():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(API_URL, headers=headers, timeout=10)
        data = resp.json()
        return data    # data is already a list of lobbies
    except Exception as e:
        print("API fetch error:", e)
        return []

# =============================
# SEND WEBHOOK
# =============================

def send_webhook(msg):
    if not WEBHOOK:
        print("No webhook set!")
        return
    try:
        requests.post(WEBHOOK, json={"content": msg})
        print("Sent:", msg)
    except Exception as e:
        print("Webhook error:", e)

# =============================
# PROCESS NEW LOBBIES
# =============================

def process_lobbies():
    state = load_state()
    old_list = state["last"]

    new_list = fetch_lobbies()
    if not new_list:
        print("No data found.")
        return

    # detect only new lobbies
    fresh = [lob for lob in new_list if lob not in old_list]

    for lob in fresh:
        msg = (
            f"✅ **New Lobby Found!**\n"
            f"Code: **{lob['code']}**\n"
            f"Host: **{lob['host']}**\n"
            f"Map: **{lob['map']}**\n"
            f"Status: {lob['status']}\n"
        )
        send_webhook(msg)

    state["last"] = new_list
    save_state(state)

# =============================
# POLLING LOOP
# =============================

def poll_loop():
    while True:
        process_lobbies()
        time.sleep(POLL_SEC)

# start background thread (works in gunicorn)
threading.Thread(target=poll_loop, daemon=True).start()

# Run local
if __name__ == "__main__":
    app.run()
