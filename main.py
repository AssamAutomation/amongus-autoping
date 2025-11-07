import time
import json
import threading
import requests
import os
from collections import deque
from flask import Flask

app = Flask(__name__)

# ==============================
# CONFIG
# ==============================
API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies-json"
HOST_NAME = "ARIJITHOST"

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
COOKIE_DATA = os.getenv("SITE_COOKIE")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://gurge44.pythonanywhere.com/lobbies",
    "Cookie": COOKIE_DATA
}

RENDER_URL = "https://amongus-autoping.onrender.com/"

# ==============================
# FAST-MODE SETTINGS
# ==============================
CODE_STABILITY_POLLS = 1        # instant detect
STATUS_STABILITY_POLLS = 1      # instant detect
GLOBAL_COOLDOWN_SEC = 20        # faster announcements
PLAYER_UPDATE_MIN_GAP = 2       # fast player updates
REPEAT_CODE_SUPPRESS_SEC = 600
OFFLINE_DELETE_SEC = 20 * 60

STATE_FILE = "last_state.json"

state_lock = threading.Lock()
last_code = None
last_status = None
last_players = None
last_msg_id = None
last_sent_ts = 0
last_player_sent_ts = 0
last_seen_host_ts = 0
recent_codes = deque(maxlen=10)

observed_code = None
observed_code_count = 0
observed_status = None
observed_status_count = 0

# ==============================
# STATE LOAD/SAVE
# ==============================
def load_state():
    global last_code, last_status, last_players, last_msg_id
    global last_sent_ts, last_player_sent_ts, last_seen_host_ts, recent_codes

    if not os.path.exists(STATE_FILE):
        return

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)

        last_code = data.get("last_code")
        last_status = data.get("last_status")
        last_players = data.get("last_players")
        last_msg_id = data.get("last_msg_id")
        last_sent_ts = data.get("last_sent_ts", 0)
        last_player_sent_ts = data.get("last_player_sent_ts", 0)
        last_seen_host_ts = data.get("last_seen_host_ts", 0)

        rc = data.get("recent_codes", [])
        cutoff = time.time() - REPEAT_CODE_SUPPRESS_SEC
        rc = [x for x in rc if x.get("ts", 0) >= cutoff]

        recent_codes.clear()
        for x in rc:
            recent_codes.append(x)

        print("✅ Loaded state")

    except:
        print("⚠ Failed loading state, starting new.")


