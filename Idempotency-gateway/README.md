# Idempotency-Gateway (The "Pay-Once" Protocol)

## 1. Project Overview
The Idempotency Gateway is a lightweight RESTful API middleware built in Python and Flask. It acts as a safety layer for payment processing, ensuring that no matter how many times a client retries a payment request due to network timeouts, the transaction is processed **exactly once**. It protects against accidental double-charging, intercepts fraudulent payload tampering, and safely handles parallel race conditions.

---

## 2. Architecture Diagram

The following sequence diagram outlines the data flow for the Idempotency Gateway, including the handling of new requests, cached duplicates, payload tampering, and in-flight race conditions.

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant Gateway as Idempotency Gateway (Flask)
    participant Store as Memory Store & Lock
    participant Processor as Payment Processor

    Client->>Gateway: POST /process-payment (Idempotency-Key, Payload)
    Gateway->>Gateway: Generate SHA-256 Hash of Payload

    Gateway->>Store: Acquire Thread Lock & Check Key
    
    alt Key Does Not Exist (Happy Path)
        Store-->>Gateway: Key Not Found
        Gateway->>Store: Save {Hash, Status: IN_PROGRESS}
        Gateway->>Processor: Process Payment (2 sec delay)
        Processor-->>Gateway: Success (200 OK)
        Gateway->>Store: Update {Status: COMPLETED, Response}
        Gateway-->>Client: 200 OK (Payment Processed)

    else Key Exists but Hash Mismatches (Fraud/Tampering)
        Store-->>Gateway: Key Found (Hash Mismatch)
        Gateway-->>Client: 422 Unprocessable Entity

    else Key Exists & Status is IN_PROGRESS (Race Condition)
        Store-->>Gateway: Key Found (Status: IN_PROGRESS)
        Gateway->>Gateway: Loop/Wait until Status == COMPLETED
        Gateway->>Store: Fetch Completed Response
        Store-->>Gateway: Cached Response
        Gateway-->>Client: 200 OK (Header: X-Cache-Hit: true)

    else Key Exists & Hash Matches (Duplicate Retry)
        Store-->>Gateway: Key Found (Status: COMPLETED)
        Gateway-->>Client: 200 OK (Header: X-Cache-Hit: true)
    end

