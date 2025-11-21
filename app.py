from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

machines = {}

@app.route("/api/update", methods=["POST"])
def update_machine():
    data = request.get_json()
    device_id = data.get("device_id")
    if not device_id:
        return jsonify({"error": "Missing device_id"}), 400

    data["last_update"] = datetime.utcnow().isoformat() + "Z"
    machines[device_id] = data
    return jsonify({"status": "ok"}), 200


@app.route("/api/machines/<device_id>", methods=["GET"])
def get_machine(device_id):
    machine = machines.get(device_id)
    if not machine:
        return jsonify({
            "error": "machine not found",
            "device_id": device_id
        }), 404
    return jsonify(machine), 200
