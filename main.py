import os
import time
import threading
import requests
from flask import Flask

# --------------------------
# CONFIG
# --------------------------
API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies"
COOKIE = os.getenv("SITE_COOKIE")  # Your cookie in render env
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")  # Your Discord Webhook
TARGET_HOST = "ARIJIT18"  # Your host name
last_sent_code = None

# Web headers
headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0"
}

# Flask keep-alive server
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running ✅"

# --------------------------
# Fetch lobby data
# --------------------------
def fetch_lobbies():
    try:
        r = requests.get(API_URL, headers=headers, timeout=10)
        return r.json()
    except Exception as e:
        print("Error fetching:", e)
        return {}

# --------------------------
# Build Discord Embed
# --------------------------
def build_embed(lobby_code, host, server, players, map_name, gamemode, version):
    return {
        "title": "🚀✅ NEW LOBBY LIVE!",
        "color": 5763719,
        "thumbnail": {
            "url": "https://cdn.aptoide.com/imgs/d/4/6/d460a63e167a534bc7b9e4f1eaeed7dc_fgraphic.png"
        },
        "image": {
            "url": "https://alfabetajuega.com/hero/2021/01/among-us-1.jpg?width=768&aspect_ratio=16:9&format=nowebp"
        },
        "fields": [
            {
                "name": "🎮 JOIN CODE (Tap to Copy)",
                "value": lobby_code,   # PERFECT copy fix
                "inline": False
            },
            {
                "name": "👤 Host",
                "value": host,
                "inline": True
            },
            {
                "name": "🌍 Server",
                "value": server,
                "inline": True
            },
            {
                "name": "👥 Players",
                "value": str(players),
                "inline": True
            },
            {
                "name": "🗺 Map",
                "value": map_name,
                "inline": True
            },
            {
                "name": "🛠 Game Mode",
                "value": gamemode,
                "inline": True
            },
            {
                "name": "📌 Version",
                "value": version,
                "inline": True
            }
        ]
    }

# --------------------------
# Monitoring Loop (24/7)
# --------------------------
def monitor_loop():
    global last_sent_code

    print("✅ Monitoring started...")

    while True:
        data = fetch_lobbies()

        if not data:
            time.sleep(5)
            continue

        # Loop through ALL lobbies (not just first one)
        for code, lobby in data.items():
            host = lobby.get("host_name", "")

            # Check if this is YOUR lobby
            if host.upper() == TARGET_HOST.upper():

                # If the same code was already sent, ignore
                if last_sent_code == code:
                    continue

                # New lobby found → send!
                last_sent_code = code

                server = lobby.get("server_name", "?")
                players = lobby.get("players", "?")
                map_name = lobby.get("map", "?")
                gamemode = lobby.get("game_mode", "?")
                version = lobby.get("version", "?")

                embed = build_embed(code, host, server, players, map_name, gamemode, version)

                # Send message
                requests.post(
                    WEBHOOK_URL,
                    json={
                        "content": "@everyone",
                        "embeds": [embed]
                    }
                )

                print("✅ Sent lobby:", code)

                # Auto-delete after 2 mins (Discord handles this)
                requests.post(
                    WEBHOOK_URL + "?wait=true",
                    json={
                        "content": "🗑 This lobby alert will auto-delete in **2 minutes**.",
                    }
                )

        time.sleep(5)

# --------------------------
# Start background thread
# --------------------------
def start_monitor():
    t = threading.Thread(target=monitor_loop)
    t.daemon = True
    t.start()

start_monitor()
