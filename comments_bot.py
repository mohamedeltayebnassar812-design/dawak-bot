import json
import os
import time
import urllib.request
import urllib.parse

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "fb_config.json")
REPLIED_FILE = os.path.join(os.path.dirname(__file__), "replied_comments.json")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_replied():
    if os.path.exists(REPLIED_FILE):
        try:
            with open(REPLIED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_replied(replied_set):
    with open(REPLIED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(replied_set), f, indent=2)

class CommentsBot:
    def __init__(self, page_id="1192151633977751"):
        self.config = load_config()
        self.page_id = page_id
        self.page_token = self.config["PAGES"][page_id]["access_token"]
        self.replied_comments = load_replied()
        self.graph_url = "https://graph.facebook.com/v21.0"

        # نص الرسالة الخاصة المرسلة في الماسنجر
        self.private_message = (
            "أهلاً بحضرتك في خدمة عملاء كارت دواك! 💊✨\n\n"
            "شكراً لتعليقك واهتمامك.. كارت دواك هو كارت رعاية صحية وخصومات طبية مجاني 100% لأهالي الإسكندرية:\n"
            "• خصم يصل إلى 20% كاش على الأدوية ومستلزمات الرعاية والتجميل.\n"
            "• خدمة توصيل سريع لحد باب بيتك في كل مناطق الإسكندرية 🛵\n"
            "• صيدليتك في جيبك وعلى الواتساب بدون أي تطبيقات معقدة.\n\n"
            "لطلب واستلام كارتك المجاني وتأكيد تفعيله الآن، برجاء إرسال:\n"
            "1. الاسم ثلاثي\n"
            "2. رقم الهاتف (واتساب)\n"
            "3. المنطقة أو العنوان في الإسكندرية\n\n"
            "أو تواصل معنا مباشرة عبر الواتساب: https://wa.me/201039823892?text=كارت"
        )

        # نص الرد العام على التعليق في البوست
        self.public_reply = "أهلاً بحضرتك يا فندم، بعتنالك تفاصيل كارت دواك المجاني وطريقة استلامه في رسائل الخاص (الماسنجر) 💌"

    def send_private_reply(self, comment_id):
        """إرسال رسالة خاصة في الماسنجر عبر نقطة /me/messages المعتمدة في Graph API"""
        url = f"{self.graph_url}/me/messages?access_token={self.page_token}"
        payload = {
            "recipient": {"comment_id": str(comment_id)},
            "message": {"text": self.private_message}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                print(f"[Private Reply Sent] Comment {comment_id}: {result}")
                return True
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            print(f"[Error Private Reply] Comment {comment_id}: {raw}")
            return False

    def reply_to_comment_publicly(self, comment_id):
        """كتابة رد عام تحت التعليق"""
        url = f"{self.graph_url}/{comment_id}/comments"
        data = urllib.parse.urlencode({
            "message": self.public_reply,
            "access_token": self.page_token
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                print(f"[Public Reply Sent] Comment {comment_id}: {result}")
                return True
        except Exception as e:
            print(f"[Error Public Reply] Comment {comment_id}: {e}")
            return False

    def handle_new_comment(self, comment_id, sender_id, sender_name, message_text):
        """معالجة التعليق الجديد والرد عليه خاص وعام"""
        # إذا كان التعليق من الصفحة نفسها، نتجاهله
        if sender_id == self.page_id:
            return

        if comment_id in self.replied_comments:
            return

        print(f"\n[جديد] تعليق من {sender_name} ({sender_id}): '{message_text}'")

        # 1. إرسال الرسالة الخاصة في الماسنجر
        priv_success = self.send_private_reply(comment_id)

        # 2. إرسال الرد العام في التعليقات
        self.reply_to_comment_publicly(comment_id)

        # حفظ التعليق في السجل
        self.replied_comments.add(comment_id)
        save_replied(self.replied_comments)

    def scan_recent_posts(self):
        """فحص أحدث المنشورات للبحث عن تعليقات جديدة غير مردود عليها"""
        feed_url = f"{self.graph_url}/{self.page_id}/feed?fields=id,comments{{id,from,message,created_time}}&limit=15&access_token={self.page_token}"
        try:
            req = urllib.request.Request(feed_url)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for post in data.get("data", []):
                    comments_data = post.get("comments", {}).get("data", [])
                    for c in comments_data:
                        cid = c.get("id")
                        from_user = c.get("from", {})
                        uid = from_user.get("id")
                        uname = from_user.get("name", "عميل")
                        msg = c.get("message", "")
                        if cid and uid != self.page_id and cid not in self.replied_comments:
                            self.handle_new_comment(cid, uid, uname, msg)
        except Exception as e:
            print(f"[Scan Error]: {e}")

if __name__ == "__main__":
    bot = CommentsBot()
    print("Dawak Comments Bot is running...")
    bot.scan_recent_posts()
