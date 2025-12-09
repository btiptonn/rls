from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

machine = {
    "state": "Idle",
    "rfid": None,
    "end_time": None
}

@app.post("/machine/start")
def machine_start():
    data = request.json
    machine["rfid"] = data["rfid"]
    minutes = data.get("minutes", 45)
    machine["state"] = "Running"
    machine["end_time"] = datetime.utcnow() + timedelta(minutes=minutes)
    return jsonify({"ok": True})

@app.post("/machine/reset")
def machine_reset():
    machine["state"] = "Idle"
    machine["rfid"] = None
    machine["end_time"] = None
    return jsonify({"ok": True})

@app.get("/machine/get")
def machine_get():
    if machine["state"] == "Running":
        remaining = (machine["end_time"] - datetime.utcnow()).total_seconds()
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
        "remaining": int(remaining)
    })

app.run(host="0.0.0.0", port=5000)
