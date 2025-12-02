import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# -------------------------------------
# GLOBAL MACHINE STATE
# -------------------------------------
machine = {
    "state": "Idle",
    "rfid": None,
    "expected": 0,          # in minutes
    "remaining_s": 0,       # real remaining seconds
    "last_update": None,    # timestamp of last tick
    "lock_uid": None,
    "log": []
}

HEARTBEAT_TIMEOUT = 20       # seconds before auto-idle
MAX_LOG = 50

# -------------------------------------
# HELPER — append to log
# -------------------------------------
def log_event(event, info=""):
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "state": machine["state"],
        "rfid": machine["rfid"],
        "info": info
    }
    machine["log"].insert(0, entry)
    machine["log"] = machine["log"][:MAX_LOG]

# -------------------------------------
# SMS (optional)
# -------------------------------------
USER_PHONE = "+1XXXXXXXXXX"
TEXTBELT_KEY = "textbelt"

def send_sms(msg):
    try:
        print("SMS ->", msg)
        r = requests.post("https://textbelt.com/text", {
            "phone": USER_PHONE,
            "message": msg,
            "key": TEXTBELT_KEY
        })
        print("SMS result:", r.text)
    except:
        print("SMS FAILED")

# -------------------------------------
# STATIC ROUTES
# -------------------------------------
@app.route("/")
def index_page():
    return send_from_directory(".", "index.html")

@app.route("/washer")
def washer_page():
    return send_from_directory(".", "washer.html")

# -------------------------------------
# AUTO-STOP CHECK
# -------------------------------------
def check_heartbeat():
    if machine["state"] == "Running":
        if machine["last_update"]:
            delta = datetime.utcnow() - machine["last_update"]
            if delta.total_seconds() > HEARTBEAT_TIMEOUT:
                # AUTO STOP
                machine["state"] = "Idle"
                machine["rfid"] = None
                machine["remaining_s"] = 0
                machine["expected"] = 0
                log_event("auto_idle", f"no tick for {delta.total_seconds():.1f}s")

# -------------------------------------
# GET STATE
# -------------------------------------
@app.route("/api/state")
def api_state():
    check_heartbeat()
    return jsonify({
        "state": machine["state"],
        "rfid": machine["rfid"],
        "expected": machine["expected"],
        "remaining_s": machine["remaining_s"],
        "last_update": machine["last_update"].isoformat() + "Z" if machine["last_update"] else None
    })

# -------------------------------------
# GET LOG
# -------------------------------------
@app.route("/api/log")
def api_log():
    return jsonify(machine["log"])

# -------------------------------------
# UPDATE FROM PICO
# -------------------------------------
@app.route("/api/update", methods=["POST"])
def api_update():
    payload = request.get_json(force=True)
    event = payload.get("event")
    data = payload.get("data", {})
    now = datetime.utcnow()

    machine["last_update"] = now

    if event == "boot":
        machine["state"] = "Idle"
        machine["rfid"] = None
        machine["remaining_s"] = 0
        machine["expected"] = 0
        log_event("boot")
        return jsonify({"ok": True})

    if event == "start":
        machine["state"] = "Running"
        machine["rfid"] = data.get("uid")
        machine["expected"] = int(data.get("seconds", 0) // 60)
        machine["remaining_s"] = int(data.get("seconds", 0))
        log_event("start", f"uid={machine['rfid']}")
        return jsonify({"ok": True})

    if event == "tick":
        machine["state"] = "Running"
        machine["remaining_s"] = int(data.get("remaining_s", machine["remaining_s"]))
        log_event("tick", f"rem={machine['remaining_s']}")
        return jsonify({"ok": True})

    if event == "abort":
        machine["state"] = "Aborted"
        log_event("abort")
        return jsonify({"ok": True})

    if event == "complete":
        machine["state"] = "Complete"
        machine["remaining_s"] = 0
        log_event("complete")
        send_sms("Your laundry cycle is COMPLETE.")
        return jsonify({"ok": True})

    if event == "unlock":
        machine["state"] = "Idle"
        machine["rfid"] = None
        machine["remaining_s"] = 0
        machine["expected"] = 0
        log_event("unlock")
        return jsonify({"ok": True})

    return jsonify({"error": "unknown event"}), 400

# -------------------------------------
# START
# -------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
