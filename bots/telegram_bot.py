import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from dotenv import load_dotenv
import requests
from nexus_dispatch import NexusDispatch

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = [u.strip() for u in os.getenv("NEXUS_ALLOWED_USERS", "").split(",") if u.strip()]
PAGES_ROOT = os.getenv("NEXUS_PAGES_ROOT", "").rstrip("/")

HELP = (
    "Nexus Remote Control\n"
    "/task <directive>  - run the autonomous pipeline\n"
    "/status            - last pipeline run status\n"
    "/latest            - link to the latest generated app\n"
    "/help              - this message"
)

API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None


def tg(method: str, timeout: int = 55, **params):
    if not API:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")
    res = requests.post(f"{API}/{method}", json=params, timeout=timeout)
    res.raise_for_status()
    return res.json()


def send(chat_id, text):
    try:
        tg("sendMessage", chat_id=chat_id, text=text)
    except requests.RequestException as e:
        print(f"[Bot] Failed to send message: {e}")


def handle(dispatch: NexusDispatch, chat_id, text: str):
    text = (text or "").strip()
    if text in ("/start", "/help"):
        send(chat_id, HELP)
    elif text == "/status":
        manifest = dispatch.latest_manifest()
        if manifest:
            send(
                chat_id,
                f"Last run: {manifest['provider']} ({manifest['model']})\n"
                f"Latency: {manifest['latency_ms']}ms  Artifacts: {len(manifest['artifacts'])}\n"
                f"Review applied: {manifest.get('review', {}).get('applied', False)}",
            )
        else:
            send(chat_id, "No completed run found yet.")
    elif text == "/latest":
        if PAGES_ROOT:
            send(chat_id, f"Latest app: {PAGES_ROOT}/output/latest_app.html")
        else:
            send(chat_id, "Set NEXUS_PAGES_ROOT to share the app link.")
    elif text.startswith("/task"):
        prompt = text[5:].strip() or "Generate a single-file HTML dashboard (dark mode, zinc/slate palette, indigo accents)."
        send(chat_id, "Nexus engaged. Dispatching pipeline...")
        try:
            run = dispatch.dispatch(prompt, mode="full")
            send(chat_id, f"Run started: {run['html_url']}")
            run = dispatch.poll(run["id"], interval=15, timeout=900)
            send(chat_id, dispatch.summarize(run))
            manifest = dispatch.latest_manifest()
            if manifest:
                send(chat_id, f"Provider: {manifest['provider']} ({manifest['model']})  Latency: {manifest['latency_ms']}ms")
            if PAGES_ROOT:
                send(chat_id, f"View the app: {PAGES_ROOT}/output/latest_app.html")
        except Exception as e:
            send(chat_id, f"Pipeline error: {e}")
    else:
        send(chat_id, "Unknown command. Send /help for the command list.")


def main():
    if not API:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set.")
    dispatch = NexusDispatch()
    print("[Bot] Nexus Telegram bridge online. Long-polling for updates...")
    offset = 0
    while True:
        try:
            data = tg("getUpdates", timeout=50, offset=offset, allowed_updates=["message"])
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message") or {}
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text")
                if not chat_id or text is None:
                    continue
                user_id = str(msg.get("from", {}).get("id", ""))
                if ALLOWED_USERS and user_id not in ALLOWED_USERS:
                    send(chat_id, "Access denied. Your user id is not authorized.")
                    continue
                print(f"[Bot] Command from {user_id}: {text[:80]}")
                handle(dispatch, chat_id, text)
        except requests.RequestException as e:
            print(f"[Bot] Network error (retrying in 5s): {e}")
            time.sleep(5)
        except Exception as e:
            print(f"[Bot] Unexpected error (retrying in 5s): {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
