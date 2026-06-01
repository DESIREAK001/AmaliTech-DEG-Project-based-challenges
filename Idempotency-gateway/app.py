from flask import Flask, request, jsonify, make_response
import time
import threading
import hashlib
import json

app = Flask(__name__)

idempotency_store = {}
store_lock = threading.Lock()

#HELPER FUNCTION: The Payload Hasher 
def generate_payload_hash(payload):
    # json.dumps converts the dictionary to a string.
    # sort_keys=True is CRUCIAL! It ensures {"a":1, "b":2} and {"b":2, "a":1} result in the same hash.
    payload_string = json.dumps(payload, sort_keys=True)
    # hashlib requires the string to be encoded into bytes
    return hashlib.sha256(payload_string.encode('utf-8')).hexdigest()

@app.route('/process-payment', methods=['POST'])
def process_payment():
    idem_key = request.headers.get('Idempotency-Key')
    if not idem_key:
        return jsonify({"error": "Idempotency-Key header is missing"}), 400

    payload = request.get_json()
    
    # Generate the hash of the incoming request
    incoming_hash = generate_payload_hash(payload)
    is_first_request = False

    with store_lock:
        if idem_key not in idempotency_store:
            # First time seeing this key. Save the HASH, not the heavy payload!
            idempotency_store[idem_key] = {
                "status": "IN_PROGRESS",
                "payload_hash": incoming_hash 
            }
            is_first_request = True
        else:
            # Duplicate attempt detected. Let's do the fraud check using the hashes.
            saved_data = idempotency_store[idem_key]
            
            if saved_data['payload_hash'] != incoming_hash:
                return jsonify({"error": "Idempotency key already used for a different request body."}), 422

    #  IN-FLIGHT CHECK (Request B) 
    if not is_first_request:
        while idempotency_store[idem_key]['status'] == 'IN_PROGRESS':
            time.sleep(0.1) 
        
        final_data = idempotency_store[idem_key]
        response = make_response(jsonify(final_data['body']), final_data['status_code'])
        response.headers['X-Cache-Hit'] = 'true'
        return response

    #  THE PAYMENT PROCESSING (Request A) 
    amount = payload.get('amount')
    currency = payload.get('currency', 'GHS')
    
    time.sleep(2) # 2-second simulated delay

    response_body = {"status": f"Charged {amount} {currency}"}
    status_code = 200

    # Lock again to save the final results
    with store_lock:
        idempotency_store[idem_key].update({
            "status": "COMPLETED",
            "body": response_body,
            "status_code": status_code
        })

    return jsonify(response_body), status_code

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)