# setup_webhook.py
import requests
import toml
import os
import time

# --- CONFIGURATION ---
# This script will read your secrets file to get the bot token.
SECRETS_FILE_PATH = os.path.join(".streamlit", "secrets.toml")
FLASK_AGENT_URL = "http://127.0.0.1:5003" # The local URL of your telegram_agent.py

def get_ngrok_url():
    """
    Connects to the local ngrok API to get the public URL.
    """
    try:
        # ngrok exposes a local API on port 4040 to inspect its tunnels.
        response = requests.get("http://127.0.0.1:4040/api/tunnels")
        response.raise_for_status()
        tunnels_data = response.json()
        # Find the HTTPS tunnel
        for tunnel in tunnels_data.get("tunnels", []):
            if tunnel.get("proto") == "https":
                return tunnel.get("public_url")
        raise ConnectionError("ngrok HTTPS tunnel not found.")
    except requests.ConnectionError:
        print("ERROR: Could not connect to ngrok. Is it running?")
        return None

def set_telegram_webhook(webhook_url, bot_token):
    """
    Tells the Telegram API where to send bot updates.
    """
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    params = {"url": f"{webhook_url}/{bot_token}"}
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        result = response.json()
        if result.get("ok"):
            print(f"✅ Webhook successfully set to: {webhook_url}/{bot_token}")
            return True
        else:
            print(f"❌ Telegram API returned an error: {result.get('description')}")
            return False
    except Exception as e:
        print(f"ERROR: Failed to set webhook. {e}")
        return False

if __name__ == "__main__":
    print("--- FocusFlow Webhook Setup ---")
    
    # 1. Load the Bot Token from secrets.toml
    print("1. Reading Telegram Bot Token from secrets.toml...")
    try:
        secrets = toml.load(SECRETS_FILE_PATH)
        bot_token = secrets.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in secrets file.")
        print("   ... Token found!")
    except Exception as e:
        print(f"   ERROR: Could not load token. {e}")
        exit()

    # 2. Get the public ngrok URL
    print("\n2. Getting public URL from ngrok...")
    # Give ngrok a moment to start up if it just launched
    time.sleep(2) 
    public_url = get_ngrok_url()

    if not public_url:
        print("   Exiting. Please ensure ngrok is running and exposing port 5003.")
        exit()
    print(f"   ... ngrok URL found: {public_url}")

    # 3. Set the webhook
    print("\n3. Contacting Telegram to set the webhook...")
    set_telegram_webhook(public_url, bot_token)

    print("\n--- Setup Complete! Your agent is now live. ---")