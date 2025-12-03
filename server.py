# ============================================================
#   RESIDENTIAL LAUNDRY SYSTEM — FULL BACKEND
#   (State Machine + Logging + Auto-Lock + Textbelt SMS)
# ============================================================

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import requests as py_requests   # <-- For Textbelt SMS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ---------------------------------------------------
# TEXTBELT CONFIG  (Option B: Hard-coded number)
# ---------------------------------------------------

TEXTBELT_PHONE = "+15555555555"     # <--- REPLACE WITH YOUR NUMBER
TEXTBELT_KEY   = "textbelt"         # Free tier = 1 SMS/day

def send_sms(message):
    try:
        r = py_requests.post(
            "https://textbelt.com/text",
            data={
                "phone": TEXTBELT_PHONE,
                "message": message,
                "key": TEXTBELT_KEY
            }
        )
        print("SMS SENT:", r.text)
        return True
    except Exception as e:
        print("SMS ERROR:", e)
        return False


# ---------------------------------------------------
# MACHINE STATE
# ---------------------------------------------------

machine = {
    "state": "Idle",          # Idle, Running, Complete, Aborted, Locked
    "rfid": None,
    "expected": 0,
    "remaining_s": 0,
    "last_update": None,
    "lock_uid": None,
    "finished_at": None,
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
    """ Timer decrement, abort-to-lock, and heartbeat timeout """
    now = datetime.utcnow()

    if machine["last_update"] is None:
        machine["last_update"] = now
        return

    delta = (now - machine["last_update"]).total_seconds()

    # Running → Heartbeat timeout auto-idle
    if delta > HEARTBEAT_TIMEOUT and machine["state"] == "Running":
        machine["state"] = "Idle"
        machine["rfid"] = None
        machine["expected"] = 0
        machine["remaining_s"] = 0
        machine["lock_uid"] = None
        machine["finished_at"] = None
        machine["aborted"] = False
        log_event("auto-idle", f"Timeout {delta:.1f}s")

        machine["last_update"] = now
        return

    # Countdown while running
    if machine["state"] == "Running":
        machine["remaining_s"] = max(0, int(machine["remaining_s"] - delta))

        if machine["remaining_s"] <= 0:
            machine["state"] = "Complete"
            machine["aborted"] = False
            machine["finished_at"] = now
            log_event("cycle-complete")

            # ---- SMS: Cycle Complete ----
            send_sms("✅ Laundry Update: Your cycle is COMPLETE. Please pick up your laundry.")

        machine["last_update"] = now
        return

    # Aborted → after 10 min → Locked
    if machine["state"] == "Aborted" and machine["finished_at"]:
        since = (now - machine["finished_at"]).total_seconds()
        if since > ABORT_GRACE_SECONDS:
            machine["state"] = "Locked"
            log_event("auto-lock", "Abort not cleared in 10 minutes")

            # ---- SMS: Auto-lock ----
            send_sms("⚠️ Laundry Notice: The washer has LOCKED due to no pickup after an aborted cycle.")

            machine["last_update"] = now


# ---------------------------------------------------
# UI ENDPOINTS
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
# PICO ENDPOINTS
# ---------------------------------------------------

@app.route("/api/status")
def api_status():
    tick()
    return jsonify({
        "state": machine["state"],
        "remaining_s": machine["remaining_s"],
        "rfid": machine["rfid"],
        "lock_uid": machine["lock_uid"],
    })


@app.route("/api/start", methods=["POST"])
def api_start():
    tick()
    data = request.get_json(force=True)

    expected = int(data.get("expected", 0))
    rfid = data.get("rfid")
    lock_uid = rfid

    if expected <= 0:
        return jsonify({"ok": False, "error": "expected must be > 0"})

    state = machine["state"]
    owner = machine["rfid"]

    # Idle → Always start
    if state == "Idle":
        machine["state"] = "Running"
        machine["rfid"] = rfid
        machine["expected"] = expected
        machine["remaining_s"] = expected * 60
        machine["lock_uid"] = lock_uid
        machine["finished_at"] = None
        machine["aborted"] = False
        machine["last_update"] = datetime.utcnow()

        log_event("start", rfid)
        return jsonify({"ok": True, "state": "Running"})

    # Complete → Override allowed
    if state == "Complete":
        if owner and rfid != owner:
            machine["state"] = "Running"
            machine["rfid"] = rfid
            machine["expected"] = expected
            machine["remaining_s"] = expected * 60
            machine["lock_uid"] = lock_uid
            machine["finished_at"] = None
            machine["aborted"] = False
            machine["last_update"] = datetime.utcnow()

            log_event("override-start", rfid)
            return jsonify({"ok": True, "state": "Running"})

        return jsonify({"ok": False, "error": "Owner must scan out"})

    # Aborted / Locked → Cannot start
    if state in ("Aborted", "Locked"):
        return jsonify({"ok": False, "error": "must scan out"})

    # Running → Busy
    return jsonify({"ok": False, "error": f"busy ({state})"})


@app.route("/api/finish", methods=["POST"])
def api_finish():
    tick()
    now = datetime.utcnow()

    aborted = machine["remaining_s"] > 0
    machine["remaining_s"] = 0
    machine["finished_at"] = now
    machine["last_update"] = now
    machine["aborted"] = aborted

    if aborted:
        machine["state"] = "Aborted"
        log_event("finish-aborted")

        # ---- SMS: Aborted ----
        send_sms("🚨 Laundry Alert: Your cycle was ABORTED. Please check the washer.")

    else:
        machine["state"] = "Complete"
        log_event("finish-complete")

        # ---- SMS: Complete ----
        send_sms("✅ Laundry Update: Your cycle is COMPLETE. Please pick up your laundry.")

    return jsonify({"ok": True, "state": machine["state"]})


@app.route("/api/scan_out", methods=["POST"])
def api_scan_out():
    tick()
    data = request.get_json(force=True)
    rfid = data.get("rfid")

    if not rfid:
        return jsonify({"ok": False, "error": "RFID needed"})

    if machine["state"] not in ("Complete", "Aborted", "Locked"):
        return jsonify({"ok": False, "error": "nothing to clear"})

    owner = machine["rfid"]
    lock_uid = machine["lock_uid"]

    if rfid != owner and rfid != lock_uid:
        log_event("scan-out-denied", rfid)
        return jsonify({"ok": False, "error": "unauthorized"})

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

    tick()

    pico_state = data.get("state")
    rfid = data.get("rfid")

    # Only sync safe states
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
