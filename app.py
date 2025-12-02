from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# In-memory store of all machines
machines = {}

@app.route("/")
def root():
    return "RLS backend up"

# ------------------------------------------------------------------
#  Pico sends updates here
#  POST  /api/update
# ------------------------------------------------------------------
@app.route("/api/update", methods=["POST"])
def update_machine():
    data = request.get_json(force=True)

    device_id = data.get("device_id")
    if not device_id:
        return jsonify({"error": "Missing device_id"}), 400

    # Add server timestamp
    data["last_update"] = datetime.utcnow().isoformat() + "Z"

    # Save state
    machines[device_id] = data

    # Log to Render logs for debugging
    print("UPDATE from", device_id, "=>", data, flush=True)

    return jsonify({"status": "ok"}), 200


# ------------------------------------------------------------------
#  Website reads a specific machine here
#  GET  /api/machines/<device_id>
# ------------------------------------------------------------------
@app.route("/api/machines/<device_id>", methods=["GET"])
def get_machine(device_id):
    machine = machines.get(device_id)
    if not machine:
        return jsonify({"error": "machine not found",
                        "device_id": device_id}), 404
    return jsonify(machine), 200


# ------------------------------------------------------------------
#  Optional debug route: list known machines
#  GET  /api/machines
# ------------------------------------------------------------------
@app.route("/api/machines", methods=["GET"])
def list_machines():
    return jsonify(list(machines.keys())), 200
