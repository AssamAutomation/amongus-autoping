import os
import time
import json
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask
# fix refresh
# force redeploy 2
# ==============================
# CONFIG
# ==============================
TARGET_URL = "https://gurge44.pythonanywhere.com/lobbies"
HOST_NAME = "ARIJIT18"        # your host name in-game
WEBHOOK = os.getenv("DISCORD_WEBHOOK")
POLL_SEC = 5
STATE_FILE = "last_seen.json"

# ==============================
# FLASK SERVER (Keepalive)
# ==============================
app = Flask(__name__)

@app.get("/")
def home():
    return "AutoPing alive"


# ==============================
# STATE FUNCTIONS
# ==============================
def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last_code": None, "last_status": None}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except:
        pass


# ==============================
# SCRAPING
# ==============================
def clean_code_cell(td):
    txt = " ".join(td.stripped_strings)
    return txt.replace("Copy", "").strip()

def scrape_lobby():
    r = requests.get(TARGET_URL, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find("table")
    if not table:
        return None

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    idx = {h: i for i, h in enumerate(headers)}

    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        host = tr.find_all("td")[idx["Host"]].get_text(strip=True)
        if host.lower() == HOST_NAME.lower():
            code = clean_code_cell(tr.find_all("td")[idx["Room Code"]])
            server = tr.find_all("td")[idx["Server"]].get_text(strip=True)
            map_ = tr.find_all("td")[idx["Map"]].get_text(strip=True)
            status = tr.find_all("td")[idx["Status"]].get_text(strip=True)

            return {
                "code": code,
                "server": server,
                "map": map_,
                "status": status,
                "host": host
            }
    return None


# ==============================
# WEBHOOK
# ==============================
def send_webhook(info):
    if not WEBHOOK:
        print("ERROR: DISCORD_WEBHOOK is missing")
        return

    payload = {
        "content": "@everyone",
        "embeds": [{
            "title": f"Among Us Lobby: {info['code']}",
            "description": f"Host: *{info['host']}*",
            "fields": [
                {"name": "Server", "value": info["server"], "inline": True},
                {"name": "Map", "value": info["map"], "inline": True},
                {"name": "Status", "value": info["status"], "inline": True}
            ],
            "footer": {"text": "AutoPing • gurge44.pythonanywhere.com/lobbies"},
            "color": 0x43B581
        }]
    }

    try:
        requests.post(WEBHOOK, json=payload, timeout=10)
        print("Ping sent for", info["code"])
    except Exception as e:
        print("Webhook error:", e)


# ==============================
# WORKER LOOP
# ==============================
def worker():
    state = load_state()

    while True:
        try:
            info = scrape_lobby()
            if info:
                code_changed = info["code"] != state.get("last_code")
                status_changed = info["status"] != state.get("last_status")

                if code_changed or (status_changed and info["status"].lower() == "open"):
                    send_webhook(info)
                    state["last_code"] = info["code"]
                    state["last_status"] = info["status"]
                    save_state(state)

        except Exception as e:
            print("Loop error:", e)

        time.sleep(POLL_SEC)


# ✅ Start worker thread ALWAYS (Gunicorn compatible)
threading.Thread(target=worker, daemon=True).start()
