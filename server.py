# ============================================================
#   RLS BACKEND — CLEAN FIXED VERSION
#   Filename: server.py
# ============================================================

import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ---------------------------------------------------
# GLOBAL MACHINE STATE
# ---------------------------------------------------
machine = {
    "state": "Idle",        # "Idle", "Running", "Finished", "Error"
    "rfid": None,
    "expected": 0,          # expected minutes
    "remaining_s": 0,       # countdown in seconds
    "last_update": None,    # datetime
    "lock_uid": None,
    "log": []
}

HEARTBEAT_TIMEOUT = 20
MAX_LOG = 50


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------
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


def format_remaining(seconds: int) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def tick():
    """Decrement the timer and auto-idle on heartbeat timeout."""
    now = datetime.utcnow()

    if machine["last_update"] is None:
        machine["last_update"] = now
        return

    delta = (now - machine["last_update"]).total_seconds()

    # Heartbeat timeout
    if delta > HEARTBEAT_TIMEOUT and machine["state"] == "Running":
        machine["state"] = "Idle"
        machine["remaining_s"] = 0
        machine["expected"] = 0
        machine["rfid"] = None
        log_event("auto-idle", f"timeout {delta:.1f}s")
        machine["last_update"] = now
        return

    # Normal countdown
    if machine["state"] == "Running" and machine["remaining_s"] > 0:
        machine["remaining_s"] = max(0, int(machine["remaining_s"] - delta))
        machine["last_update"] = now

        if machine["remaining_s"] == 0:
            machine["state"] = "Finished"
            log_event("cycle-finished")


# ---------------------------------------------------
# ROUTES
# ---------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/status", methods=["GET"])
def api_status():
    tick()
    return jsonify({
        "state": machine["state"],
        "rfid": machine["rfid"],
        "expected": machine["expected"],
        "remaining_s": machine["remaining_s"],
        "remaining_str": format_remaining(machine["remaining_s"]),
        "last_update": machine["last_update"].isoformat() + "Z" if machine["last_update"] else None,
        "log": machine["log"],
    })


@app.route("/api/start", methods=["POST"])
def api_start():
    data = request.get_json(force=True) or {}

    expected = int(data.get("expected", 0))
    rfid = data.get("rfid")
    lock_uid = data.get("lock_uid")

    if expected <= 0:
        return jsonify({"ok": False, "error": "expected must be > 0"})

    now = datetime.utcnow()

    machine["state"] = "Running"
    machine["expected"] = expected
    machine["remaining_s"] = expected * 60
    machine["rfid"] = rfid
    machine["lock_uid"] = lock_uid
    machine["last_update"] = now

    log_event("start", f"expected={expected}, rfid={rfid}")

    return jsonify({
        "ok": True,
        "state": "Running",
        "remaining_s": machine["remaining_s"]
    })


@app.route("/api/finish", methods=["POST"])
def api_finish():
    tick()
    machine["state"] = "Finished"
    machine["remaining_s"] = 0
    log_event("finish", "finished by Pico")
    machine["last_update"] = datetime.utcnow()

    return jsonify({"ok": True, "state": "Finished"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    tick()
    machine["state"] = "Idle"
    machine["expected"] = 0
    machine["remaining_s"] = 0
    machine["rfid"] = None
    machine["lock_uid"] = None
    machine["last_update"] = datetime.utcnow()

    log_event("stop", "stopped from UI")

    return jsonify({"ok": True, "state": "Idle"})


@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    data = request.get_json(force=True) or {}
    pico_state = data.get("state")
    rfid = data.get("rfid")
    lock_uid = data.get("lock_uid")
    device_id = data.get("device_id")

    tick()  # Keep the server timer accurate

    now = datetime.utcnow()
    machine["last_update"] = now

    # Sync state *safely*
    if pico_state:
        if pico_state == "Idle" and machine["state"] == "Running":
            # keep running until timer hits zero
            log_event("heartbeat", f"pico idle ignored (still running timer)")
        else:
            machine["state"] = pico_state

    if rfid is not None:
        machine["rfid"] = rfid

    if lock_uid is not None:
        machine["lock_uid"] = lock_uid

    log_event("heartbeat", f"from {device_id}, pico_state={pico_state}")

    return jsonify({
        "ok": True,
        "state": machine["state"],
        "remaining_s": machine["remaining_s"]
    })


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
