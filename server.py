# ============================================================
#  RESIDENTIAL LAUNDRY SYSTEM — RENDER BACKEND
#  Handles:
#   - Pico POST events (boot/start/tick/abort/complete)
#   - Live machine state (used by washer.html)
#   - Textbelt paid SMS (guaranteed delivery)
# ============================================================

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.request
import urllib.parse

# ============================================================
#  CONFIG — UPDATE THESE TWO VALUES ONLY
# ============================================================

PHONE_NUMBER = "+12569246101"       # <--- replace with your phone (ex: +12565551234)
TEXTBELT_KEY = "797d161d1c256b18b56a937777d3011de59b4c0eiaUVHwbOvxFgv01X2jDWEyWye" # <--- replace with your paid API key

PORT = 10000    # Render will override internally, but keep this


# ============================================================
#  SIMPLE DEPENDENCY-FREE POST FUNCTION
# ============================================================

def http_post(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()


# ============================================================
#  TEXTBELT SMS WRAPPER (PAID KEY VERSION)
# ============================================================

def send_sms_textbelt(message):

    print("📱 SENDING SMS TO TEXTBELT...")
    print("📨 PHONE =", PHONE_NUMBER)
    print("📨 MESSAGE =", message)

    try:
        response = http_post("https://textbelt.com/text", {
            "phone": PHONE_NUMBER,
            "message": message,
            "key": TEXTBELT_KEY  # <--- PAID KEY HERE
        })
        print("📡 RAW RESPONSE:", response)

    except Exception as e:
        print("❌ SMS ERROR:", e)


# ============================================================
#  GLOBAL MACHINE STATE (served to washer.html)
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

    # ------------------------------------------------------------
    #   HANDLE POSTS FROM PICO
    # ------------------------------------------------------------
    def do_POST(self):
        global last_data

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body.decode())
            print("📩 FULL PAYLOAD:", data)

            event = data.get("event", "").lower()
            edata = data.get("data", {})

            # ---------------- BOOT ----------------
            if event == "boot":
                last_data = {
                    "rfid": "None",
                    "state": "Booted",
                    "time": "00:00",
                    "expected": 0
                }

            # ---------------- START ----------------
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

            # ---------------- TICK ----------------
            elif event == "tick":
                rem = int(edata.get("remaining_s", 0))
                mm = str(rem // 60).zfill(2)
                ss = str(rem % 60).zfill(2)
                last_data["time"] = f"{mm}:{ss}"

            # ---------------- COMPLETE ----------------
            elif event == "complete":
                last_data["state"] = "Complete"
                last_data["time"] = "00:00"

                send_sms_textbelt("✅ Laundry cycle complete! Ready for pickup.")

            # ---------------- ABORT ----------------
            elif event == "abort":
                last_data["state"] = "Aborted"
                last_data["time"] = "00:00"

                send_sms_textbelt("⚠️ Laundry cycle aborted — no vibration for 2 minutes.")

            else:
                print("⚠️ UNKNOWN EVENT:", event)

            # SUCCESS RESPONSE
            self._set_headers(200)
            self.wfile.write(json.dumps({"ok": True}).encode())

        except Exception as e:
            print("❌ SERVER ERROR:", e)
            self._set_headers(400)
            self.wfile.write(json.dumps({"ok": False}).encode())

    # ------------------------------------------------------------
    #   SERVE STATE TO FRONT-END
    # ------------------------------------------------------------
    def do_GET(self):
        if self.path == "/api/state":
            self._set_headers(200)
            self.wfile.write(json.dumps(last_data).encode())
        else:
            self._set_headers(404)
            self.wfile.write(b"{}")


# ============================================================
#  START SERVER
# ============================================================

print(f"🚀 BACKEND READY ON PORT {PORT}")
HTTPServer(("", PORT), Handler).serve_forever()
