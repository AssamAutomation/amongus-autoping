import time
import requests

API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies.json"

def fetch_latest_lobby():
    try:
        r = requests.get(API_URL, timeout=10)
        data = r.json()

        if not data:
            print("❌ No lobby data found.")
            return

        # Get first lobby (latest)
        first_code = list(data.keys())[0]
        lobby = data[first_code]

        print("\n✅ Latest Lobby Found")
        print("Code:", first_code)
        print("Host:", lobby.get("host_name"))
        print("Players:", lobby.get("players"))
        print("Status:", lobby.get("status"))
        print("Server:", lobby.get("server_name"))
        print("Version:", lobby.get("version"))
        print("----------------------------")

    except Exception as e:
        print("❌ Error fetching lobby:", e)

print("=== Fetch Test Started ===")

while True:
    fetch_latest_lobby()
    time.sleep(10)   # fetch every 10 seconds
