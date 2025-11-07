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

# ==============================
# ANTI-SPAM / STATE
# ==============================
STATE_FILE = "last_state.json"

# Stability requirements (poll interval is 5s)
CODE_STABILITY_POLLS = 3        # 3 * 5s = 15s same code
STATUS_STABILITY_POLLS = 2      # 2 * 5s = 10s same status

GLOBAL_COOLDOWN_SEC = 120       # at least 2 min between any messages
REPEAT_CODE_SUPPRESS_SEC = 600  # don't re-announce same code within 10 minutes

# In-memory runtime state (also persisted)
state_lock = threading.Lock()
last_code = None
last_status = None
last_sent_ts = 0
recent_codes = deque(maxlen=8)   # list of {"code": str, "ts": float}

# Rolling observations to enforce stability
observed_code = None
observed_code_count = 0
observed_status = None
observed_status_count = 0


def load_state():
    global last_code, last_status, last_sent_ts, recent_codes
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            last_code = data.get("last_code")
            last_status = data.get("last_status")
            last_sent_ts = data.get("last_sent_ts", 0)
            rc = data.get("recent_codes", [])
            # filter out old entries
            cutoff = time.time() - REPEAT_CODE_SUPPRESS_SEC
            rc = [x for x in rc if x.get("ts", 0) >= cutoff]
            recent_codes.clear()
            for x in rc:
                recent_codes.append({"code": x.get("code"), "ts": x.get("ts", 0)})
            print("Loaded state:", {
                "last_code": last_code,
                "last_status": last_status,
                "last_sent_ts": last_sent_ts,
                "recent_codes": list(recent_codes)
            })
        except Exception as e:
            print("State load error, starting fresh:", e)


def save_state():
    try:
        data = {
            "last_code": last_code,
            "last_status": last_status,
            "last_sent_ts": last_sent_ts,
            "recent_codes": list(recent_codes)
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print("State save error:", e)


def code_recently_announced(code: str) -> bool:
    now = time.time()
    # purge old
    while recent_codes and (now - recent_codes[0]["ts"] > REPEAT_CODE_SUPPRESS_SEC):
        recent_codes.popleft()
    for item in recent_codes:
        if item["code"] == code and now - item["ts"] <= REPEAT_CODE_SUPPRESS_SEC:
            return True
    return False


def remember_code_announcement(code: str):
    recent_codes.append({"code": code, "ts": time.time()})


# ==============================
# DELETE MESSAGE AFTER 2 MINS
# ==============================
def delete_message_later(webhook, msg_id):
    time.sleep(120)
    try:
        requests.delete(f"{webhook}/messages/{msg_id}")
        print("🗑 Deleted old message:", msg_id)
    except Exception as e:
        print("⚠ Could not delete message:", e)


# ==============================
# SEND EMBED (respects cooldown)
# ==============================
def safe_send_embed(event_title, code, lobby, extra_message=""):
    global last_sent_ts

    # Global cooldown
    now = time.time()
    if now - last_sent_ts < GLOBAL_COOLDOWN_SEC:
        print(f"⏳ Cooldown active ({int(GLOBAL_COOLDOWN_SEC - (now - last_sent_ts))}s left) — skipping send.")
        return

    # Validate code
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
        ],
        "footer": {"text": "Among Us AutoPing • ARIJIT18 Host", "icon_url": thumb_url}
    }

    if extra_message:
        embed["fields"].append({"name": "📢 Update", "value": extra_message, "inline": False})

    payload = {"content": "@everyone", "embeds": [embed]}

    try:
        r = requests.post(WEBHOOK_URL + "?wait=true", json=payload, timeout=10)
        print("✅ Embed send status:", r.status_code)

        if r.status_code == 200:
            msg_id = r.json().get("id")
            last_sent_ts = now
            threading.Thread(target=delete_message_later, args=(WEBHOOK_URL, msg_id), daemon=True).start()
        else:
            print("❌ Webhook non-200:", r.text[:200])

    except Exception as e:
        print("❌ Webhook send error:", e)


# ==============================
# CHOOSE BEST LOBBY FOR HOST
# ==============================
def select_host_lobby(all_data: dict):
    """
    Return (code, lobby) for HOST_NAME with simple heuristics:
    - Prefer non-empty code
    - Prefer 'In Game' over 'In Lobby'
    - Prefer higher players
    """
    candidates = []
    for code, lobby in all_data.items():
        if lobby.get("host_name") != HOST_NAME:
            continue
        status = lobby.get("status") or ""
        players = int(lobby.get("players") or 0)
        join_code = (code or "").strip()
        score = 0
        if join_code not in ("", "-"):
            score += 10
        if status == "In Game":
            score += 5
        if status == "In Lobby":
            score += 3
        score += min(players, 15)  # cap
        candidates.append((score, code, lobby))

    if not candidates:
        return None, None

    # pick highest score
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1], candidates[0][2]


# ==============================
# FETCH LOOP — SPAM-PROOF
# ==============================
def fetch_loop():
    global last_code, last_status
    global observed_code, observed_code_count, observed_status, observed_status_count

    while True:
        try:
            r = requests.get(API_URL, headers=HEADERS, timeout=10)
            data = r.json()

            # Debug list
            try:
                print("------ All lobbies ------")
                for code, lobby in data.items():
                    print(code, "=>", lobby.get("host_name"), lobby.get("status"), lobby.get("players"))
            except Exception:
                pass

            code, lobby = select_host_lobby(data)
            if not lobby:
                # No lobby for our host — reset observations slowly
                observed_code = None
                observed_code_count = 0
                observed_status = None
                observed_status_count = 0
                time.sleep(5)
                continue

            status = lobby.get("status") or ""

            # ---------- CODE STABILITY ----------
            if code == observed_code:
                observed_code_count += 1
            else:
                observed_code = code
                observed_code_count = 1

            # Only lock in current_code when stable enough
            stable_code_ready = observed_code_count >= CODE_STABILITY_POLLS

            # ---------- STATUS STABILITY ----------
            if status == observed_status:
                observed_status_count += 1
            else:
                observed_status = status
                observed_status_count = 1

            stable_status_ready = observed_status_count >= STATUS_STABILITY_POLLS

            # ---------- DECISION LOGIC ----------
            with state_lock:
                # Announce NEW LOBBY only if stable code and not recently announced
                if stable_code_ready and code != last_code:
                    if not code_recently_announced(code):
                        safe_send_embed("🚀✅ NEW LOBBY LIVE!", code, lobby)
                        last_code = code
                        last_status = status
                        remember_code_announcement(code)
                        save_state()
                    else:
                        print(f"🔇 Suppressed repeat code {code} (within {REPEAT_CODE_SUPPRESS_SEC}s)")
                else:
                    # If same code, we may announce status changes — but only when status is stable
                    if stable_status_ready and last_code == code and last_status != status:
                        if last_status == "In Lobby" and status == "In Game":
                            safe_send_embed("🟥 Game Started!", code, lobby, "I'll ping you when it ends.")
                            last_status = status
                            save_state()
                        elif last_status == "In Game" and status == "In Lobby":
                            safe_send_embed("🟩 Game Ended!", code, lobby, "You may join again.")
                            last_status = status
                            save_state()

            time.sleep(5)

        except Exception as e:
            print("❌ Fetch error:", e)
            time.sleep(5)


# ==============================
# KEEP ALIVE (Render)
# ==============================
def keep_alive():
    while True:
        try:
            requests.get("https://amongus-autoping.onrender.com/", timeout=10)
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
    threading.Thread(target=keep_alive, daemon=True).start()


start_background()
