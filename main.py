import time
import threading
import requests
from flask import Flask
import os

app = Flask(__name__)

# ✅ Your API URL
API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies-json"

# ✅ Your in-game Host Name
TARGET_HOST = "ARIJIT18"

# ✅ Webhook from Render Environment
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

# ✅ Your COOKIE (put exact value from browser DevTools)
COOKIE_VALUE = os.getenv("SITE_COOKIE")   # store cookie in Render environment

# ✅ HEADERS (required to bypass login protection)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://gurge44.pythonanywhere.com/lobbies",
    "Cookie": COOKIE_VALUE
}


# -----------------------------------------------------
# ✅ SEND MESSAGE TO DISCORD
# -----------------------------------------------------
def send_to_discord(message):
    try:
        data = {"content": message}
        r = requests.post(WEBHOOK_URL, json=data, timeout=10)
        print("✅ Discord send status:", r.status_code)
    except Exception as e:
        print("❌ Webhook Error:", e)


# -----------------------------------------------------
# ✅ FETCH LOBBIES + SEARCH YOUR HOSTNAME
# -----------------------------------------------------
def fetch_lobbies_loop():
    print("\n=== FETCH LOOP STARTED ===\n")

    while True:
        try:
            r = requests.get(API_URL, headers=HEADERS, timeout=10)

            raw = r.text
            print("\nRAW RESPONSE (first 200 chars):")
            print(raw[:200])

            data = r.json()

            if not data:
                print("❌ No lobby data found.")
                time.sleep(5)
                continue

            print("\n✅ ALL LOBBIES:")
            print("------------------------------")

            found = False

            # ✅ Loop through ALL lobbies
            for code, info in data.items():
                print(f"Code: {code}")
                print("Host:", info.get("host_name"))
                print("Players:", info.get("players"))
                print("Status:", info.get("status"))
                print("Server:", info.get("server_name"))
                print("Version:", info.get("version"))
                print("------------------------------")

                # ✅ If your host name appears → send webhook
                if info.get("host_name") == TARGET_HOST:
                    msg = (
                        f"✅ **Your Lobby Found!**\n"
                        f"Code: **{code}**\n"
                        f"Server: {info.get('server_name')}\n"
                        f"Players: {info.get('players')}\n"
                        f"Status: {info.get('status')}"
                    )
                    send_to_discord(msg)
                    found = True

            if not found:
                print("❌ Your lobby not found this cycle.")

        except Exception as e:
            print("❌ Error fetching lobby:", e)

        time.sleep(5)  # run loop every 5 seconds


# -----------------------------------------------------
# ✅ FLASK HOMEPAGE
# -----------------------------------------------------
@app.route("/")
def home():
    return "AutoPing alive ✅"


# -----------------------------------------------------
# ✅ START BACKGROUND THREAD
# -----------------------------------------------------
threading.Thread(target=fetch_lobbies_loop, daemon=True).start()


# -----------------------------------------------------
# ✅ RUN FLASK SERVER
# -----------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
