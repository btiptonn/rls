# ============================================================
#   RESIDENTIAL LAUNDRY SYSTEM — FINAL FIXED BACKEND
#   All bugs corrected: Aborted timer freeze, RFID sync,
#   scan-out reliability, auto-lock, heartbeat accuracy.
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import requests as py_requests

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------
# TEXTBELT SMS (Option B)
# ---------------------------------------------------

TEXTBELT_PHONE = "+15555555555"      # << CHANGE THIS
TEXTBELT_KEY   = "textbelt"          # free key = 1 SMS/day

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
        print("SMS:", r.text)
    except Exception as e:
        print("SMS ERROR:", e)

# ---------------------------------------------------
# MACHINE STATE
# ---------------------------------------------------

machine = {
    "state": "Idle",       # Idle, Running, Complete, Aborted, Locked
    "rfid": None,
    "expected": 0,
    "remaining_s": 0,
    "last_update": None,
    "finished_at": None,
    "lock_uid": None,
    "aborted": False,
    "log": []
}

HEARTBEAT_TIMEOUT      = 20          # seconds
ABORT_GRACE_SECONDS    = 10 * 60     # 10 minutes
MAX_LOG                = 50

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


# ---------------------------------------------------
# TICK FUNCTION (Time + Auto-Lock + Heartbeat Timeout)
# ---------------------------------------------------

def tick():
    now = datetime.utcnow()

    if machine["last_update"] is None:
        machine["last_update"] = now
        return

    delta = (now - machine["last_update"]).total_seconds()

    # ---------------------------
    # RUNNING → decrement timer
    # ---------------------------
    if machine["state"] == "Running":
        machine["remaining_s"] = max(0, machine["remaining_s"] - delta)

        # heartbeat timeout fail-safe
        if delta > HEARTBEAT_TIMEOUT:
            machine["state"] = "Idle"
            machine["rfid"] = None
            machine["remaining_s"] = 0
            machine["expected"] = 0
            machine["lock_uid"] = None
            log_event("auto-idle-timeout")
            machine["last_update"] = now
            return

        # finished normally
        if machine["remaining_s"] <= 0:
            machine["state"] = "Complete"
            machine["aborted"] = False
            machine["finished_at"] = now
            log_event("cycle-complete")
            send_sms("✅ Laundry: Your cycle is COMPLETE.")

        machine["last_update"] = now
        return

    # ---------------------------
    # ABORTED → freeze time
    # ---------------------------
    if machine["state"] == "Aborted":
        # DO NOT decrement remaining_s — keep frozen
        if machine["finished_at"]:
            since = (now - machine["finished_at"]).total_seconds()

            if since > ABORT_GRACE_SECONDS:
                machine["state"] = "Locked"
                log_event("auto-lock")
                send_sms("⚠️ Laundry: Machine LOCKED (aborted not cleared).")

        machine["last_update"] = now
        return

    # ---------------------------
    # COMPLETE or LOCKED → do nothing
    # ---------------------------
    machine["last_update"] = now


# ---------------------------------------------------
# FRONTEND ENDPOINTS
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
        "lock_uid": machine["lock_uid"]
    })


@app.route("/api/start", methods=["POST"])
def api_start():
    tick()
    data = request.get_json(force=True)

    expected = int(data.get("expected", 0))
    rfid = data.get("rfid")

    if expected <= 0:
        return jsonify({"ok": False, "error": "expected must be > 0"})

    state  = machine["state"]
    owner  = machine["rfid"]

    # -----------------------------------
    # IDLE → always start
    # -----------------------------------
    if state == "Idle":
        machine["state"] = "Running"
        machine["rfid"] = rfid
        machine["expected"] = expected
        machine["remaining_s"] = expected * 60
        machine["finished_at"] = None
        machine["lock_uid"] = rfid
        machine["aborted"] = False
        machine["last_update"] = datetime.utcnow()

        log_event("start", rfid)
        return jsonify({"ok": True, "state": "Running"})

    # -----------------------------------
    # COMPLETE → override allowed
    # -----------------------------------
    if state == "Complete":
        # different user → override
        if rfid != owner:
            machine["state"] = "Running"
            machine["rfid"] = rfid
            machine["expected"] = expected
            machine["remaining_s"] = expected * 60
            machine["finished_at"] = None
            machine["lock_uid"] = rfid
            machine["aborted"] = False
            machine["last_update"] = datetime.utcnow()

            log_event("override-start", rfid)
            return jsonify({"ok": True, "state": "Running"})

        return jsonify({"ok": False, "error": "owner must scan out"})

    # -----------------------------------
    # Aborted/Locked → must scan out
    # -----------------------------------
    if state in ("Aborted", "Locked"):
        return jsonify({"ok": False, "error": "must scan out"})

    # Running → busy
    return jsonify({"ok": False, "error": "busy"})


@app.route("/api/finish", methods=["POST"])
def api_finish():
    tick()
    now = datetime.utcnow()

    aborted = machine["remaining_s"] > 0   # movement stopped early
    machine["remaining_s"] = machine["remaining_s"]  # freeze value
    machine["finished_at"] = now
    machine["last_update"] = now
    machine["aborted"] = aborted

    if aborted:
        machine["state"] = "Aborted"
        log_event("finish-aborted")
        send_sms("🚨 Laundry: Cycle ABORTED.")
    else:
        machine["state"] = "Complete"
        log_event("finish-complete")
        send_sms("✅ Laundry: Cycle COMPLETE.")

    return jsonify({"ok": True, "state": machine["state"]})


@app.route("/api/scan_out", methods=["POST"])
def api_scan_out():
    tick()
    data = request.get_json(force=True)
    rfid = data.get("rfid")

    if machine["state"] not in ("Complete", "Aborted", "Locked"):
        return jsonify({"ok": False, "error": "nothing to clear"})

    owner = machine["rfid"]
    lock_uid = machine["lock_uid"]

    if rfid != owner and rfid != lock_uid:
        return jsonify({"ok": False, "error": "unauthorized"})

    # clear → idle
    machine["state"] = "Idle"
    machine["rfid"] = None
    machine["expected"] = 0
    machine["remaining_s"] = 0
    machine["lock_uid"] = None
    machine["finished_at"] = None
    machine["aborted"] = False
    machine["last_update"] = datetime.utcnow()

    log_event("scan-out", rfid)
    return jsonify({"ok": True, "state": "Idle"})


@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    data = request.get_json(force=True)
    tick()

    pico_state = data.get("state")
    rfid = data.get("rfid")

    # only update state if it's Running
    if pico_state == "Running":
        machine["state"] = "Running"

    # DO NOT WIPE RFID — only set if Pico sends a value
    if rfid:
        machine["rfid"] = rfid

    machine["last_update"] = datetime.utcnow()
    log_event("heartbeat", pico_state)

    return jsonify({
        "ok": True,
        "state": machine["state"],
        "remaining_s": machine["remaining_s"]
    })

# ---------------------------------------------------
# RUN SERVER
# ---------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
