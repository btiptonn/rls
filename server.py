# ============================================================
#  FULL RENDER BACKEND FOR RESIDENTIAL LAUNDRY SYSTEM
#  - Handles Pico events (boot/start/tick/complete/abort)
#  - Stores live machine state
#  - Sends SMS alerts (Textbelt)
#  - Logs full payload for debugging
# ============================================================

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.request
import urllib.parse

# ============================================================
#  SIMPLE REQUESTS-LIKE SENDER (NO DEPENDENCIES NEEDED)
# ============================================================
def http_post(url, fields):
    data = urllib.parse.urlencode(fields).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()

# ============================================================
#  TEXTBELT SMS SENDER
# ============================================================
def send_sms_textbelt(message):
    try:
        response = http_post("https://textbelt.com/text", {
            'phone': '+12569246101',   # <--- PUT YOUR NUMBER HERE
            'message': message,
            'key': 'textbelt'               # free key = 1 SMS/day
        })
        print("📱 FULL SMS RESPONSE:", response)
    except Exception as e:
        print("❌ SMS ERROR:", e)

# ============================================================
#  GLOBAL STATE
# ============================================================
last_data = {
    "rfid": "None",
    "state": "Idle",
    "time": "00:00",
    "expected": 0
}

# ============================================================
#  REQUEST HANDLER
# ============================================================
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

    # ======================================================
    #  HANDLE POST FROM PICO
    # ======================================================
    def do_POST(self):
        global last_data

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body.decode())
            print("📩 FULL PAYLOAD:", data)  # <-- IMPORTANT FOR DEBUGGING

            event = data.get("event", "").lower()
            edata = data.get("data", {})

            # ------------------------------------------------------
            #  BOOT EVENT
            # ------------------------------------------------------
            if event == "boot":
                last_data = {
                    "rfid": "None",
                    "state": "Booted",
                    "time": "00:00",
                    "expected": 0
                }

            # ------------------------------------------------------
            #  START EVENT
            # ------------------------------------------------------
            elif event == "start":
                uid = edata.get("uid", "unknown")
                secs = int(edata.get("seconds", 0))
                mm = str(secs // 60).zfill(2)
                ss = str(secs % 60).zfill(2)

                last_data = {
                    "rfid": uid,
                    "state": "Running",
                    "time": f"{mm}:{ss}",
                    "expected": secs // 60
                }

            # ------------------------------------------------------
            #  TICK EVENT
            # ------------------------------------------------------
            elif event == "tick":
                rem = int(edata.get("remaining_s", 0))
                mm = str(rem // 60).zfill(2)
                ss = str(rem % 60).zfill(2)
                last_data["time"] = f"{mm}:{ss}"

            # ------------------------------------------------------
            #  COMPLETE EVENT
            # ------------------------------------------------------
            elif event == "complete":
                last_data["state"] = "Complete"
                last_data["time"] = "00:00"

                send_sms_textbelt("✅ Laundry cycle complete! Ready for pickup.")

            # ------------------------------------------------------
            #  ABORT EVENT
            # ------------------------------------------------------
            elif event == "abort":
                last_data["state"] = "Aborted"
                last_data["time"] = "00:00"

                print("🚫 MACHINE ABORTED:", edata)
                send_sms_textbelt("⚠️ Laundry cycle aborted — no vibration for 2 minutes.")

            else:
                print("⚠️ Unknown event key:", event)

            # SEND OK RESPONSE
            self._set_headers(200)
            self.wfile.write(json.dumps({"ok": True}).encode())

        except Exception as e:
            print("❌ ERROR IN POST HANDLER:", e)
            self._set_headers(400)
            self.wfile.write(json.dumps({"ok": False}).encode())

    # ======================================================
    #  FRONTEND GET REQUEST
    # ======================================================
    def do_GET(self):
        if self.path == "/api/state":
            self._set_headers(200)
            self.wfile.write(json.dumps(last_data).encode())
        else:
            self._set_headers(404)
            self.wfile.write(b"{}")

# ============================================================
#  SERVER START
# ============================================================
PORT = 10000
print(f"🚀 SERVER LIVE ON PORT {PORT}")
HTTPServer(("", PORT), Handler).serve_forever()
