import os
import time
import threading
import requests
from flask import Flask
import discord
from discord.ext import commands, tasks

app = Flask(__name__)

API_URL = "https://gurge44.pythonanywhere.com/get-all-lobbies"
COOKIE = os.getenv("SITE_COOKIE")
TARGET_HOST = "ARIJIT18"
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
last_sent_code = None

headers = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0"
}

def fetch_lobbies():
    try:
        r = requests.get(API_URL, headers=headers, timeout=10)
        return r.json()
    except:
        return {}

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

def build_embed(lobby_code, host, server, players, map_name, gamemode, version):
    return {
        "title": "🚀✅ NEW LOBBY LIVE!",
        "color": 5763719,
        "thumbnail": {
            "url": "https://cdn.aptoide.com/imgs/d/4/6/d460a63e167a534bc7b9e4f1eaeed7dc_fgraphic.png"
        },
        "image": {
            "url": "https://alfabetajuega.com/hero/2021/01/among-us-1.jpg?width=768&aspect_ratio=16:9&format=nowebp"
        },
        "fields": [
            {
                "name": "🎮 JOIN CODE (Tap to Copy)",
                "value": lobby_code,
                "inline": False
            },
            {
                "name": "👤 Host",
                "value": host,
                "inline": True
            },
            {
                "name": "🌍 Server",
                "value": server,
                "inline": True
            },
            {
                "name": "👥 Players",
                "value": str(players),
                "inline": True
            },
            {
                "name": "🗺 Map",
                "value": map_name,
                "inline": True
            },
            {
                "name": "🛠 Game Mode",
                "value": gamemode,
                "inline": True
            },
            {
                "name": "📌 Version",
                "value": version,
                "inline": True
            }
        ]
    }

def monitor_loop():
    global last_sent_code

    while True:
        data = fetch_lobbies()
        if not data:
            time.sleep(5)
            continue

        for code, lobby in data.items():
            host = lobby.get("host_name", "")
            if host.upper() == TARGET_HOST.upper():
                if last_sent_code == code:
                    continue

                last_sent_code = code
                server = lobby.get("server_name", "NA")
                players = lobby.get("players", "?")
                map_name = lobby.get("map", "?")
                gamemode = lobby.get("game_mode", "?")
                version = lobby.get("version", "?")

                embed = build_embed(code, host, server, players, map_name, gamemode, version)

                requests.post(
                    WEBHOOK_URL,
                    json={
                        "content": "@everyone",
                        "embeds": [embed]
                    }
                )

                # Auto delete after 2 minutes
                requests.post(
                    WEBHOOK_URL,
                    json={
                        "content": f"🗑 This message will auto-delete in 2 minutes.",
                        "flags": 64
                    }
                )

        time.sleep(5)

@app.route("/")
def home():
    return "Bot running"

def start_loop():
    t = threading.Thread(target=monitor_loop)
    t.daemon = True
    t.start()

start_loop()
