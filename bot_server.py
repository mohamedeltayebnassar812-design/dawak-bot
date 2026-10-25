import json
import os
import threading
import time
import urllib.request
import urllib.parse
from flask import Flask, request
from bot_logic import DawakBotLogic
from comments_bot import CommentsBot

app = Flask(__name__)
bot = DawakBotLogic()
comments_bot = CommentsBot()

# رمز التحقق الخاص بالويب هوك
VERIFY_TOKEN = "dawak_bot_verify_token_2026"

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "fb_config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

PAGE_ID = "1192151633977751"
PAGE_ACCESS_TOKEN = config["PAGES"][PAGE_ID]["access_token"]

def send_facebook_message(recipient_id, message_data):
    """إرسال رسالة رد للعميل عبر Graph API"""
    url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": message_data
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Error sending message to {recipient_id}: {e}")
        return None

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """تحقق فيسبوك من السيرفر عند الربط (Verification)"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("[Webhook] Verification successful!")
        return challenge, 200
    else:
        return "Verification token mismatch", 403

@app.route("/webhook", methods=["POST"])
def receive_events():
    """استقبال أحداث الماسنجر والتعليقات والرد عليها فورياً"""
    data = request.get_json()

    if data and data.get("object") == "page":
        for entry in data.get("entry", []):
            # 1. رسائل الماسنجر
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                if "message" in messaging_event and not messaging_event["message"].get("is_echo"):
                    msg = messaging_event["message"]
                    incoming_text = msg.get("text", "")
                    quick_payload = msg.get("quick_reply", {}).get("payload")
                    query = quick_payload if quick_payload else incoming_text
                    print(f"[Messenger Message] from {sender_id}: {query}")

                    reply_data = bot.process_incoming_text(query)
                    send_facebook_message(sender_id, reply_data)

            # 2. تعليقات المنشورات (Feed / Comments)
            for change in entry.get("changes", []):
                if change.get("field") == "feed":
                    val = change.get("value", {})
                    item = val.get("item")
                    verb = val.get("verb")
                    if item == "comment" and verb == "add":
                        cid = val.get("comment_id")
                        from_data = val.get("from", {})
                        uid = from_data.get("id")
                        uname = from_data.get("name", "عميل")
                        msg = val.get("message", "")
                        print(f"[Webhook New Comment] {uname} ({cid}): {msg}")
                        comments_bot.handle_new_comment(cid, uid, uname, msg)

        return "EVENT_RECEIVED", 200

    return "Not Found", 404

def comments_background_scanner():
    """فحص دوري ذكي لضمان الرد على أي تعليق حتى في حال تأخر الويب هوك"""
    print("[Watcher] Comments background scanner started (checking every 30s)...")
    while True:
        try:
            comments_bot.scan_recent_posts()
        except Exception as e:
            print(f"[Watcher Error]: {e}")
        time.sleep(30)

# تشغيل الفاحص الدوري في الخلفية تلقائياً سواء تشغيل مباشر أو عبر WSGI/Cloud
watcher_thread = threading.Thread(target=comments_background_scanner, daemon=True)
watcher_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Dawak Unified Bot Server (Messenger + Comments) running on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
