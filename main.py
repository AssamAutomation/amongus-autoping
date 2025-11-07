import time
import json
import threading
import requests
import os
from flask import Flask

app = Flask(__name__)

# ==============================
# CONFIG
# ==============================
API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies-json"
HOST_NAME = "ARIJIT18"

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
COOKIE_DATA = os.getenv("SITE_COOKIE")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://gurge44.pythonanywhere.com/lobbies",
    "Cookie": COOKIE_DATA
}

# anti-spam
last_code = None
last_status = None


# ==============================
# DELETE MESSAGE AFTER 2 MINS
# ==============================
def delete_message_later(webhook, msg_id):
    time.sleep(900)
    try:
        requests.delete(f"{webhook}/messages/{msg_id}")
        print("🗑 Deleted old message:", msg_id)
    except:
        print("⚠ Could not delete message")


# ==============================
# SEND EMBED
# ==============================
def send_embed(event_title, code, lobby, extra_message=""):

    # ✅ remove backticks — only CODE gets copied
    display_code = code if code != "-" else "NO CODE"

    banner_url = "https://alfabetajuega.com/hero/2021/01/among-us-1.jpg?width=768&aspect_ratio=16:9&format=nowebp"
    thumb_url = "https://cdn.aptoide.com/imgs/d/4/6/d460a63e167a534bc7b9e4f1eaeed7dc_fgraphic.png"

    embed = {
        "title": event_title,
        "color": 0xF7E7A6,
        "thumbnail": {"url": thumb_url},
        "image": {"url": banner_url},
        "fields": [
            {
                "name": "🎮 JOIN CODE (Tap to Copy)",
                "value": display_code,   # ✅ only the code, no ``` no commas
                "inline": False
            },
            {"name": "👤 Host", "value": lobby.get("host_name", "-"), "inline": True},
            {"name": "🌍 Server", "value": lobby.get("server_name", "-"), "inline": True},
            {"name": "👥 Players", "value": str(lobby.get("players", "-")), "inline": True},
            {"name": "🗺 Map", "value": lobby.get("map", "-"), "inline": True},
            {"name": "🎛 Mode", "value": lobby.get("game_mode", "-"), "inline": True},
            {"name": "💾 Version", "value": lobby.get("version", "-"), "inline": True},
        ],
        "footer": {
            "text": "Among Us AutoPing • ARIJIT18 Host",
            "icon_url": thumb_url
        }
    }

    if extra_message:
        embed["fields"].append({
            "name": "📢 Update",
            "value": extra_message,
            "inline": False
        })

    payload = {
        "content": "@everyone",
        "embeds": [embed]
    }

    try:
        r = requests.post(WEBHOOK_URL + "?wait=true", json=payload)
        print("✅ Embed sent:", r.status_code)

        if r.status_code == 200:
            msg_id = r.json()["id"]
            threading.Thread(
                target=delete_message_later,
                args=(WEBHOOK_URL, msg_id),
                daemon=True
            ).start()

    except Exception as e:
        print("❌ Webhook send error:", e)


# ==============================
# FETCH LOOP (SCANS ALL LOBBIES)
# ==============================
def fetch_loop():
    global last_code, last_status

    while True:
        try:
            r = requests.get(API_URL, headers=HEADERS, timeout=10)
            data = r.json()

            # ✅ show all lobbies in log
            print("------ All lobbies ------")
            for code, lobby in data.items():
                print(code, "=>", lobby.get("host_name"), lobby.get("status"))

            # ✅ check your host lobbies
            for code, lobby in data.items():

                if lobby.get("host_name") != HOST_NAME:
                    continue

                status = lobby.get("status")

                # NEW LOBBY
                if code != last_code:
                    send_embed("🚀✅ NEW LOBBY LIVE!", code, lobby)
                    last_code = code
                    last_status = status
                    print("✅ NEW LOBBY:", code)
                    continue

                # GAME STARTED
                if last_status == "In Lobby" and status == "In Game":
                    send_embed("🟥 Game Started!", code, lobby, "I'll ping you when it ends.")
                    last_status = status
                    print("🎮 Game started")
                    continue

                # GAME ENDED
                if last_status == "In Game" and status == "In Lobby":
                    send_embed("🟩 Game Ended!", code, lobby, "You may join again.")
                    last_status = status
                    print("✅ Game ended")
                    continue

            time.sleep(5)

        except Exception as e:
            print("❌ Fetch error:", e)
            time.sleep(5)


# ==============================
# FLASK ROUTE
# ==============================
@app.route("/")
def home():
    return "✅ AutoPing is running..."


# ==============================
# BACKGROUND THREAD
# ==============================
def start_background():
    t = threading.Thread(target=fetch_loop, daemon=True)
    t.start()


# ✅ Start on boot
start_background()
