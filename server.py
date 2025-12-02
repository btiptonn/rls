# ============================================================
#   RLS BACKEND — ABORT LOCK + SCAN-OUT + OVERRIDE
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
    "state": "Idle",        # "Idle", "Running", "Finished", "Aborted", "Locked", "Error"
    "rfid": None,           # owner of current/last load
    "expected": 0,          # expected minutes
    "remaining_s": 0,       # countdown in seconds
    "last_update": None,    # datetime
    "lock_uid": None,       # usually same as rfid
    "finished_at": None,    # when Finished/Aborted happened
    "aborted": False,       # True if last finish was an abort
    "log": []
}

HEARTBEAT_TIMEOUT = 20            # seconds
ABORT_GRACE_SECONDS = 10 * 60     # 10 minutes
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
    """
    - Running → decrement remaining_s
    - Running timeout → auto Idle
    - Aborted > 10 min with no scan-out → Locked
    """
    now = datetime.utcnow()

    if machine["last_update"] is None:
        machine["last_update"] = now
        return

    delta = (now - machine["last_update"]).total_seconds()

    # Heartbeat timeout while running
    if delta > HEARTBEAT_TIMEOUT and machine["state"] == "Running":
        machine["state"] = "Idle"
        machine["remaining_s"] = 0
        machine["expected"] = 0
        machine["rfid"] = None
        machine["lock_uid"] = None
        machine["finished_at"] = None
        machine["aborted"] = False
        log_event("auto-idle", f"timeout {delta:.1f}s")
        machine["last_update"] = now
        return

    # Normal countdown
    if machine["state"] == "Running" and machine["remaining_s"] > 0:
        machine["remaining_s"] = max(0, int(machine["remaining_s"] - delta))
        machine["last_update"] = now

        if machine["remaining_s"] == 0:
            machine["state"] = "Finished"
            machine["aborted"] = False
            machine["finished_at"] = now
            log_event("cycle-finished")

    # Aborted → after grace time → Locked
    if machine["state"] == "Aborted" and machine["finished_at"] is not None:
        since_finish = (now - machine["finished_at"]).total_seconds()
        if since_finish > ABORT_GRACE_SECONDS:
            machine["state"] = "Locked"
            log_event("locked", "abort not cleared within 10 minutes")
            machine["last_update"] = now


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
        "last_update": machine["last_update"].isoformat() + "Z"
            if machine["last_update"] else None,
        "lock_uid": machine["lock_uid"],
        "finished_at": machine["finished_at"].isoformat() + "Z"
            if machine["finished_at"] else None,
        "aborted": machine["aborted"],
        "log": machine["log"],
    })


@app.route("/api/start", methods=["POST"])
def api_start():
    """
    Start a cycle.

    Rules:
    - If Idle  → always allowed.
    - If Finished:
        * If rfid != owner → override allowed (new user takes over).
        * If rfid == owner → blocked, they should scan out first.
    - Any other state (Aborted/Locked/Running/Error) → blocked.
    """
    tick()
    data = request.get_json(force=True) or {}

    expected = int(data.get("expected", 0))
    rfid = data.get("rfid")
    lock_uid = data.get("lock_uid") or rfid
    state_before = machine["state"]
    owner = machine["rfid"]

    if expected <= 0:
        return jsonify({"ok": False, "error": "expected must be > 0"}), 400

    now = datetime.utcnow()

    # CASE 1: clean Idle
    if state_before == "Idle":
        machine["state"] = "Running"
        machine["expected"] = expected
        machine["remaining_s"] = expected * 60
        machine["rfid"] = rfid
        machine["lock_uid"] = lock_uid
        machine["last_update"] = now
        machine["finished_at"] = None
        machine["aborted"] = False
        log_event("start", f"expected={expected}, rfid={rfid}")
        return jsonify({
            "ok": True,
            "state": "Running",
            "remaining_s": machine["remaining_s"]
        })

    # CASE 2: Finished → can be overridden by different RFID
    if state_before == "Finished":
        if owner and rfid != owner:
            # override allowed
            log_event("override-start", f"from={rfid}, previous_owner={owner}")
            machine["state"] = "Running"
            machine["expected"] = expected
            machine["remaining_s"] = expected * 60
            machine["rfid"] = rfid
            machine["lock_uid"] = lock_uid
            machine["last_update"] = now
            machine["finished_at"] = None
            machine["aborted"] = False
            return jsonify({
                "ok": True,
                "state": "Running",
                "remaining_s": machine["remaining_s"]
            })
        else:
            # same RFID or no owner recorded → must scan out first
            return jsonify({
                "ok": False,
                "error": "previous user must scan out before starting a new load"
            }), 400

    # CASE 3: Running / Aborted / Locked / Error → must scan out / wait
    return jsonify({
        "ok": False,
        "error": f"machine not ready to start (state={state_before})"
    }), 400