def save_state():
    try:
        data = {
            "last_code": last_code,
            "last_status": last_status,
            "last_players": last_players,
            "last_msg_id": last_msg_id,
            "last_sent_ts": last_sent_ts,
            "last_player_sent_ts": last_player_sent_ts,
            "last_seen_host_ts": last_seen_host_ts,
            "recent_codes": list(recent_codes)
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except:
        print("⚠ State save error")


def code_recently_announced(code):
    now = time.time()
    while recent_codes and now - recent_codes[0]["ts"] > REPEAT_CODE_SUPPRESS_SEC:
        recent_codes.popleft()

    for item in recent_codes:
        if item["code"] == code:
            return True
    return False


def remember_code(code):
    recent_codes.append({"code": code, "ts": time.time()})


# ==============================
# DISCORD HELPERS
# ==============================
def delete_message(msg_id):
    if not msg_id:
        return
    try:
        requests.delete(f"{WEBHOOK_URL}/messages/{msg_id}", timeout=10)
        print("🗑 Deleted old message")
    except:
        print("⚠ Delete failed")


def title_for(status, players):
    p = int(players or 0)

    if status == "In Game":
        return f"🟥 Game Started! ({p}/15)"
    else:
        return f"🚀✅ NEW LOBBY LIVE! ({p}/15)"  # ALWAYS show this for lobby


def build_embed(event_title, code, lobby):
    display_code = code.strip() if code else "NO CODE"

    banner = "https://alfabetajuega.com/hero/2021/01/among-us-1.jpg?width=768&aspect_ratio=16:9&format=nowebp"
    thumb = "https://cdn.aptoide.com/imgs/d/4/6/d460a63e167a534bc7b9e4f1eaeed7dc_fgraphic.png"

    return {
        "title": event_title,
        "color": 0xF7E7A6,
        "thumbnail": {"url": thumb},
        "image": {"url": banner},
        "fields": [
            {"name": "🎮 JOIN CODE", "value": display_code, "inline": False},
            {"name": "👤 Host", "value": lobby.get("host_name"), "inline": True},
            {"name": "🌍 Server", "value": lobby.get("server_name"), "inline": True},
            {"name": "👥 Players", "value": str(lobby.get("players")), "inline": True},
            {"name": "🗺 Map", "value": lobby.get("map"), "inline": True},
            {"name": "🎛 Mode", "value": lobby.get("game_mode"), "inline": True},
            {"name": "💾 Version", "value": lobby.get("version"), "inline": True},
            {"name": "📌 Status", "value": lobby.get("status"), "inline": True},
        ],
        "footer": {"text": "Among Us AutoPing • ARIJIT18 Host", "icon_url": thumb}
    }


def send_embed_and_get_id(title, code, lobby, *, bypass_cooldown=False, is_player=False):
    global last_sent_ts, last_player_sent_ts

    now = time.time()

    if is_player:
        if now - last_player_sent_ts < PLAYER_UPDATE_MIN_GAP:
            return None
    else:
        if not bypass_cooldown and now - last_sent_ts < GLOBAL_COOLDOWN_SEC:
            return None

    payload = {"content": "@everyone", "embeds": [build_embed(title, code, lobby)]}

    try:
        r = requests.post(WEBHOOK_URL + "?wait=true", json=payload, timeout=10)
        if r.status_code == 200:
            msg_id = r.json()["id"]
            if is_player:
                last_player_sent_ts = now
            else:
                last_sent_ts = now
            return msg_id
        return None
    except:
        return None


# ==============================
# LOBBY PICKING
# ==============================
def select_host_lobby(data):
    best = None
    best_score = -999

    for code, lobby in data.items():
        if lobby.get("host_name") != HOST_NAME:
            continue

        players = int(lobby.get("players") or 0)
        status = lobby.get("status")

        score = players
        if code not in ("", "-"):
            score += 10
        if status == "In Game":
            score += 5

        if score > best_score:
            best_score = score
            best = (code, lobby)

    return best if best else (None, None)


# ==============================
# MAIN LOGIC LOOP
# ==============================
def fetch_loop():
    global last_code, last_status, last_players, last_msg_id
    global last_seen_host_ts, observed_code, observed_code_count
    global observed_status, observed_status_count

    while True:
        try:
            r = requests.get(API_URL, headers=HEADERS, timeout=10)
            data = r.json()

            code, lobby = select_host_lobby(data)

            if not lobby:
                if last_msg_id:
                    delete_message(last_msg_id)
                    last_msg_id = None
                    save_state()
                time.sleep(5)
                continue

            last_seen_host_ts = time.time()

            status = lobby.get("status")
            players = int(lobby.get("players") or 0)

            # Stability
            observed_code_count = observed_code_count + 1 if code == observed_code else 1
            observed_code = code
            code_stable = observed_code_count >= CODE_STABILITY_POLLS

            observed_status_count = observed_status_count + 1 if status == observed_status else 1
            observed_status = status
            status_stable = observed_status_count >= STATUS_STABILITY_POLLS

            with state_lock:

                # NEW LOBBY
                if code_stable and code != last_code:
                    if not code_recently_announced(code):
                        if last_msg_id:
                            delete_message(last_msg_id)
                            last_msg_id = None

                        title = title_for(status, players)
                        msg_id = send_embed_and_get_id(title, code, lobby)

                        if msg_id:
                            last_msg_id = msg_id
                            last_code = code
                            last_status = status
                            last_players = players
                            remember_code(code)
                            save_state()

                # STATUS CHANGE
                elif code_stable and status_stable and status != last_status:
                    if last_msg_id:
                        delete_message(last_msg_id)
                        last_msg_id = None

                    # Always NEW LOBBY LIVE for lobby status
                    title = title_for(status, players)
                    msg_id = send_embed_and_get_id(title, code, lobby)

                    if msg_id:
                        last_msg_id = msg_id
                        last_status = status
                        last_players = players
                        save_state()

                # PLAYER COUNT CHANGE
                elif (
                    code_stable and status_stable and players != last_players
                    and last_code == code and last_players is not None
                ):
                    if last_msg_id:
                        delete_message(last_msg_id)
                        last_msg_id = None

                    title = title_for(status, players)
                    msg_id = send_embed_and_get_id(
                        title, code, lobby,
                        bypass_cooldown=True,
                        is_player=True
                    )

                    if msg_id:
                        last_msg_id = msg_id
                        last_players = players
                        save_state()

                # INITIAL MESSAGE
                elif last_msg_id is None and code_stable:
                    title = title_for(status, players)
                    msg_id = send_embed_and_get_id(title, code, lobby)

                    if msg_id:
                        last_msg_id = msg_id
                        last_code = code
                        last_status = status
                        last_players = players
                        remember_code(code)
                        save_state()

            time.sleep(5)

        except Exception as e:
            print("Fetch error:", e)
            time.sleep(5)


# ==============================
# WATCHDOG (20 MIN OFFLINE)
# ==============================
def offline_watchdog():
    global last_msg_id, last_seen_host_ts

    while True:
        try:
            now = time.time()
            if last_msg_id and last_seen_host_ts and now - last_seen_host_ts >= OFFLINE_DELETE_SEC:
                delete_message(last_msg_id)
                last_msg_id = None
                save_state()
        except:
            pass

        time.sleep(60)


# ==============================
# KEEP-ALIVE
# ==============================
def keep_alive():
    while True:
        try:
            requests.get(RENDER_URL, timeout=5)
        except:
            pass
        time.sleep(240)


# ==============================
# FLASK ROUTE
# ==============================
@app.route("/")
def home():
    return "✅ AutoPing is running..."


# ==============================
# STARTUP
# ==============================
def start_background():
    load_state()
    threading.Thread(target=fetch_loop, daemon=True).start()
    threading.Thread(target=offline_watchdog, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()


start_background()
