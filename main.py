import os
import time
import threading
import requests
from flask import Flask

app = Flask(__name__)

API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies-json"

# ✅ Load your cookie from Render environment
COOKIE = os.getenv("GURGE_COOKIE", "")

# ✅ Required headers (same as browser)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://gurge44.pythonanywhere.com/lobbies",
    "Origin": "https://gurge44.pythonanywhere.com",
}

# ✅ Add cookie if we have it
if COOKIE:
    HEADERS["Cookie"] = COOKIE

# ✅ Use session (browser-like)
session = requests.Session()
session.headers.update(HEADERS)

def fetch_latest_lobby():
    try:
        print("FETCHING...")
        r = session.get(API_URL, timeout=12)

        print("RAW =", r.text[:200])  # <--- VERY IMPORTANT

        data = r.json()   # ✅ This will work only if cookie is correct

        if not data:
            print("❌ No lobby data.")
            return
        
        first_code = list(data.keys())[0]
        lobby = data[first_code]

        print("\n✅ LATEST LOBBY")
        print("Code:", first_code)
        print("Host:", lobby.get("host_name"))
        print("Players:", lobby.get("players"))
        print("Status:", lobby.get("status"))
        print("Server:", lobby.get("server_name"))
        print("Version:", lobby.get("version"))
        print("----------------------------------")

    except Exception as e:
        print("❌ Error fetching lobby:", e)

def background_loop():
    print("=== FETCH LOOP STARTED ===")
    while True:
        fetch_latest_lobby()
        time.sleep(10)

@app.route("/")
def home():
    return "Fetcher running ✅"

# ✅ Start background thread
threading.Thread(target=background_loop, daemon=True).start()
