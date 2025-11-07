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
HOST_NAME = "ARIJIT18"

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
COOKIE_DATA = os.getenv("SITE_COOKIE")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://gurge44.pythonanywhere.com/lobbies",
    "Cookie": COOKIE_DATA
}

RENDER_URL = "https://amongus-autoping.onrender.com/"  # your Render URL

# ==============================
# STATE / ANTI-SPAM
# ==============================
STATE_FILE = "last_state.json"

CODE_STABILITY_POLLS = 3          # require same code 3 polls in a row (3*5s = 15s)
STATUS_STABILITY_POLLS = 2        # require same status 2 polls in a row (2*5s = 10s)

GLOBAL_COOLDOWN_SEC = 90          # min gap for code/status announcements
REPEAT_CODE_SUPPRESS_SEC = 600    # don't re-announce same code within 10 minutes

PLAYER_UPDATE_MIN_GAP = 5         # min gap between player updates (allows frequent updates)
OFFLINE_DELETE_SEC = 20 * 60      # delete last message if host unseen for 20 minutes

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
# PERSISTENCE
# ==============================
def load_state():
    global last_code, last_status, last_players, last_msg_id
    global last_sent_ts, last_player_sent_ts, last_seen_host_ts, recent_codes

    if os.path.exists(STATE_FILE):
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
                recent_codes.append({"code": x.get("code"), "ts": x.get("ts", 0)})

            print("Loaded state:", {
                "last_code": last_code,
                "last_status": last_status,
                "last_players": last_players,
                "last_msg_id": last_msg_id,
                "last_sent_ts": last_sent_ts,
                "last_player_sent_ts": last_player_sent_ts,
                "last_seen_host_ts": last_seen_host_ts,
                "recent_codes": list(recent_codes)
            })
        except Exception as e:
            print("State load error, starting fresh:", e)


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
    except Exception as e:
        print("State save error:", e)


def code_recently_announced(code: str):
    now = time.time()
    while recent_codes and (now - recent_codes[0]["ts"] > REPEAT_CODE_SUPPRESS_SEC):
        recent_codes.pop() if False else recent_codes.popleft()
    for item in recent_codes:
        if item["code"] == code and now - item["ts"] <= REPEAT_CODE_SUPPRESS_SEC:
            return True
    return False


def remember_code_announcement(code: str):
    recent_codes.append({"code": code, "ts": time.time()})


# ==============================
# DISCORD HELPERS
# ==============================
def delete_message(msg_id):
    if not msg_id:
        return
    try:
        r = requests.delete(f"{WEBHOOK_URL}/messages/{msg_id}", timeout=10)
        print("🗑 Deleted message:", r.status_code)
    except Exception as e:
        print("⚠ Delete error:", e)


def title_for(status: str, players: int):
    """
    Only two titles by design:
    - In Lobby  -> 🚀✅ NEW LOBBY LIVE! (X/15)
    - In Game   -> 🟥 Game Started! (X/15)

    After game ends (In Game -> In Lobby), this will immediately show NEW LOBBY LIVE.
    """
    p = int(players or 0)
    if status == "In Game":
        return f"🟥 Game Started! ({p}/15)"
    else:
        # Treat all non-In-Game as Lobby (covers In Lobby and any return-to-lobby cases)
        return f"🚀✅ NEW LOBBY LIVE! ({p}/15)"


def build_embed(event_title, code, lobby):
    display_code = (code or "").strip()
    if display_code in ("", "-"):
        display_code = "NO CODE"

    banner = "https://alfabetajuega.com/hero/2021/01/among-us-1.jpg?width=768&aspect_ratio=16:9&format=nowebp"
    thumb = "https://cdn.aptoide.com/imgs/d/4/6/d460a63e167a534bc7b9e4f1eaeed7dc_fgraphic.png"

    embed = {
        "title": event_title,
        "color": 0xF7E7A6,
        "thumbnail": {"url": thumb},
        "image": {"url": banner},
        "fields": [
            {"name": "🎮 JOIN CODE", "value": display_code, "inline": False},
            {"name": "👤 Host", "value": lobby.get("host_name", "-"), "inline": True},
            {"name": "🌍 Server", "value": lobby.get("server_name", "-"), "inline": True},
            {"name": "👥 Players", "value": str(lobby.get("players", "-")), "inline": True},
            {"name": "🗺 Map", "value": lobby.get("map", "-"), "inline": True},
            {"name": "🎛 Mode", "value": lobby.get("game_mode", "-"), "inline": True},
            {"name": "💾 Version", "value": lobby.get("version", "-"), "inline": True},
            {"name": "📌 Status", "value": lobby.get("status", "-"), "inline": True},
        ],
        "footer": {"text": "Among Us AutoPing • ARIJIT18 Host", "icon_url": thumb}
    }

    return embed


