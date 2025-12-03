# ============================================================
#   RESIDENTIAL LAUNDRY SYSTEM — FIXED + STABLE BACKEND
#   (Correct timer sync, correct heartbeat, no drift, no jumps)
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import requests as py_requests

app = Flask(__name__)
CORS(app)

# --------------------------------------------------
# TEXTBELT SMS CONFIG
# --------------------------------------------------

TEXTBELT_PHONE = "+15555555555"   # <- put your number
TEXTBELT_KEY = "textbelt"         # free tier: 1 msg/day

def send_sms(msg):
    try:
        r = py_requests.post(
            "https://textbelt.com/text",
            data={"phone": TEXTBELT_PHONE, "message": msg, "key": TEXTBELT_KEY}
        )
        print("SMS:", r.text)
    except Exception as e:
        print("SMS ERROR:", e)



# --------------------------------------------------
# MACHINE STATE
# --------------------------------------------------

machine = {
    "state": "Idle",
    "rfid": None,
    "expected": 0,             # in minutes
    "remaining_s": 0,          # always authoritative
    "last_update": None,
    "lock_uid": None,
    "aborted": False,
    "finished_at": None,
    "log": []
}

HEARTBEAT_TIMEOUT = 25           # give Pico grace
ABORT_GRACE_SECONDS = 600        # 10 min
MAX_LOG = 50



# --------------------------------------------------
# LOGGING
# --------------------------------------------------

def log_event(event, info=""):
    machine["log"].insert(0, {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "state": machine["state"],
        "rfid": machine["rfid"],
        "info": info
    })
    machine["log"] = machine["log"][:MAX_LOG]



# --------------------------------------------------
# TIME FORMATTER
# --------------------------------------------------

def format_time(sec):
    sec = max(0, int(sec))
    m = sec // 60
    s = sec % 60
    return f"{m:02d}:{s:02d}"



# --------------------------------------------------
# MASTER TICK LOOP — FIXED
# --------------------------------------------------

def tick():
    now = datetime.utcnow()

    # First tick initialization
    if machine["last_update"] is None:
        machine["last_update"] = now
        return

    delta = (now - machine["last_update"]).total_seconds()

    # No delta or tiny delta → don't touch
    if delta <= 0:
        return

    # -----------------------------
    # HEARTBEAT TIMEOUT (RUNNING)
    # -----------------------------
    if machine["state"] == "Running" and delta > HEARTBEAT_TIMEOUT:
        machine.update({
            "state": "Idle",
            "rfid": None,
            "expected": 0,
            "remaining_s": 0,
            "lock_uid": None,
            "aborted": False,
            "finished_at": None
        })
        log_event("auto-idle", f"Heartbeat loss {delta:.1f}s")
        machine["last_update"] = now
        return

    # -----------------------------
    # RUNNING → Count down normally
    # -----------------------------
    if machine["state"] == "Running":
        machine["remaining_s"] -= delta

        if machine["remaining_s"] <= 0:
            machine["remaining_s"] = 0
            machine["state"] = "Complete"
            machine["aborted"] = False
            machine["finished_at"] = now
            log_event("cycle-complete")
            send_sms("✔ Laundry: Your cycle is COMPLETE. Please pick up your laundry.")

        machine["last_update"] = now
        return

    # -----------------------------
    # ABORTED → Auto-lock after 10 minutes
    # -----------------------------
    if machine["state"] == "Aborted" and machine["finished_at"]:
        since = (now - machine["finished_at"]).total_seconds()
        if since >= ABORT_GRACE_SECONDS:
            machine["state"] = "Locked"
            log_event("auto-lock", "10 min after abort")
            send_sms("⚠ Laundry: Washer LOCKED (no pickup after aborted cycle).")

    machine["last_update"] = now




# ============================================================
# API: STATE ENDPOINT
# ============================================================

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




# ============================================================
# PICO ENDPOINTS
# ============================================================

@app.route("/api/status")
def api_status():
    tick()
    return jsonify({
        "state": machine["state"],
        "remaining_s": machine["remaining_s"],
        "rfid": machine["rfid"],
        "lock_uid": machine["lock_uid"],
    })



