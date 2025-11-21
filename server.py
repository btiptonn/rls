# ============================================================
#  RESIDENTIAL LAUNDRY SYSTEM — RENDER BACKEND
#  - Tracks machine + lock state
#  - Sends SMS via Textbelt paid key
#  - Serves /api/state to frontend
# ============================================================

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.request
import urllib.parse

# ====== CONFIG: UPDATE THESE ======
PHONE_NUMBER = "+1YOURNUMBERHERE"        # e.g. "+12565551234"
TEXTBELT_KEY = "textbelt_PAID_KEY_HERE"  # your paid key from Textbelt
PORT = 10000
# ==================================

def http_post(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()

def send_sms_textbelt(message):
    print("📱 SENDING SMS")
    print("📨 PHONE =", PHONE_NUMBER)
    print("📨 MESSAGE =", message)
    try:
        response = http_post("https://textbelt.com/text", {
            "phone": PHONE_NUMBER,
            "message": message,
            "key": TEXTBELT_KEY
        })
        print("📡 RAW RESPONSE:", response)
    except Exception as e:
        print("❌ SMS ERROR:", e)

# ====== GLOBAL STATE ======
# rfid      = last card that started a cycle
# state     = Idle | Running | Locked | Booted
# lock_uid  = uid of user who must scan out (or None)
# time      = mm:ss remaining or 00:00 when not running
last_data = {
    "rfid": "None",
    "state": "Idle",
    "time": "00:00",
    "expected": 0,
    "lock_uid": None
}

def set_lock(uid):
    global last_data
    last_data["lock_uid"] = uid
    last_data["state"] = "Locked"
    last_data["time"] = "00:00"

def clear_lock():
    global last_data
    last_data["lock_uid"] = None
    last_data["state"] = "Idle"
    last_data["rfid"] = "None"
    last_data["time"] = "00:00"
    last_data["expected"] = 0

class Handler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        global last_data
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body.decode())
            print("📩 FULL PAYLOAD:", data)

            event = data.get("event", "").lower()
            edata = data.get("data", {})

            # ---------- BOOT ----------
            if event == "boot":
                # keep lock_uid as-is if you want to preserve lock,
                # or clear it here if you want fresh boot:
                # clear_lock()
                last_data["state"] = "Idle" if last_data["lock_uid"] is None else "Locked"

            # ---------- START ----------
            elif event == "start":
                uid = edata.get("uid", "unknown")
                secs = int(edata.get("seconds", 0))
                mm = str(secs // 60).zfill(2)
                ss = str(secs % 60).zfill(2)

                last_data["rfid"] = uid
                last_data["state"] = "Running"
                last_data["time"] = f"{mm}:{ss}"
                last_data["expected"] = secs // 60
                last_data["lock_uid"] = None

            # ---------- TICK ----------
            elif event == "tick":
                rem = int(edata.get("remaining_s", 0))
                mm = str(rem // 60).zfill(2)
                ss = str(rem % 60).zfill(2)
                last_data["time"] = f"{mm}:{ss}"

            # ---------- COMPLETE ----------
            elif event == "complete":
                uid = last_data.get("rfid", "None")
                set_lock(uid)
                send_sms_textbelt("✅ Laundry cycle complete! Machine locked until scan-out.")

            # ---------- ABORT ----------
            elif event == "abort":
                uid = last_data.get("rfid", "None")
                set_lock(uid)
                send_sms_textbelt("⚠️ Laundry cycle aborted—no movement. Machine locked until scan-out.")

            # ---------- UNLOCK (scan-out or override) ----------
            elif event == "unlock":
                mode = edata.get("mode", "normal")  # "normal" or "override"
                print("🔓 UNLOCK EVENT, mode:", mode)
                clear_lock()

            else:
                print("⚠️ Unknown event:", event)

            self._set_headers(200)
            self.wfile.write(json.dumps({"ok": True}).encode())

        except Exception as e:
            print("❌ SERVER ERROR:", e)
            self._set_headers(400)
            self.wfile.write(json.dumps({"ok": False}).encode())

    def do_GET(self):
        if self.path == "/api/state":
            self._set_headers(200)
            self.wfile.write(json.dumps(last_data).encode())
        else:
            self._set_headers(404)
            self.wfile.write(b"{}")

print(f"🚀 BACKEND READY ON PORT {PORT}")
HTTPServer(("", PORT), Handler).serve_forever()
