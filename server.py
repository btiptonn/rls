from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

machine = {
    "state": "Idle",
    "rfid": None,
    "end_time": None
}

@app.post("/machine/start")
def start():
    data = request.jsonfrom flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# -----------------------------
# MACHINE STATE (REAL STORAGE)
# -----------------------------
machine = {
    "state": "Idle",
    "rfid": None,
    "remaining_s": 0,
    "expected": 0,
    "last_update": None,
    "log": []
}

def log(event, info=""):
    machine["log"].insert(0, {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "info": info,
        "state": machine["state"],
        "rfid": machine["rfid"]
    })
    machine["log"] = machine["log"][:50]


# ------------------------------------
# POST: RFID update from the Pico
# ------------------------------------
@app.route("/machine/set_rfid", methods=["POST"])
def set_rfid():
    data = request.json
    uid = data.get("rfid")

    if not uid:
        return jsonify({"ok": False, "err": "missing_uid"}), 400

    machine["rfid"] = uid
    log("RFID Scanned", uid)

    return jsonify({"ok": True})


# ------------------------------------
# POST: start the washer cycle
# ------------------------------------
@app.route("/machine/start", methods=["POST"])
def start_cycle():
    data = request.json
    minutes = data.get("minutes")
    uid = data.get("rfid")

    if not minutes:
        return jsonify({"ok": False, "err": "missing_minutes"}), 400

    machine["state"] = "Running"
    machine["rfid"] = uid
    machine["expected"] = minutes
    machine["remaining_s"] = minutes * 60
    machine["last_update"] = datetime.utcnow()

    log("Cycle Started", f"{minutes} minutes")

    return jsonify({"ok": True})


# ------------------------------------
# GET: washer status (washer.html calls this)
# ------------------------------------
@app.route("/machine/get")
def get_machine():

    # update remaining time
    if machine["state"] == "Running" and machine["last_update"]:
        delta = datetime.utcnow() - machine["last_update"]
        passed = int(delta.total_seconds())
        machine["remaining_s"] = max(0, machine["remaining_s"] - passed)
        machine["last_update"] = datetime.utcnow()

        if machine["remaining_s"] <= 0:
            machine["state"] = "Finished"
            log("Cycle Finished")

    return jsonify({
        "ok": True,
        "state": machine["state"],
        "remaining_s": machine["remaining_s"],
        "rfid": machine["rfid"],
        "log": machine["log"]
    })


# ------------------------------------
# ROOT
# ------------------------------------
@app.route("/")
def home():
    return jsonify({"ok": True, "service": "RLS Laundry API Server"})


# ------------------------------------
# START SERVER
# ------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0

    minutes = data.get("minutes")
    rfid = data.get("rfid")

    machine["state"] = "Running"
    machine["rfid"] = rfid
    machine["end_time"] = datetime.utcnow() + timedelta(minutes=minutes)

    return jsonify({"ok": True})

@app.post("/machine/reset")
def reset():
    machine["state"] = "Idle"
    machine["rfid"] = None
    machine["end_time"] = None
    return jsonify({"ok": True})

@app.get("/machine/get")
def get_state():
    if machine["state"] == "Running":
        remaining = int((machine["end_time"] - datetime.utcnow()).total_seconds())
        if remaining <= 0:
            machine["state"] = "Idle"
            machine["rfid"] = None
            machine["end_time"] = None
            remaining = 0
    else:
        remaining = 0

    return jsonify({
        "state": machine["state"],
        "rfid": machine["rfid"],
        "remaining": remaining
    })

@app.get("/")
def home():
    return "ok:true"
