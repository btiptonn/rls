import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ----------------------
#  GLOBAL WASHER STATE
# ----------------------
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

# ----------------------
#  TEXTBELT SMS CONFIG
# ----------------------

USER_PHONE = "+1XXXXXXXXXX"    # <-- PUT YOUR PHONE HERE
TEXTBELT_KEY = "textbelt"      # free key (1 SMS/day)

def send_sms(message):
    """
    Sends a text message using Textbelt API.
    """
    try:
        print("Sending SMS:", message)
        resp = requests.post(
            "https://textbelt.com/text",
            {
                "phone": USER_PHONE,
                "message": message,
                "key": TEXTBELT_KEY
            }
        )
        print("Textbelt response:", resp.text)
    except Exception as e:
        print("SMS ERROR:", e)

# ----------------------
#  STATIC FILE ROUTES
# ----------------------

@app.route("/")
def index_page():
    return send_from_directory(".", "index.html")

@app.route("/washer")
def washer_page():
    return send_from_directory(".", "washer.html")

# ----------------------
#  API ROUTES
# ----------------------

@app.route("/api/state", methods=["GET"])
def api_state():
    data = {k: v for k, v in washer_state.items() if k != "log"}
    return jsonify(data)

@app.route("/api/log", methods=["GET"])
def api_log():
    return jsonify(washer_state["log"])

@app.route("/api/update", methods=["POST"])
def api_update():
    """
    Pico posts updates here.
    Expected JSON:
      state, rfid, expected, time, lock_uid, event
    """
    payload = request.get_json(force=True, silent=True) or {}
    now = datetime.utcnow().isoformat() + "Z"

    # Update fields
    for key in ["state", "rfid", "expected", "time", "lock_uid"]:
        if key in payload:
            washer_state[key] = payload[key]

    washer_state["last_update"] = now

    # Add log entry
    event_text = payload.get("event", f"State -> {washer_state['state']}")
    log_entry = {
        "ts": now,
        "state": washer_state["state"],
        "rfid": washer_state["rfid"],
        "event": event_text
    }

    washer_state["log"].insert(0, log_entry)
    washer_state["log"] = washer_state["log"][:MAX_LOG_ENTRIES]

    # ----------------------
    #   SMS TRIGGER
    # ----------------------
    if washer_state["state"] == "Complete":
        send_sms("Your laundry cycle is complete! (Machine 1)")

    return jsonify({"ok": True, "timestamp": now})

# ----------------------
#  ENTRYPOINT
# ----------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
