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
# ANTI-SPAM / STATE
# ==============================
STATE_FILE = "last_state.json"

# Stability requirements (poll interval is 5s)
CODE_STABILITY_POLLS = 3        # 3 * 5s = 15s same code
STATUS_STABILITY_POLLS = 2      # 2 * 5s = 10s same status

GLOBAL_COOLDOWN_SEC = 90        # code/status announcements minimum gap
REPEAT_CODE_SUPPRESS_SEC = 600  # don't re-announce same code within 10 min

# Player updates (own small gap so it can refresh often)
PLAYER_UPDATE_MIN_GAP = 5       # seconds between player-count updates

# Offline cleanup
OFFLINE_DELETE_SEC = 20 * 60    # delete message if host unseen for 20 minutes

# In-memory runtime state (persisted too)
state_lock = threading.Lock()
last_code = None
last_status = None
last_players = None
last_msg_id = None
last_sent_ts = 0
last_player_sent_ts = 0
last_seen_host_ts = 0
recent_codes = deque(maxlen=10)   # list of {"code": str, "ts": float}

# Rolling observations to enforce stability
observed_code = None
observed_code_count = 0
observed_status = None
observed_status_count = 0

# ==============================
# PERSISTENCE
# ==============================
def load_state():
    global last_code, last_status, last_players, last_msg_id, last_sent_ts, last_player_sent_ts, last_seen_host_ts, recent_codes
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
    else:
        last_seen_host_ts = 0


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


def code_recently_announced(code: str) -> bool:
    now = time.time()
    while recent_codes and (now - recent_codes[0]["ts"] > REPEAT_CODE_SUPPRESS_SEC):
        recent_codes.popleft()
    for item in recent_codes:
        if item["code"] == code and now - item["ts"] <= REPEAT_CODE_SUPPRESS_SEC:
            return True
    return False


def remember_code_announcement(code: str):
    recent_codes.append({"code": code, "ts": time.time()})


# ==============================
# DISCORD HELPERS
# ==============================
def delete_message(msg_id: str):
    if not msg_id:
        return
    try:
        r = requests.delete(f"{WEBHOOK_URL}/messages/{msg_id}", timeout=10)
        print(f"🗑 Delete {msg_id} →", r.status_code)
    except Exception as e:
        print("⚠ Delete error:", e)


def title_for(status: str, players: int) -> str:
    p = int(players or 0)
    if status == "In Game":
        return f"🎮 MATCH IN PROGRESS ({p}/15)"
    else:
        # default treat as In Lobby/Waiting
        return f"🎮 JOIN NOW ({p}/15)"


def build_embed(event_title, code, lobby, extra_message=""):
    display_code = (code or "").strip()
    if display_code in ("", "-"):
        display_code = "NO CODE"

    banner_url = "https://alfabetajuega.com/hero/2021/01/among-us-1.jpg?width=768&aspect_ratio=16:9&format=nowebp"
    thumb_url = "https://cdn.aptoide.com/imgs/d/4/6/d460a63e167a534bc7b9e4f1eaeed7dc_fgraphic.png"

    embed = {
        "title": event_title,
        "color": 0xF7E7A6,
        "thumbnail": {"url": thumb_url},
        "image": {"url": banner_url},
        "fields": [
            {"name": "🎮 JOIN CODE (Tap to Copy)", "value": display_code, "inline": False},
            {"name": "👤 Host", "value": lobby.get("host_name", "-"), "inline": True},
            {"name": "🌍 Server", "value": lobby.get("server_name", "-"), "inline": True},
            {"name": "👥 Players", "value": str(lobby.get("players", "-")), "inline": True},
            {"name": "🗺 Map", "value": lobby.get("map", "-"), "inline": True},
            {"name": "🎛 Mode", "value": lobby.get("game_mode", "-"), "inline": True},
            {"name": "💾 Version", "value": lobby.get("version", "-"), "inline": True},
            {"name": "📌 Status", "value": lobby.get("status", "-"), "inline": True},
        ],
        "footer": {"text": "Among Us AutoPing • ARIJIT18 Host", "icon_url": thumb_url}
    }
    if extra_message:
        embed["fields"].append({"name": "📢 Update", "value": extra_message, "inline": False})
    return embed


def send_embed_and_get_id(event_title, code, lobby, *, bypass_cooldown=False, is_player_update=False, min_gap=0):
    """
    Sends embed and returns message id.
    - bypass_cooldown: skip global cooldown (used for player updates)
    - is_player_update: when True, uses last_player_sent_ts tracking instead of last_sent_ts
    - min_gap: minimum seconds between consecutive sends for this category
    """
    global last_sent_ts, last_player_sent_ts

    now = time.time()
    if is_player_update:
        # own smaller gap
        if now - last_player_sent_ts < max(min_gap, 0):
            print(f"⏳ Player-update gap active ({int(max(min_gap,0) - (now - last_player_sent_ts))}s left) — skip.")
            return None
    else:
        if not bypass_cooldown and (now - last_sent_ts < GLOBAL_COOLDOWN_SEC):
            print(f"⏳ Global cooldown ({int(GLOBAL_COOLDOWN_SEC - (now - last_sent_ts))}s left) — skip.")
            return None

    payload = {"content": "@everyone", "embeds": [build_embed(event_title, code, lobby)]}
    try:
        r = requests.post(WEBHOOK_URL + "?wait=true", json=payload, timeout=10)
        print("✅ Embed send status:", r.status_code)
        if r.status_code == 200:
            msg_id = r.json().get("id")
            if is_player_update:
                last_player_sent_ts = now
            else:
                last_sent_ts = now
            return msg_id
        else:
            print("❌ Webhook non-200:", r.text[:200])
            return None
    except Exception as e:
        print("❌ Webhook send error:", e)
        return None


