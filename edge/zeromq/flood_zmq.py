import zmq
import os           # ← for os.urandom
import time
import psutil

# --- Config ---------------------------------------------------------------
PUB_PORT      = 5556
PAYLOAD_SIZE  = 1024      # 64, 256, 1024, …
DURATION      = 30        # seconds to run
# --------------------------------------------------------------------------

# --- Setup ZMQ PUB socket -------------------------------------------------
context = zmq.Context()
socket  = context.socket(zmq.PUB)
socket.setsockopt(zmq.SNDHWM, 1000)      # high-water mark
socket.bind(f"tcp://*:{PUB_PORT}")

# --- Build the payload ONCE ----------------------------------------------
payload = os.urandom(PAYLOAD_SIZE)       # use b'\0' * PAYLOAD_SIZE for zeros

print(f"Sending {PAYLOAD_SIZE}-byte messages for {DURATION}s on tcp://*:{PUB_PORT}")

# --- Send loop ------------------------------------------------------------
start_time = time.time()
last_log   = start_time
sent_bytes = 0

while time.time() - start_time < DURATION:
    try:
        # copy=False avoids an internal memcpy
        socket.send(payload, flags=zmq.NOBLOCK | zmq.COPY_FALSE)
        sent_bytes += PAYLOAD_SIZE
    except zmq.Again:                    # PUB queue is full → short back-off
        time.sleep(0.0005)

    now = time.time()
    if now - last_log >= 5:
        throughput_kbps = sent_bytes / (now - last_log) / 1000
        print(f"[{time.strftime('%H:%M:%S')}] "
              f"Throughput: {throughput_kbps:,.2f} KB/s | RAM: {psutil.virtual_memory().percent}%")
        sent_bytes = 0
        last_log   = now

print("Done.")
