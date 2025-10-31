from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Store latest data from the Pico
last_data = {"rfid": "None", "state": "Idle", "time": "00:00"}

@app.route("/api/state", methods=["GET"])
def get_state():
    return jsonify(last_data)

@app.route("/api/state", methods=["POST"])
def update_state():
    global last_data
    data = request.get_json(force=True)
    last_data = data
    print("📩 Received:", data)
    return jsonify({"ok": True})

@app.route("/", methods=["GET"])
def root():
    return "RLS backend is running ✅"

if __name__ == "__main__":
    # Render provides the port number through an environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