# ==============================
# LOBBY SELECTOR (pick best for host)
# ==============================
def select_host_lobby(all_data: dict):
    candidates = []
    for code, lobby in all_data.items():
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
# FETCH LOOP — STABLE + CLEAN DELETE RULES + PLAYER UPDATES
# ==============================
def fetch_loop():
    global last_code, last_status, last_players, last_msg_id, last_seen_host_ts
    global observed_code, observed_code_count, observed_status, observed_status_count

    while True:
        try:
            r = requests.get(API_URL, headers=HEADERS, timeout=10)
            data = r.json()

            # Debug list
            try:
                print("------ All lobbies ------")
                for c, l in data.items():
                    print(c, "=>", l.get("host_name"), l.get("status"), l.get("players"))
            except Exception:
                pass

            code, lobby = select_host_lobby(data)

            if not lobby:
                # No lobby for our host → delete immediately if a message exists (cancelled/not searchable)
                if last_msg_id:
                    print("❌ Host lobby gone → deleting current message")
                    delete_message(last_msg_id)
                    last_msg_id = None
                    save_state()
                time.sleep(5)
                continue

            # Host is present
            last_seen_host_ts = time.time()

            status = (lobby.get("status") or "").strip()
            players = int(lobby.get("players") or 0)

            # ----- STABILITY: CODE -----
            if code == observed_code:
                observed_code_count += 1
            else:
                observed_code = code
                observed_code_count = 1
            code_stable = observed_code_count >= CODE_STABILITY_POLLS

            # ----- STABILITY: STATUS -----
            if status == observed_status:
                observed_status_count += 1
            else:
                observed_status = status
                observed_status_count = 1
            status_stable = observed_status_count >= STATUS_STABILITY_POLLS

            # ----- DECISIONS -----
            with state_lock:

                # 1) NEW STABLE LOBBY (code change)
                if code_stable and code != last_code:
                    if not code_recently_announced(code):
                        if last_msg_id:
                            print("🔁 New code → deleting previous message before posting")
                            delete_message(last_msg_id)
                            last_msg_id = None
                        msg_id = send_embed_and_get_id(
                            title_for(status, players), code, lobby,
                            bypass_cooldown=False, is_player_update=False
                        )
                        if msg_id:
                            last_msg_id = msg_id
                            last_code = code
                            last_status = status
                            last_players = players
                            remember_code_announcement(code)
                            save_state()
                    else:
                        print(f"🔇 Suppressed repeat code {code} (within {REPEAT_CODE_SUPPRESS_SEC}s)")

                else:
                    # 2) STATUS CHANGE (same code; stable)
                    if status_stable and last_code == code and last_status != status:
                        if last_msg_id:
                            print("🔁 Status change → deleting previous message before posting")
                            delete_message(last_msg_id)
                            last_msg_id = None

                        msg_id = send_embed_and_get_id(
                            title_for(status, players), code, lobby,
                            bypass_cooldown=False, is_player_update=False
                        )
                        if msg_id:
                            last_msg_id = msg_id
                            last_status = status
                            last_players = players
                            save_state()

                    # 3) PLAYER COUNT CHANGE (same code; status stable; players changed)
                    elif code_stable and status_stable and last_code == code and last_players is not None and players != last_players:
                        if last_msg_id:
                            print(f"🔁 Players {last_players} → {players} → deleting & updating")
                            delete_message(last_msg_id)
                            last_msg_id = None

                        # Player updates should be frequent; bypass global cooldown but apply small gap
                        msg_id = send_embed_and_get_id(
                            title_for(status, players), code, lobby,
                            bypass_cooldown=True, is_player_update=True, min_gap=PLAYER_UPDATE_MIN_GAP
                        )
                        if msg_id:
                            last_msg_id = msg_id
                            last_players = players
                            save_state()

                    # 4) First-time message when state loaded but nothing sent yet
                    elif last_msg_id is None and code_stable:
                        msg_id = send_embed_and_get_id(
                            title_for(status, players), code, lobby,
                            bypass_cooldown=False, is_player_update=False
                        )
                        if msg_id:
                            last_msg_id = msg_id
                            last_code = code
                            last_status = status
                            last_players = players
                            remember_code_announcement(code)
                            save_state()

            time.sleep(5)

        except Exception as e:
            print("❌ Fetch error:", e)
            time.sleep(5)


# ==============================
# OFFLINE WATCHDOG (20-min cleanup)
# ==============================
def offline_watchdog():
    global last_msg_id, last_seen_host_ts
    while True:
        try:
            now = time.time()
            # If we have a message but haven't seen host lobby for OFFLINE_DELETE_SEC → delete
            if last_msg_id and last_seen_host_ts and (now - last_seen_host_ts >= OFFLINE_DELETE_SEC):
                print("⏱ Offline >20m → deleting last message")
                delete_message(last_msg_id)
                last_msg_id = None
                save_state()
        except Exception as e:
            print("Watchdog error:", e)
        time.sleep(60)  # check every minute


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
        time.sleep(240)  # every 4 min


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
