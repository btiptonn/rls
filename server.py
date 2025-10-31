from http.server import BaseHTTPRequestHandler, HTTPServer
import json

# Store latest washer data
last_data = {
    "rfid": "None",
    "state": "Idle",
    "time": "00:00",
    "expected": 0
}

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
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode())
            event = payload.get("event", "").lower()
            data = payload.get("data", {})

            print("📩 Received:", event, data)

            # handle events from Pico
            if event == "boot":
                last_data = {
                    "rfid": "None",
                    "state": "Booted",
                    "time": "00:00",
                    "expected": 0
                }

            elif event == "start":
                uid = data.get("uid", "unknown")
                secs = int(data.get("seconds", 0))
                mm = str(secs // 60).zfill(2)
                ss = str(secs % 60).zfill(2)
                last_data = {
                    "rfid": uid,
                    "state": "Running",
                    "time": f"{mm}:{ss}",
                    "expected": secs // 60
                }

            elif event == "tick":
                rem = int(data.get("remaining_s", 0))
                mm = str(rem // 60).zfill(2)
                ss = str(rem % 60).zfill(2)
                last_data["time"] = f"{mm}:{ss}"

            elif event == "complete":
                last_data["state"] = "Complete"
                last_data["time"] = "00:00"

            elif event == "abort":
                last_data["state"] = "Aborted"
                last_data["time"] = "00:00"

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
print(f"✅ Server running on port {PORT}")
HTTPServer(("", PORT), Handler).serve_forever()
