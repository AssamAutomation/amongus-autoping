import time
import threading
import requests
from flask import Flask

app = Flask(__name__)

API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html,*/*",
    "Referer": "https://gurge44.pythonanywhere.com/lobbies",
}

def fetch_latest_lobby():
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        print("RAW RESPONSE:", r.text[:200])     # Debug print
        
        data = r.json()  # ← previously failing

        if not data:
            print("❌ No lobby data found.")
            return

        first_code = list(data.keys())[0]
        lobby = data[first_code]

        print("\n✅ Latest Lobby Found")
        print("Code:", first_code)
        print("Host:", lobby.get("host_name"))
        print("Players:", lobby.get("players"))
        print("Status:", lobby.get("status"))
        print("Server:", lobby.get("server_name"))
        print("Version:", lobby.get("version"))
        print()

    except Exception as e:
        print("❌ Error fetching:", e)

@app.route("/")
def home():
    return "Fetcher running"

def background_loop():
    while True:
        fetch_latest_lobby()
        time.sleep(5)

threading.Thread(target=background_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
