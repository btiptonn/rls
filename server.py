# ============================================================
#   RLS BACKEND — COMPLETE STATE, ABORT LOCK, OVERRIDE, LOG
# ============================================================

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ---------------------------------------------------
# MACHINE STATE
# ---------------------------------------------------
machine = {
    "state": "Idle",          # Idle, Running, Complete, Aborted, Locked
    "rfid": None,             # who started the load
    "expected": 0,            # minutes
    "remaining_s": 0,         # seconds
    "last_update": None,
    "lock_uid": None,
    "finished_at": None,      # datetime
    "aborted": False,
    "log": []
}

HEARTBEAT_TIMEOUT = 20
ABORT_GRACE_SECONDS = 10 * 60
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


def format_time(sec):
    sec = max(0, int(sec))
    m, s = divmod(sec, 60)
    return f"{m:02d}:{s:02d}"


def tick():
    """ Timer decrement, abort-to-lock, heartbeat timeout """
    now = datetime.utcnow()

    if machine["last_update"] is None:
        machine["last_update"] = now
        return

    delta = (now - machine["last_update"]).total_seconds()

    # Running → heartbeat timed out
    if delta > HEARTBEAT_TIMEOUT and machine["state"] == "Running":
        machine["state"] = "Idle"
        machine["rfid"] = None
        machine["remaining_s"] = 0
        machine["expected"] = 0
        machine["lock_uid"] = None
        machine["finished_at"] = None
        machine["aborted"] = False
        log_event("auto-idle", f"Timeout {delta:.1f}s")
        machine["last_update"] = now
        return

    # Countdown
    if machine["state"] == "Running":
        machine["remaining_s"] = max(0, int(machine["remaining_s"] - delta))
        machine["last_update"] = now

        if machine["remaining_s"] <= 0:
            machine["state"] = "Complete"
            machine["aborted"] = False
            machine["finished_at"] = now
            log_event("cycle-complete")
            return

    # Aborted → after grace → Locked
    if machine["state"] == "Aborted" and machine["finished_at"]:
        since = (now - machine["finished_at"]).total_seconds()
        if since > ABORT_GRACE_SECONDS:
            machine["state"] = "Locked"
            log_event("auto-lock", "Abort not cleared in 10 minutes")
            machine["last_update"] = now


# ---------------------------------------------------
# API ENDPOINTS FOR UI
# ---------------------------------------------------

@app.route("/api/state")
def api_state():
    tick()
    return jsonify({
        "state": machine["state"],
        "time": format_time(machine["remaining_s"]),
        "rfid": machine["rfid"],
        "expected": machine["expected"],
        "lock_uid": machine["lock_uid"]
    })


@app.route("/api/log")
def api_log():
    tick()
    return jsonify(machine["log"])


# ---------------------------------------------------
# PICO API ENDPOINTS
# ---------------------------------------------------

@app.route("/api/status", methods=["GET"])
def api_status():
    tick()
    return jsonify({
        "state": machine["state"],
        "remaining_s": machine["remaining_s"],
        "rfid": machine["rfid"],
        "lock_uid": machine["lock_uid"]
    })


@app.route("/api/start", methods=["POST"])
def api_start():
    tick()
    data = request.get_json(force=True)

    expected = int(data.get("expected", 0))
    rfid = data.get("rfid")
    lock_uid = rfid

    if expected <= 0:
        return jsonify({"ok": False, "error": "expected must be >0"}), 400

    state = machine["state"]
    owner = machine["rfid"]

    # Idle → always start
    if state == "Idle":
        now = datetime.utcnow()
        machine["state"] = "Running"
        machine["rfid"] = rfid
        machine["expected"] = expected
        machine["remaining_s"] = expected * 60
        machine["lock_uid"] = lock_uid
        machine["finished_at"] = None
        machine["aborted"] = False
        machine["last_update"] = now
        log_event("start", f"{rfid}")
        return jsonify({"ok": True, "state": "Running"})

    # Complete → override allowed by different user
    if state == "Complete":
        if owner and rfid != owner:
            now = datetime.utcnow()
            machine["state"] = "Running"
            machine["rfid"] = rfid
            machine["expected"] = expected
            machine["remaining_s"] = expected * 60
            machine["lock_uid"] = lock_uid
            machine["finished_at"] = None
            machine["aborted"] = False
            machine["last_update"] = now
            log_event("override-start", f"{rfid}")
            return jsonify({"ok": True, "state": "Running"})
        else:
            return jsonify({"ok": False, "error": "Owner must scan out"}), 400

    # Aborted / Locked → must scan out
    if state in ("Aborted", "Locked"):
        return jsonify({"ok": False, "error": "must scan out"}), 400

    # Running → cannot start
    return jsonify({"ok": False, "error": f"busy ({state})"}), 400


@app.route("/api/finish", methods=["POST"])
def api_finish():
    tick()
    now = datetime.utcnow()

    # If timer > 0 → Aborted
    aborted = machine["remaining_s"] > 0
    machine["remaining_s"] = 0
    machine["finished_at"] = now
    machine["last_update"] = now
    machine["aborted"] = aborted

    if aborted:
        machine["state"] = "Aborted"
        log_event("finish-aborted")
    else:
        machine["state"] = "Complete"
        log_event("finish-complete")

    return jsonify({"ok": True, "state": machine["state"]})


@app.route("/api/scan_out", methods=["POST"])
def api_scan_out():
    tick()
    data = request.get_json(force=True)
    rfid = data.get("rfid")

    if not rfid:
        return jsonify({"ok": False, "error": "RFID needed"}), 400

    if machine["state"] not in ("Complete", "Aborted", "Locked"):
        return jsonify({"ok": False, "error": "nothing to clear"}), 400

    owner = machine["rfid"]
    lock_uid = machine["lock_uid"]

    if rfid != owner and rfid != lock_uid:
        log_event("scan-out-denied", rfid)
        return jsonify({"ok": False, "error": "unauthorized"}), 403

    # Clear → Idle
    machine["state"] = "Idle"
    machine["rfid"] = None
    machine["expected"] = 0
    machine["remaining_s"] = 0
    machine["lock_uid"] = None
    machine["finished_at"] = None
    machine["aborted"] = False
    machine["last_update"] = datetime.utcnow()

    log_event("scan-out-ok", rfid)
    return jsonify({"ok": True, "state": "Idle"})


@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    data = request.get_json(force=True)
    pico_state = data.get("state")
    rfid = data.get("rfid")

    tick()

    # Sync only safe states
    if pico_state and pico_state not in ("Running",):
        machine["state"] = pico_state

    if rfid is not None:
        machine["rfid"] = rfid

    machine["last_update"] = datetime.utcnow()
    log_event("heartbeat", pico_state)

    return jsonify({
        "ok": True,
        "state": machine["state"],
        "remaining_s": machine["remaining_s"]
    })


# ---------------------------------------------------
# RUN
# ---------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