@app.route("/api/finish", methods=["POST"])
def api_finish():
    """
    Called by Pico when it thinks the washer stopped.

    - If remaining_s > 0 → Aborted (10-minute pickup window).
    - If remaining_s == 0 → Finished normally.
    """
    tick()
    now = datetime.utcnow()

    aborted = machine["remaining_s"] > 0

    machine["remaining_s"] = 0
    machine["finished_at"] = now
    machine["last_update"] = now
    machine["aborted"] = aborted

    if aborted:
        machine["state"] = "Aborted"
        log_event("finish", "aborted before timer end")
    else:
        machine["state"] = "Finished"
        log_event("finish", "finished normally")

    return jsonify({
        "ok": True,
        "state": machine["state"],
        "aborted": machine["aborted"]
    })


@app.route("/api/stop", methods=["POST"])
def api_stop():
    """
    Hard stop from UI == user abort.
    10-minute window then Locked if not cleared.
    """
    tick()
    now = datetime.utcnow()

    machine["state"] = "Aborted"
    machine["remaining_s"] = 0
    machine["finished_at"] = now
    machine["last_update"] = now
    machine["aborted"] = True

    log_event("stop", "aborted from UI")

    return jsonify({"ok": True, "state": "Aborted"})


@app.route("/api/scan_out", methods=["POST"])
def api_scan_out():
    """
    RFID scan after Finished / Aborted / Locked.
    Only the original RFID (or lock_uid) can clear.
    """
    tick()
    data = request.get_json(force=True) or {}
    rfid = data.get("rfid")

    if not rfid:
        return jsonify({"ok": False, "error": "rfid required"}), 400

    state = machine["state"]
    if state not in ("Finished", "Aborted", "Locked"):
        return jsonify({
            "ok": False,
            "error": f"nothing to scan out (state={state})"
        }), 400

    owner = machine["rfid"]
    locker = machine["lock_uid"] or owner

    if rfid != owner and rfid != locker:
        log_event("scan-out-denied", f"rfid={rfid}")
        return jsonify({"ok": False, "error": "unauthorized RFID"}), 403

    # Clear everything, go Idle
    machine["state"] = "Idle"
    machine["expected"] = 0
    machine["remaining_s"] = 0
    machine["rfid"] = None
    machine["lock_uid"] = None
    machine["finished_at"] = None
    machine["aborted"] = False
    machine["last_update"] = datetime.utcnow()

    log_event("scan-out-ok", f"rfid={rfid}")

    return jsonify({"ok": True, "state": "Idle"})


@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    data = request.get_json(force=True) or {}
    pico_state = data.get("state")
    rfid = data.get("rfid")
    lock_uid = data.get("lock_uid")
    device_id = data.get("device_id")

    tick()  # keep timers/locks correct

    now = datetime.utcnow()
    machine["last_update"] = now

    # Sync state safely:
    if pico_state:
        if pico_state == "Idle" and machine["state"] == "Running":
            # timer controls finish, ignore Pico idle
            log_event("heartbeat", "pico idle ignored (server running)")
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
