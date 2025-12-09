from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------------
# MACHINE STATE
# ------------------------------------------------------------
machine = {
    "state": "Idle",          # Idle | Running | Finished
    "rfid": None,             # last RFID scanned
    "expected_min": 0,
    "remaining_s": 0,
    "last_update": None,
    "log": []
}

HEARTBEAT_TIMEOUT = 10
MAX_LOG = 50


# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------
def log(event, info=""):
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "state": machine["state"],
        "rfid": machine["rfid"],
        "info": info
    }
    machine["log"].insert(0, entry)
    machine["log"] = machine["log"][:MAX_LOG]


# ------------------------------------------------------------
# TICK / HEARTBEAT
# ------------------------------------------------------------
def tick():
    if machine["state"] != "Running":
        return

    now = datetime.utcnow()

    # Missed heartbeat?
    if machine["last_update"]:
        if (now - machine["last_update"]).total_seconds() > HEARTBEAT_TIMEOUT:
            machine["state"] = "Idle"
            machine["remaining_s"] = 0
            log("ERROR", "Lost heartbeat")
            return

    machine["last_update"] = now

    # Decrement
    if machine["remaining_s"] > 0:
        machine["remaining_s"] -= 1
        if machine["remaining_s"] <= 0:
            machine["state"] = "Finished"
            log("FINISHED")


# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/washer")
def washer():
    return render_template("washer.html")


@app.route("/machine/get")
def get_machine():
    tick()
    return jsonify(machine)


@app.route("/machine/set_rfid", methods=["POST"])
def set_rfid():
    data = request.json
    uid = data.get("rfid")
    machine["rfid"] = uid
    log("RFID", uid)
    return jsonify({"ok": True})


@app.route("/machine/start", methods=["POST"])
def start_machine():
    data = request.json
    minutes = int(data.get("minutes", 30))
    uid = data.get("rfid")

    machine["state"] = "Running"
    machine["rfid"] = uid
    machine["expected_min"] = minutes
    machine["remaining_s"] = minutes * 60
    machine["last_update"] = datetime.utcnow()

    log("START", f"{minutes} minutes")

    return jsonify({"ok": True})


@app.route("/machine/reset", methods=["POST"])
def reset_machine():
    machine["state"] = "Idle"
    machine["expected_min"] = 0
    machine["remaining_s"] = 0
    log("RESET")
    return jsonify({"ok": True})


@app.route("/logs")
def get_logs():
    return jsonify(machine["log"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
