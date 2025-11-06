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

# ✅ prevent repeating same code
last_sent_code = None


def send_to_discord(message):
    try:
        payload = {"content": f"@everyone\n{message}"}
        r = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        print("✅ Discord Response:", r.status_code)
    except Exception as e:
        print("❌ Webhook Error:", e)


def fetch_lobbies_loop():
    global last_sent_code

    print("\n=== FETCH LOOP STARTED ✅ ===")

    while True:
        try:
            r = requests.get(API_URL, headers=HEADERS, timeout=10)
            raw = r.text
            print("\nRAW RESPONSE (first 150 chars):", raw[:150])

            data = r.json()
            if not data:
                print("❌ No lobbies found.")
                time.sleep(5)
                continue

            print("\n✅ CHECKING ALL LOBBIES...")
            print("------------------------------------")

            my_lobby_found = False
            found_code = None

            # ✅ loop every lobby
            for code, info in data.items():
                host = info.get("host_name")
                print(f"Code={code} | Host={host} | Players={info.get('players')}")

                # ✅ check if this is your lobby
                if host == TARGET_HOST:
                    my_lobby_found = True
                    found_code = code

            # ✅ if your lobby is found
            if my_lobby_found:
                print(f"\n✅ Your Lobby Found: {found_code}")

                # ✅ send only if code is NEW
                if found_code != last_sent_code:
                    print("✅ NEW CODE DETECTED → Sending to Discord")
                    last_sent_code = found_code  # update memory

                    message = (
                        f"✅ **Your Among Us Lobby is LIVE!**\n"
                        f"**Join Code:** `{found_code}`\n"
                        f"Host: {TARGET_HOST}"
                    )
                    send_to_discord(message)
                else:
                    print("🔁 Same code as before → No Discord spam.")
            else:
                print("❌ Your lobby not found this cycle.")

        except Exception as e:
            print("❌ ERROR:", e)

        time.sleep(5)


@app.route("/")
def home():
    return "AutoPing alive ✅"


threading.Thread(target=fetch_lobbies_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
