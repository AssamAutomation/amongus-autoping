import os
import time
import json
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask

# ============================
# CONFIG
# ============================

TARGET_URL = "https://gurge44.pythonanywhere.com/lobbies"  # ✅ correct lobby site
WEBHOOK = os.getenv("https://discordapp.com/api/webhooks/1436023355353600031/6VYyhrMeMSVk7H2AVczTI3UyI94GtBdUhdLqpp8HT3qF0s0QEOA--oJQL2VB98cD33p1")   # ✅ stored in Render environment variable
POLL_SEC = 5
STATE_FILE = "last_state.json"

# ============================
# FLASK SERVER (Keepalive)
# ============================

app = Flask(__name__)

@app.route("/")
def home():
    return "AutoPing alive"


# ============================
# STATE SAVE / LOAD
# ============================

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last_lobbies": []}


def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except:
        pass


# ============================
# SCRAPING ALL LOBBIES
# ============================

def scrape_lobbies():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(TARGET_URL, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.find("table")
        if not table:
            print("No table found on website.")
            return []

        lobbies = []
        rows = table.find_all("tr")[1:]   # skip header row

        for r in rows:
            cols = [c.text.strip() for c in r.find_all("td")]
            if len(cols) < 3:
                continue

            lobby_code = cols[0]
            host = cols[1]
            status = cols[-1]

            lobbies.append({
                "code": lobby_code,
                "host": host,
                "status": status
            })

        return lobbies

    except Exception as e:
        print("Scraping error:", e)
        return []


# ============================
# SEND MESSAGE TO WEBHOOK
# ============================

def send_webhook(msg):
    if not WEBHOOK:
        print("Webhook missing!")
        return

    data = {
        "content": msg
    }

    try:
        requests.post(WEBHOOK, json=data)
        print("Ping sent:", msg)
    except Exception as e:
        print("Webhook error:", e)


# ============================
# PROCESS LOBBIES
# ============================

def process_lobbies():
    state = load_state()
    old = state["last_lobbies"]

    lobbies = scrape_lobbies()
    if not lobbies:
        print("No lobbies found")
        return

    # Only send new lobbies that were not in the last cycle
    new_lobbies = [x for x in lobbies if x not in old]

    for lob in new_lobbies:
        msg = f"✅ **Lobby Found!**\nCode: **{lob['code']}**  |  Host: **{lob['host']}**  |  Status: {lob['status']}"
        send_webhook(msg)

    state["last_lobbies"] = lobbies
    save_state(state)


# ============================
# LOOP THREAD
# ============================

def poll_loop():
    while True:
        process_lobbies()
        time.sleep(POLL_SEC)


# Start scraper thread as soon as app loads (Gunicorn safe)
threading.Thread(target=poll_loop, daemon=True).start()


# ============================
# RUN LOCAL (ignored on Render)
# ============================

if __name__ == "__main__":
    app.run()
