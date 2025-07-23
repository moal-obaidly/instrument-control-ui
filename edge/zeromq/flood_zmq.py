import zmq
import os
import time
import psutil

# --- Config ---------------------------------------------------------------
PUB_PORT      = 5556
PAYLOAD_SIZE  = 1024      # Adjust this (e.g., 64, 256, 1024, 32000)
DURATION      = 30        # seconds to run
total_bytes   = 0
# --------------------------------------------------------------------------

# --- Setup ZMQ PUB socket -------------------------------------------------
context = zmq.Context()
socket  = context.socket(zmq.PUB)
socket.setsockopt(zmq.SNDHWM, 100)       # Back-pressure: 100-message buffer
socket.bind(f"tcp://*:{PUB_PORT}")

# --- Build payload ONCE ---------------------------------------------------
payload = os.urandom(PAYLOAD_SIZE)       # or use b'\0' * PAYLOAD_SIZE

print(f"Sending {PAYLOAD_SIZE}-byte messages for {DURATION}s on tcp://*:{PUB_PORT}")

# --- Send loop ------------------------------------------------------------
start_time = time.time()
last_log   = start_time
sent_bytes = 0

while time.time() - start_time < DURATION:
    # Blocking send with zero-copy
    socket.send(payload, copy=False)

    sent_bytes  += PAYLOAD_SIZE
    total_bytes += PAYLOAD_SIZE

    now = time.time()
    if now - last_log >= 5:
        throughput_kbps = sent_bytes / (now - last_log) / 1000
        print(f"[{time.strftime('%H:%M:%S')}] "
              f"Throughput: {throughput_kbps:,.2f} KB/s | RAM: {psutil.virtual_memory().percent}%")
        sent_bytes = 0
        last_log   = now

print("Done.")
print(f"TOTAL SENT:     {total_bytes:,d} bytes")
