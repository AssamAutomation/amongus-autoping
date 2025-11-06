import os, time, json, threading, requests
from bs4 import BeautifulSoup
from flask import Flask

TARGET_URL = "https://gurge44.pythonanywhere.com/lobbies"
HOST_NAME  = "ARIJIT18"
WEBHOOK    = os.getenv("DISCORD_WEBHOOK")
POLL_SEC   = 5
STATE_FILE = "last_seen.json"

app = Flask(__name__)
@app.get("/")
def home():
    return "AutoPing alive"

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last_code": None, "last_status": None}

def save_state(s):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(s, f)
    except:
        pass

def clean_code_cell(td):
    txt = " ".join(td.stripped_strings)
    return txt.replace("Copy", "").strip()

def scrape_lobby():
    r = requests.get(TARGET_URL, timeout=20)
    r.raise_for_status()
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
        host = tr.find_all("td")[idx.get("Host")].get_text(strip=True)
        if host.lower() == HOST_NAME.lower():
            code = clean_code_cell(tr.find_all("td")[idx.get("Room Code")])
            server = tr.find_all("td")[idx.get("Server")].get_text(strip=True)
            map_ = tr.find_all("td")[idx.get("Map")].get_text(strip=True)
            status = tr.find_all("td")[idx.get("Status")].get_text(strip=True)
            return {"code": code, "server": server, "map": map_, "status": status, "host": host}
    return None

def send_webhook(info):
    if not WEBHOOK:
        print("Missing DISCORD_WEBHOOK")
        return
    payload = {
        "content": "@everyone",
        "embeds": [{
            "title": f"Among Us Lobby: {info['code']}",
            "description": f"Host: **{info['host']}**",
            "fields": [
                {"name": "Server", "value": info["server"], "inline": True},
                {"name": "Map", "value": info["map"], "inline": True},
                {"name": "Status", "value": info["status"], "inline": True},
            ],
            "footer": {"text": "AutoPing • gurge44.pythonanywhere.com/lobbies"},
            "color": 0x43B581
        }]
    }
    try:
        requests.post(WEBHOOK, json=payload, timeout=20)
        print("Ping sent for", info["code"])
    except Exception as e:
        print("Webhook error:", e)

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

    threading.Thread(target=worker, daemon=True).start()
