from flask import Flask, request, jsonify
import time
import threading
import json
import os

app = Flask(__name__)

# --- 1. SHARED MEMORY, LOCK & PERSISTENCE ---
monitors = {}
store_lock = threading.Lock()
STATE_FILE = "state.json"

def load_state():
    """Loads saved monitors from disk when the server starts."""
    global monitors
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                monitors = json.load(f)
                print(f"💾 Loaded {len(monitors)} monitors from disk.")
            except json.JSONDecodeError:
                monitors = {}

def save_state():
    """Saves the current memory dictionary to disk."""
    with open(STATE_FILE, 'w') as f:
        json.dump(monitors, f, indent=2)

# --- 2. THE BACKGROUND WATCHER ---
def watcher_loop():
    print("👀 Watcher Thread Started: Monitoring for offline devices...")
    while True:
        current_time = time.time()
        state_changed = False
        
        with store_lock:
            for device_id, data in monitors.items():
                if data['status'] == 'ACTIVE':
                    if current_time > data['expiration_time']:
                        alert_payload = {
                            "ALERT": f"Device {device_id} is down!",
                            "time": current_time,
                            "contact": data['alert_email']
                        }
                        print(f"\n🚨 CRITICAL ALERT 🚨\n{alert_payload}\n")
                        data['status'] = 'DOWN'
                        state_changed = True
            
            # If a device went down, save the new state to disk
            if state_changed:
                save_state()
                        
        time.sleep(1)

# --- 3. FLASK API ENDPOINTS ---

@app.route('/monitors', methods=['POST'])
def create_monitor():
    payload = request.get_json()
    device_id = payload.get('id')
    timeout = payload.get('timeout', 60)
    alert_email = payload.get('alert_email')

    if not device_id:
        return jsonify({"error": "Device ID is required"}), 400

    with store_lock:
        monitors[device_id] = {
            "status": "ACTIVE",
            "timeout": timeout,
            "expiration_time": time.time() + timeout,
            "alert_email": alert_email
        }
        save_state() # Save to disk!

    return jsonify({"message": f"Monitor created for {device_id}. Timeout: {timeout}s"}), 201


@app.route('/monitors/<device_id>/heartbeat', methods=['POST'])
def heartbeat(device_id):
    with store_lock:
        if device_id not in monitors:
            return jsonify({"error": "Monitor not found"}), 404

        data = monitors[device_id]
        data['expiration_time'] = time.time() + data['timeout']
        data['status'] = 'ACTIVE'
        save_state() # Save to disk!

    return jsonify({"message": f"Heartbeat received for {device_id}. Timer reset."}), 200


@app.route('/monitors/<device_id>/pause', methods=['POST'])
def pause_monitor(device_id):
    with store_lock:
        if device_id not in monitors:
            return jsonify({"error": "Monitor not found"}), 404

        monitors[device_id]['status'] = 'PAUSED'
        save_state() # Save to disk!

    return jsonify({"message": f"Monitor for {device_id} is now PAUSED. No alerts will fire."}), 200


# --- 4. START THE SERVER & THREAD ---
if __name__ == '__main__':
    # Load any saved data before starting
    load_state()
    
    watcher = threading.Thread(target=watcher_loop, daemon=True)
    watcher.start()
    app.run(debug=True, port=5000, use_reloader=False)