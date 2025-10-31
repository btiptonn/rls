from http.server import BaseHTTPRequestHandler, HTTPServer
import json

# Store the latest data received from the Pico
last_data = {
    "rfid": "None",
    "state": "Idle",
    "time": "00:00",
    "expected": 0
}

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
            payload = json.loads(body.decode())
            event = payload.get("event", "")
            data = payload.get("data", {})

            # Update internal state
            if event == "boot":
                last_data["state"] = "Booted"
            elif event == "start":
                last_data["rfid"] = data.get("uid", "Unknown")
                last_data["expected"] = int(data.get("seconds", 0) / 60)
                last_data["state"] = "Running"
            elif event == "tick":
                remaining = data.get("remaining_s", 0)
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                last_data["time"] = f"{mins:02d}:{secs:02d}"
                last_data["state"] = "Running"
            elif event == "complete":
                last_data["state"] = "Complete"
                last_data["time"] = "00:00"
            elif event == "abort":
                last_data["state"] = "Aborted"

            print("📩 Received:", event, "->", last_data)
            self._set_headers(200)
            self.wfile.write(json.dumps({"ok": True}).encode())
        except Exception as e:
            print("Error:", e)
            self._set_headers(400)
            self.wfile.write(json.dumps({"ok": False}).encode())

    def do_GET(self):
        if self.path == "/api/state":
            self._set_headers(200)
            self.wfile.write(json.dumps(last_data).encode())
        else:
            self._set_headers(404)
            self.wfile.write(b"{}")

PORT = 10000  # Render auto-detects port
print(f"✅ Server running on port {PORT}")
HTTPServer(("", PORT), Handler).serve_forever()
