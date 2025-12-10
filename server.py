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
    data = request.json
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
