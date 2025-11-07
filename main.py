import time
import threading
import requests
import json
import os
from flask import Flask

app = Flask(__name__)

API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies-json"
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
HOST_NAME = "ARIJIT18"   # your host name
COOKIE_VALUE = os.getenv("SITE_COOKIE")  # store your cookie safely in Render

last_sent_code = None  # avoid spam


def send_webhook(lobby):
    """Send embed to Discord with custom design + auto delete"""

    code = lobby.get("code", "UNKNOWN")
    host = lobby.get("host_name", "?")
    server = lobby.get("server_name", "?")
    players = lobby.get("players", "?")
    mapname = lobby.get("map", "?")
    version = lobby.get("version", "?")
    mode = lobby.get("game_mode", "?")

    embed = {
        "embeds": [
            {
                "title": "🚀✅ NEW LOBBY LIVE!",
                "description": "**🎮 JOIN CODE (Tap to Copy)**\n```" + code + "```",
                "color": 0x2ecc71,  # green
                "thumbnail": {
                    "url": "https://alfabetajuega.com/hero/2021/01/among-us-1.jpg?width=768&aspect_ratio=16:9&format=nowebp"
                },
                "image": {
                    "url": "https://cdn.aptoide.com/imgs/d/4/6/d460a63e167a534bc7b9e4f1eaeed7dc_fgraphic.png"
                },
                "fields": [
                    {"name": "👤 Host", "value": host, "inline": True},
                    {"name": "🌍 Server", "value": server, "inline": True},
                    {"name": "🧑‍🤝‍🧑 Players", "value": str(players), "inline": True},
                    {"name": "🗺 Map", "value": mapname, "inline": True},
                    {"name": "⚙️ Game Mode", "value": mode, "inline": True},
                    {"name": "📌 Version", "value": version, "inline": True}
                ]
            }
        ]
    }

    # Send message
    r = requests.post(WEBHOOK_URL, json=embed)
    if r.status_code != 204 and r.status_code != 200:
        print("❌ Webhook send error:", r.text)
        return None

    # Fetch message ID for auto delete
    message = None
    try:
        message = r.json()
    except:
        pass

    # Auto delete not supported directly for webhooks unless interaction is returned
    # So we send a delete request manually using Discord API format
    if message and "id" in message:
        msg_id = message["id"]
        delete_url = WEBHOOK_URL + f"/messages/{msg_id}"

        def delete_later(mid):
            time.sleep(120)
            try:
                requests.delete(delete_url)
            except:
                pass

        threading.Thread(target=delete_later, args=(msg_id,), daemon=True).start()

    print("✅ Webhook sent:", code)


def fetch_loop():
    global last_sent_code

    print("✅ FETCH LOOP STARTED")
    headers = {"Cookie": COOKIE_VALUE}

    while True:
        try:
            r = requests.get(API_URL, headers=headers, timeout=10)
            data = r.json()

            # Loop all lobbies
            for code, lobby in data.items():
                host = lobby.get("host_name", "")

                # Only send if your lobby appears
                if host.upper() == HOST_NAME.upper():

                    # avoid duplicate spam
                    if last_sent_code == code:
                        continue

                    last_sent_code = code
                    print(f"✅ FOUND YOUR LOBBY: {code}")
                    send_webhook({"code": code, **lobby})
                    break

        except Exception as e:
            print("❌ Error:", e)

        time.sleep(5)  # fetch every 5 sec


# Start background thread
threading.Thread(target=fetch_loop, daemon=True).start()


@app.route("/")
def home():
    return "AutoPing ✅ Running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