def send_embed_and_get_id(title, code, lobby, *, bypass_cooldown=False, is_player=False):
    global last_sent_ts, last_player_sent_ts
    now = time.time()

    if is_player:
        if now - last_player_sent_ts < PLAYER_UPDATE_MIN_GAP:
            print(f"⏳ Player update gap — {int(PLAYER_UPDATE_MIN_GAP - (now - last_player_sent_ts))}s left")
            return None
    else:
        if not bypass_cooldown and (now - last_sent_ts < GLOBAL_COOLDOWN_SEC):
            print(f"⏳ Global cooldown — {int(GLOBAL_COOLDOWN_SEC - (now - last_sent_ts))}s left")
            return None

    payload = {"content": "@everyone", "embeds": [build_embed(title, code, lobby)]}

    try:
        r = requests.post(WEBHOOK_URL + "?wait=true", json=payload, timeout=10)
        if r.status_code == 200:
            msg_id = r.json().get("id")
            if is_player:
                last_player_sent_ts = now
            else:
                last_sent_ts = now
            print("✅ Sent embed")
            return msg_id
        print("❌ Webhook non-200:", r.status_code, r.text[:200])
        return None
    except Exception as e:
        print("❌ Webhook send error:", e)
        return None


# ==============================
# LOBBY SELECTOR
# ==============================
def select_host_lobby(data):
    candidates = []
    for code, lobby in data.items():
        if lobby.get("host_name") != HOST_NAME:
            continue
        status = (lobby.get("status") or "").strip()
        players = int(lobby.get("players") or 0)
        join_code = (code or "").strip()

        score = 0
        if join_code not in ("", "-"):
            score += 10
        if status == "In Game":
            score += 5
        if status == "In Lobby":
            score += 3
        score += min(players, 15)

        candidates.append((score, code, lobby))

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1], candidates[0][2]


# ==============================
# MAIN FETCH LOOP
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

            # No lobby — delete current message (cancelled / not searchable)
            if not lobby:
                if last_msg_id:
                    print("❌ Host lobby gone → deleting current message")
                    delete_message(last_msg_id)
                    last_msg_id = None
                    save_state()
                time.sleep(5)
                continue

            last_seen_host_ts = time.time()

            status = (lobby.get("status") or "").strip()
            players = int(lobby.get("players") or 0)

            # stability: code
            if code == observed_code:
                observed_code_count += 1
            else:
                observed_code = code
                observed_code_count = 1
            code_stable = observed_code_count >= CODE_STABILITY_POLLS

            # stability: status
            if status == observed_status:
                observed_status_count += 1
            else:
                observed_status = status
                observed_status_count = 1
            status_stable = observed_status_count >= STATUS_STABILITY_POLLS

            with state_lock:

                # 1) NEW STABLE LOBBY (code change)
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
                            remember_code_announcement(code)
                            save_state()
                    else:
                        print(f"🔇 Suppressed repeat code {code} (within {REPEAT_CODE_SUPPRESS_SEC}s)")

                # 2) STATUS CHANGE (Lobby ↔ Game) — after Game Ended → **show NEW LOBBY LIVE**
                elif code_stable and status_stable and last_status != status:
                    if last_msg_id:
                        delete_message(last_msg_id)
                        last_msg_id = None

                    # Only two titles via title_for(): Lobby -> NEW LOBBY LIVE, Game -> Game Started
                    title = title_for(status, players)
                    msg_id = send_embed_and_get_id(title, code, lobby)
                    if msg_id:
                        last_msg_id = msg_id
                        last_status = status
                        last_players = players
                        save_state()

                # 3) PLAYER COUNT CHANGE (same code, stable)
                elif (
                    code_stable
                    and status_stable
                    and last_code == code
                    and last_players is not None
                    and players != last_players
                ):
                    if last_msg_id:
                        delete_message(last_msg_id)
                        last_msg_id = None

                    title = title_for(status, players)
                    msg_id = send_embed_and_get_id(
                        title, code, lobby,
                        bypass_cooldown=True, is_player=True
                    )
                    if msg_id:
                        last_msg_id = msg_id
                        last_players = players
                        save_state()

                # 4) INITIAL POST IF NOTHING SENT YET
                elif last_msg_id is None and code_stable:
                    title = title_for(status, players)
                    msg_id = send_embed_and_get_id(title, code, lobby)
                    if msg_id:
                        last_msg_id = msg_id
                        last_code = code
                        last_status = status
                        last_players = players
                        remember_code_announcement(code)
                        save_state()

            time.sleep(5)

        except Exception as e:
            print("Fetch error:", e)
            time.sleep(5)


# ==============================
# OFFLINE WATCHDOG (20-min cleanup)
# ==============================
def offline_watchdog():
    global last_msg_id, last_seen_host_ts
    while True:
        try:
            now = time.time()
            if last_msg_id and last_seen_host_ts and (now - last_seen_host_ts >= OFFLINE_DELETE_SEC):
                print("⏱ Offline >20m → deleting last message")
                delete_message(last_msg_id)
                last_msg_id = None
                save_state()
        except Exception as e:
            print("Watchdog error:", e)
        time.sleep(60)


# ==============================
# KEEP ALIVE (Render)
# ==============================
def keep_alive():
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
            print("🔄 Keep-alive ping sent")
        except Exception as e:
            print("Keep-alive error:", e)
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
