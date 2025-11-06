import time
import threading
import requests
from flask import Flask
import os

app = Flask(__name__)

API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies-json"

TARGET_HOST = "ARIJIT18"

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

COOKIE_VALUE = os.getenv("SITE_COOKIE")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://gurge44.pythonanywhere.com/lobbies",
    "Cookie": COOKIE_VALUE
}

def send_to_discord(message):
    try:
        r = requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
        print("✅ Discord Response:", r.status_code)
    except Exception as e:
        print("❌ Webhook Error:", e)

def fetch_lobbies_loop():
    print("\n=== FETCH LOOP STARTED ===")

    while True:
        try:
            r = requests.get(API_URL, headers=HEADERS, timeout=10)

            raw = r.text
            print("\nRAW RESPONSE (first 200 chars):")
            print(raw[:200])

            data = r.json()

            if not data:
                print("❌ No lobbies found.")
                time.sleep(5)
                continue

            found_my_lobby = False

            print("\n✅ LIST OF ALL LOBBIES:")
            print("------------------------------------")

            # ✅ LOOP THROUGH *EVERY* LOBBY
            for code, info in data.items():
                print(f"Code: {code}")
                print("Host:", info.get("host_name"))
                print("Players:", info.get("players"))
                print("Status:", info.get("status"))
                print("Server:", info.get("server_name"))
                print("Version:", info.get("version"))
                print("------------------------------------")

                # ✅ CHECK IF THIS IS YOUR LOBBY
                if info.get("host_name") == TARGET_HOST:
                    found_my_lobby = True
                    message = (
                        f"✅ **Your Lobby Found!**\n"
                        f"Code: **{code}**\n"
                        f"Server: {info.get('server_name')}\n"
                        f"Players: {info.get('players')}\n"
                        f"Status: {info.get('status')}"
                    )
                    send_to_discord(message)

            if not found_my_lobby:
                print("❌ Your lobby not found this cycle.")

        except Exception as e:
            print("❌ Fetch Error:", e)

        time.sleep(5)

@app.route("/")
def home():
    return "AutoPing alive ✅"

threading.Thread(target=fetch_lobbies_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
