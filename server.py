from http.server import BaseHTTPRequestHandler, HTTPServer
import json

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
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode())
            last_data = data
            print("📩 Received:", data)
            self._set_headers(200)
            self.wfile.write(json.dumps({"ok": True}).encode())
        except:
            self._set_headers(400)
            self.wfile.write(json.dumps({"ok": False}).encode())

    def do_GET(self):
        if self.path == "/api/state":
            self._set_headers(200)
            self.wfile.write(json.dumps(last_data).encode())
        else:
            self._set_headers(404)
            self.wfile.write(b"{}")

PORT = 5501
print(f"✅ Server running on http://0.0.0.0:{PORT}")
HTTPServer(("", PORT), Handler).serve_forever()
