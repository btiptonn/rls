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
    "state": "Idle",      # Idle, Running, Aborted, Complete
    "rfid": None,
    "expected": 0,        # minutes
    "time": "00:00",      # "MM:SS"
    "lock_uid": None,
    "last_update": None,  # UTC timestamp for drift correction
    "log": []
}

MAX_LOG_ENTRIES = 50

# ---------------------------
# TEXTBELT SMS SETTINGS
# ---------------------------
USER_PHONE = "+1XXXXXXXXXX"
TEXTBELT_KEY = "textbelt"

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
# API — RETURN FULL MACHINE STATE
# ---------------------------
@app.route("/api/state", methods=["GET"])
def api_state():
    # Return everything except the log
    return jsonify({
        "state": washer_state["state"],
        "rfid": washer_state["rfid"],
        "expected": washer_state["expected"],
        "time": washer_state["time"],
        "last_update": washer_state["last_update"]
    })

# ---------------------------
# API — RETURN LOG
# ---------------------------
@app.route("/api/log", methods=["GET"])
def api_log():
    return jsonify(washer_state["log"])

# ---------------------------
# API — UPDATE STATE (FROM PICO)
# ---------------------------
@app.route("/api/update", methods=["POST"])
def api_update():
    payload = request.get_json(force=True, silent=True) or {}
    now = datetime.utcnow().isoformat() + "Z"

    event = payload.get("event", "")
    data  = payload.get("data", {})

    # Handle event types
    if event == "start":
        washer_state["state"] = "Running"
        washer_state["rfid"] = data.get("uid")
        seconds = int(data.get("seconds", 0))
        washer_state["expected"] = seconds // 60
        washer_state["time"] = f"{seconds//60:02d}:{seconds%60:02d}"

    elif event == "tick":
        remaining = int(data.get("remaining_s", 0))
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

    washer_state["log"].insert(0, {
        "ts": now,
        "event": event,
        "state": washer_state["state"],
        "rfid": washer_state["rfid"]
    })
    washer_state["log"] = washer_state["log"][:MAX_LOG_ENTRIES]

    if washer_state["state"] == "Complete":
        send_sms("Your laundry cycle is COMPLETE (Machine 1)")

    return jsonify({"ok": True})

# ---------------------------
# START
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