# ============================================================
# START
# ============================================================

@app.route("/api/start", methods=["POST"])
def api_start():
    tick()
    data = request.get_json(force=True)

    expected = int(data.get("expected", 0))
    rfid = data.get("rfid")

    if expected <= 0:
        return jsonify({"ok": False, "error": "expected > 0 required"})

    state = machine["state"]
    owner = machine["rfid"]

    # -------------------------------
    # Idle → Always start
    # -------------------------------
    if state == "Idle":
        machine.update({
            "state": "Running",
            "rfid": rfid,
            "expected": expected,
            "remaining_s": expected * 60,
            "lock_uid": rfid,
            "aborted": False,
            "finished_at": None,
            "last_update": datetime.utcnow()
        })
        log_event("start", rfid)
        return jsonify({"ok": True, "state": "Running"})

    # -------------------------------
    # Complete → override allowed
    # -------------------------------
    if state == "Complete":
        # Owner must scan out if same user
        if rfid == owner:
            return jsonify({"ok": False, "error": "Owner must scan out first"})
        # Different RFID → override
        machine.update({
            "state": "Running",
            "rfid": rfid,
            "expected": expected,
            "remaining_s": expected * 60,
            "lock_uid": rfid,
            "aborted": False,
            "finished_at": None,
            "last_update": datetime.utcnow()
        })
        log_event("override-start", rfid)
        return jsonify({"ok": True, "state": "Running"})

    # Aborted / Locked → No start allowed
    if state in ("Aborted", "Locked"):
        return jsonify({"ok": False, "error": "must scan out"})

    # Running → Busy
    return jsonify({"ok": False, "error": "busy"})


# ============================================================
# FINISH (Triggered by Pico)
# ============================================================

@app.route("/api/finish", methods=["POST"])
def api_finish():
    tick()
    now = datetime.utcnow()

    aborted = machine["remaining_s"] > 1

    machine.update({
        "remaining_s": 0,
        "finished_at": now,
        "last_update": now,
        "aborted": aborted
    })

    if aborted:
        machine["state"] = "Aborted"
        log_event("finish-aborted")
        send_sms("🚨 Laundry: Your cycle was ABORTED.")
    else:
        machine["state"] = "Complete"
        log_event("finish-complete")
        send_sms("✔ Laundry: Your cycle is COMPLETE.")

    return jsonify({"ok": True, "state": machine["state"]})



# ============================================================
# SCAN OUT
# ============================================================

@app.route("/api/scan_out", methods=["POST"])
def api_scan_out():
    tick()
    data = request.get_json(force=True)
    rfid = data.get("rfid")

    if not rfid:
        return jsonify({"ok": False, "error": "RFID required"})

    if machine["state"] not in ("Complete", "Aborted", "Locked"):
        return jsonify({"ok": False, "error": "nothing to clear"})

    owner = machine["rfid"]
    lock_uid = machine["lock_uid"]

    # Must be owner or lock UID
    if rfid not in (owner, lock_uid):
        log_event("scan-out-denied", rfid)
        return jsonify({"ok": False, "error": "unauthorized"})

    # Reset machine
    machine.update({
        "state": "Idle",
        "rfid": None,
        "expected": 0,
        "remaining_s": 0,
        "lock_uid": None,
        "finished_at": None,
        "aborted": False,
        "last_update": datetime.utcnow()
    })

    log_event("scan-out-ok", rfid)
    return jsonify({"ok": True, "state": "Idle"})


# ============================================================
# HEARTBEAT
# ============================================================

@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    data = request.get_json(force=True)
    tick()

    # Heartbeat always updates last_update
    machine["last_update"] = datetime.utcnow()

    # Keep only RUNNING safe from override
    pico_state = data.get("state")
    if pico_state == "Running":
        machine["state"] = "Running"

    # Sync RFID if given
    if data.get("rfid") is not None:
        machine["rfid"] = data["rfid"]

    log_event("heartbeat", pico_state)

    return jsonify({
        "ok": True,
        "state": machine["state"],
        "remaining_s": machine["remaining_s"]
    })


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
