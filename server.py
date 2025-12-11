# ============================================================
#  RESIDENTIAL LAUNDRY SYSTEM — BACKEND
# ============================================================

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.request
import urllib.parse

# ------------------------------------------------------------
#  TEXTBELT CONFIG
# ------------------------------------------------------------
PHONE_NUMBER = "+12569246101"
TEXTBELT_KEY = "797d161d1c256b18b56a937777d3011de59b4c0eiaUVHwbOvxFgv01X2jDWEyWye"

PORT = 10000

# ------------------------------------------------------------
#  SIMPLE HTTP POST WRAPPER
# ------------------------------------------------------------
def http_post(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()

# ------------------------------------------------------------
#  SEND SMS (PAID KEY)
# ------------------------------------------------------------
def send_sms(message):
    print("📱 SEND SMS:", message)
    try:
        out = http_post("https://textbelt.com/text", {
            "phone": PHONE_NUMBER,
            "message": message,
            "key": TEXTBELT_KEY
        })
        print("📨 TEXTBELT:", out)
    except Exception as e:
        print("❌ SMS ERROR:", e)

# ------------------------------------------------------------
#  GLOBAL STATE
# ------------------------------------------------------------
state = {
    "rfid": "None",
    "state": "Idle",
    "time": "00:00",
    "expected": 0
}

# ------------------------------------------------------------
#  REQUEST HANDLER
# ------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):

    def _json(self, code=200):
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

    # ---------------------------
    #  RECEIVE EVENT FROM PICO
    # ---------------------------
    def do_POST(self):
        global state
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body.decode())
            event = data.get("event", "").lower()
            edata = data.get("data", {})

            print("📩 EVENT:", event, edata)

            # ---------------- BOOT ----------------
            if event == "boot":
                state = {
                    "rfid": "None",
                    "state": "Booted",
                    "time": "00:00",
                    "expected": 0
                }

            # ---------------- START ----------------
            elif event == "start":
                uid = edata.get("uid", "None")
                secs = int(edata.get("seconds", 0))

                mm = str(secs // 60).zfill(2)
                ss = str(secs % 60).zfill(2)

                state = {
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
                state["time"] = f"{mm}:{ss}"

            # ---------------- COMPLETE ----------------
            elif event == "complete":
                state["state"] = "Complete"
                state["time"] = "00:00"
                send_sms("✅ Laundry cycle finished! Pick up your laundry.")

            # ---------------- ABORT ----------------
            elif event == "abort":
                state["state"] = "Aborted"
                state["time"] = "00:00"
                send_sms("⚠️ Laundry cycle aborted — no vibration detected.")

            # ---------------- LOCKED ----------------
            elif event == "locked":
                # keep same RFID + expected, just mark as locked
                state["state"] = "Locked"

            self._json(200)
            self.wfile.write(b'{"ok": true}')

        except Exception as e:
            print("❌ SERVER ERROR:", e)
            self._json(400)
            self.wfile.write(b'{"ok": false}')

    # ---------------------------
    #  SERVE STATE TO WEB
    # ---------------------------
    def do_GET(self):
        if self.path == "/api/state":
            self._json(200)
            self.wfile.write(json.dumps(state).encode())
        else:
            self._json(404)
            self.wfile.write(b"{}")


print(f"🚀 BACKEND RUNNING ON PORT {PORT}")
HTTPServer(("", PORT), Handler).serve_forever()
