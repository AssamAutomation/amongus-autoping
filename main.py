import os
import requests

WEBHOOK = os.getenv("DISCORD_WEBHOOK")

data = {"content": "Hello everyone faltu"}
requests.post(WEBHOOK, json=data)

print("Message sent!")
