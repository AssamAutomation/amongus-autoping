import time
import requests
import os
import threading
from flask import Flask

app = Flask(__name__)

API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies-json"
HOST_NAME = "ARIJIT18"   # ✅ your host name

WEBHOOK = os.getenv("DISCORD_WEBHOOK")
COOKIE_VALUE = os.getenv("SITE_COOKIE")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://gurge44.pythonanywhere.com/lobbies",
    "Cookie": COOKIE_VALUE
}

# ✅ anti-spam trackers
last_code = None
last_status = None


# ===============================================================
# ✅ SEND PREMIUM EMBED
# ===============================================================
def send_embed(event_title, code, lobby, extra_message="", color=0xF7E400):
        thumbnail_url = "https://i.imgur.com/1V5ZQog.png"
    banner_url = "https://img.itch.zone/aW1hZ2UvMjU3Njc3LzYyNzc0MTkucG5n/original/oyM651.png"
   # ✅ Option C banner

    embed = {
        "title": f"**{event_title}**",
        "color": color,
        "thumbnail": {"url": thumbnail_url},
        "image": {"url": banner_url},
        "fields": [
            {"name": "🎮 **Join Code**", "value": f"`{code}`", "inline": False},
            {"name": "👤 Host", "value": lobby.get("host_name", "-"), "inline": True},
            {"name": "🌍 Server", "value": lobby.get("server_name", "-"), "inline": True},
            {"name": "👥 Players", "value": str(lobby.get("players", "-")), "inline": True},
            {"name": "🗺 Map", "value": lobby.get("map", "-"), "inline": True},
            {"name": "🎛 Mode", "value": lobby.get("game_mode", "-"), "inline": True},
            {"name": "💾 Version", "value": lobby.get("version", "-"), "inline": True},
        ],
        "footer": {
            "text": "Among Us AutoPing • EHR Tracker • Made for ARIJIT18",
            "icon_url": thumbnail_url
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
        r = requests.post(WEBHOOK, json=payload)
        print(f"✅ Embed sent ({event_title}) | Code: {code} | Status:", r.status_code)
    except Exception as e:
        print("❌ Error sending embed:", e)


# ===============================================================
# ✅ LOGIC LOOP: Scans ALL lobbies 24×7
# ===============================================================
def scan_loop():
    global last_code, last_status

    print("\n✅ AutoPing Started — Running 24×7\n")

    while True:
        try:
            r = requests.get(API_URL, headers=HEADERS, timeout=10)
            data = r.json()
        except Exception as e:
            print("❌ Fetch Error:", e)
            time.sleep(5)
            continue

        my_lobby = None
        my_code = None

        # ✅ Scan every lobby
        for code, info in data.items():
            host = info.get("host_name", "")
            print(f"{code} | Host: {host} | Status: {info.get('status')}")

            if host == HOST_NAME:
                my_lobby = info
                my_code = code

        if not my_lobby:
            print("❌ Your lobby not found.\n")
            time.sleep(5)
            continue

        status = my_lobby.get("status")

        # ✅ NEW LOBBY DETECTED
        if my_code != last_code:
            last_code = my_code
            last_status = status

            send_embed(
                "✅ NEW LOBBY LIVE!",
                my_code,
                my_lobby,
                extra_message="Join quickly before it fills up!",
                color=0x00FF00  # green
            )

        # ✅ GAME START DETECTED
        if last_status == "In Lobby" and status == "In Game":
            last_status = "In Game"

            send_embed(
                "🎮 GAME STARTED!",
                my_code,
                my_lobby,
                extra_message="I'll ping you as soon as the game ends!",
                color=0x3498DB  # blue
            )

        # ✅ GAME END DETECTED
        if last_status == "In Game" and status == "In Lobby":
            last_status = "In Lobby"

            send_embed(
                "🏁 GAME ENDED!",
                my_code,
                my_lobby,
                extra_message="Players returned to lobby. New match ready!",
                color=0xFF00FF  # purple
            )

        time.sleep(5)


# ===============================================================
# ✅ Background Thread + Web Server
# ===============================================================
@app.route("/")
def home():
    return "✅ AutoPing Premium Running 24×7"

threading.Thread(target=scan_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
