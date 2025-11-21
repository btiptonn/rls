import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ---------------------------
# GLOBAL WASHER STATE
# ---------------------------
washer_state = {
    "state": "Idle",
    "rfid": None,
    "expected": 0,
    "time": "00:00",
    "lock_uid": None,
    "last_update": None,
    "log": []
}

MAX_LOG_ENTRIES = 50

# ---------------------------
# TEXTBELT SMS SETTINGS
# ---------------------------
USER_PHONE = "+1XXXXXXXXXX"      # your number
TEXTBELT_KEY = "textbelt"        # free key

def send_sms(message):
    try:
        print("SMS:", message)
        resp = requests.post(
            "https://textbelt.com/text",
            {
                "phone": USER_PHONE,
                "message": message,
                "key": TEXTBELT_KEY
            }
        )
        print("SMS result:", resp.text)
    except Exception as e:
        print("SMS ERROR:", e)

# ---------------------------
# STATIC ROUTES
# ---------------------------
@app.route("/")
def index_page():
    return send_from_directory(".", "index.html")

@app.route("/washer")
def washer_page():
    return send_from_directory(".", "washer.html")

# ---------------------------
# API — GET STATE
# ---------------------------
@app.route("/api/state", methods=["GET"])
def api_state():
    return jsonify({k: v for k, v in washer_state.items() if k != "log"})

# ---------------------------
# API — GET LOG
# ---------------------------
@app.route("/api/log", methods=["GET"])
def api_log():
    return jsonify(washer_state["log"])

# ---------------------------
# API — UPDATE STATE
# ---------------------------
@app.route("/api/update", methods=["POST"])
def api_update():
    payload = request.get_json(force=True, silent=True) or {}
    now = datetime.utcnow().isoformat() + "Z"

    # Server expects JSON from Pico here:
    # {
    #   "device_id": "...",
    #   "event": "start/tick/abort/complete",
    #   "ts_ms": 123456,
    #   "data": { "uid": "...", "seconds": 30 }
    # }

    event = payload.get("event", "")
    data  = payload.get("data", {})

    # Interpret events:
    if event == "start":
        washer_state["state"] = "Running"
        washer_state["rfid"] = data.get("uid")
        washer_state["expected"] = int(data.get("seconds", 0) // 60)
        washer_state["time"] = f"{data.get('seconds',0)//60:02d}:{data.get('seconds',0)%60:02d}"

    elif event == "tick":
        remaining = data.get("remaining_s", 0)
        washer_state["time"] = f"{remaining//60:02d}:{remaining%60:02d}"

    elif event == "abort":
        washer_state["state"] = "Aborted"

    elif event == "complete":
        washer_state["state"] = "Complete"

    elif event == "unlock":
        washer_state["state"] = "Idle"
        washer_state["rfid"] = None
        washer_state["expected"] = 0
        washer_state["time"] = "00:00"

    washer_state["last_update"] = now

    # Log everything
    log_entry = {
        "ts": now,
        "event": event,
        "state": washer_state["state"],
        "rfid": washer_state["rfid"]
    }

    washer_state["log"].insert(0, log_entry)
    washer_state["log"] = washer_state["log"][:MAX_LOG_ENTRIES]

    # SMS
    if washer_state["state"] == "Complete":
        send_sms("Your laundry cycle is COMPLETE (Machine 1)")

    return jsonify({"ok": True})
    
# ---------------------------
# START
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
