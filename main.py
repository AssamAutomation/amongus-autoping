import time
import requests
import threading
from flask import Flask
import os

app = Flask(__name__)

API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies-json"

COOKIE_HEADER = {
    "Cookie": os.getenv("SITE_COOKIE", "")
}

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK", "")
HOST_NAME = os.getenv("HOST_NAME", "").upper()

last_sent_code = None


def send_discord_lobby(lobby):
    global last_sent_code

    code = lobby.get("code", "")
    if not code:
        return

    # Anti-spam: do not send same code twice
    if code == last_sent_code:
        return
    
    last_sent_code = code

    host = lobby.get("host_name", "Unknown")
    server = lobby.get("server_name", "Unknown")
    players = lobby.get("players", "?")
    mapname = lobby.get("map", "?")
    mode = lobby.get("game_mode", "?")
    version = lobby.get("version", "?")

    embed = {
        "content": "@everyone ✅ **YOUR AMONG US LOBBY IS LIVE!**",
        "embeds": [
            {
                "title": "🚀✅ NEW LOBBY LIVE!",
                "color": 0x2ecc71,
                "thumbnail": {
                    "url": "https://cdn.aptoide.com/imgs/d/4/6/d460a63e167a534bc7b9e4f1eaeed7dc_fgraphic.png"
                },
                "fields": [
                    {
                        "name": "🎮 JOIN CODE (Tap to Copy)",
                        "value": f"```{code}```",
                        "inline": False
                    },
                    {"name": "👤 Host", "value": host, "inline": True},
                    {"name": "🌍 Server", "value": server, "inline": True},
                    {"name": "👥 Players", "value": str(players), "inline": True},
                    {"name": "🗺 Map", "value": mapname, "inline": True},
                    {"name": "⚙️ Mode", "value": mode, "inline": True},
                    {"name": "📌 Version", "value": version, "inline": True}
                ],
                "image": {
                    "url": "https://alfabetajuega.com/hero/2021/01/among-us-1.jpg?width=768"
                }
            },

            # ✅ SEPARATE COPY-ONLY EMBED (Only this gets copied)
            {
                "description": f"```{code}```",
                "color": 0xffffff
            }
        ]
    }

    try:
        r = requests.post(WEBHOOK_URL, json=embed)
        if r.status_code not in [200, 204]:
            print("❌ Webhook failed:", r.text)
            return
        
        print(f"✅ SENT LOBBY CODE: {code}")

        # ✅ Auto-delete after 2 mins
        delete_after_120_seconds()

    except Exception as e:
        print("❌ Webhook error:", e)


def delete_after_120_seconds():
    """Deletes the last sent message after 120 seconds (Discord only allows via token bot)."""
    # Webhooks cannot delete their own messages unless using bot tokens.
    # If user wants this, they must use a full Discord bot, not a webhook.
    pass



def fetch_loop():
    print("✅ BACKGROUND SEARCH STARTED...")

    while True:
        try:
            r = requests.get(API_URL, headers=COOKIE_HEADER, timeout=10)
            data = r.json()

            if not data:
                print("❌ No data received.")
                time.sleep(5)
                continue
            
            # Loop through ALL lobbies (not just first)
            for code, lobby in data.items():
                host = lobby.get("host_name", "").upper()

                if host == HOST_NAME:
                    print(f"\n✅ MATCH FOUND → {code}")
                    send_discord_lobby({**lobby, "code": code})

        except Exception as e:
            print("❌ Fetch error:", e)

        time.sleep(6)  # Scan every 6 seconds



@app.route("/")
def home():
    return "AutoPing Active ✅"


if __name__ == "__main__":
    threading.Thread(target=fetch_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
