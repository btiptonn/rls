from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import requests   # for SMS alerts via Textbelt

# ======== Textbelt SMS helper ========
def send_sms_textbelt(msg):
    try:
        res = requests.post('https://textbelt.com/text', {
            'phone': '+12569246101',  # 👈 replace with your number, e.g. +12565551234
            'message': msg,
            'key': 'textbelt'         # free key (1 text/day) — buy key for unlimited
        })
        print("📱 SMS sent:", res.json())
    except Exception as e:
        print("❌ SMS error:", e)

# ======== Global State ========
last_data = {"rfid": "None", "state": "Idle", "time": "00:00"}

class Handler(BaseHTTPRequestHandler):
    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        global last_data
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode())
            print("📩 Received:", data)

            event = data.get("event", "").lower()

            if event == "boot":
                last_data = {"rfid": "None", "state": "Booted", "time": "00:00"}

            elif event == "start":
                uid = data["data"].get("uid", "unknown")
                secs = int(data["data"].get("seconds", 0))
                mm = str(secs // 60).zfill(2)
                ss = str(secs % 60).zfill(2)
                last_data = {
                    "rfid": uid,
                    "state": "Running",
                    "time": f"{mm}:{ss}",
                    "expected": secs // 60
                }

            elif event == "tick":
                rem = int(data["data"].get("remaining_s", 0))
                mm = str(rem // 60).zfill(2)
                ss = str(rem % 60).zfill(2)
                last_data["time"] = f"{mm}:{ss}"

            elif event == "complete":
                last_data["state"] = "Complete"
                last_data["time"] = "00:00"
                send_sms_textbelt("✅ Laundry cycle complete! Ready for pickup.")

            elif event == "abort":
                last_data["state"] = "Aborted"
                last_data["time"] = "00:00"
                reason = data["data"].get("reason", "quiet")
                print(f"🚫 Aborted due to: {reason}")
                send_sms_textbelt("⚠️ Laundry cycle aborted — no vibration for 2 minutes.")

            else:
                print("⚠️ Unknown event:", event)

            self._set_headers(200)
            self.wfile.write(json.dumps({"ok": True}).encode())

        except Exception as e:
            print("❌ Error handling POST:", e)
            self._set_headers(400)
            self.wfile.write(json.dumps({"ok": False}).encode())

    def do_GET(self):
        if self.path == "/api/state":
            self._set_headers(200)
            self.wfile.write(json.dumps(last_data).encode())
        else:
            self._set_headers(404)
            self.wfile.write(b"{}")


PORT = 10000
print(f"✅ Server running on http://0.0.0.0:{PORT}")
HTTPServer(("", PORT), Handler).serve_forever()
