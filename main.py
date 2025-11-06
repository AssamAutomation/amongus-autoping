import os
import requests
from flask import Flask

app = Flask(__name__)

WEBHOOK = os.getenv("DISCORD_WEBHOOK")  # put your webhook in Render env variable

@app.route("/")
def home():
    return "Test Webhook alive"

@app.route("/test")
def test_webhook():
    if not WEBHOOK:
        return "Webhook missing!"

    msg = "✅ Bot is connected!\nThe lobby code will be available soon..."
    try:
        requests.post(WEBHOOK, json={"content": msg})
        return "Test message sent to Discord!"
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    app.run()
