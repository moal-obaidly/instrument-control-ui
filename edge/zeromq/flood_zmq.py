import zmq
import struct
import random
import time
import psutil

# --- Config ---
PUB_PORT = 5556
PAYLOAD_SIZE = 1024  # Adjust this (e.g., 64, 256, 1024, etc.)
DURATION = 30        # Run for this many seconds
BATCH_SIZE = PAYLOAD_SIZE // 12  # One sample = 12 bytes (double + int)

# --- Setup ZMQ PUB socket ---
context = zmq.Context()
socket = context.socket(zmq.PUB)

# Set high water mark to prevent memory overload
socket.setsockopt(zmq.SNDHWM, 1000)

socket.bind(f"tcp://*:{PUB_PORT}")

print(f"Sending {PAYLOAD_SIZE}-byte messages for {DURATION}s on tcp://*:{PUB_PORT}")

# --- Send loop ---
seq = 1
checksum = 0
start_time = time.time()
sent_bytes = 0
last_log = time.time()

while time.time() - start_time < DURATION:
    batch = []
    for _ in range(BATCH_SIZE):
        value = random.uniform(0, 4095)
        packed = struct.pack('dI', value, seq)
        batch.append(packed)
        checksum += sum(packed)
        seq += 1

    payload = b''.join(batch)

    try:
        socket.send(payload, flags=zmq.NOBLOCK)
        sent_bytes += len(payload)
    except zmq.Again:
        print("Buffer full! Dropping batch...")
        time.sleep(0.001)  # back off if overwhelmed

    # Throughput log every 5 seconds
    now = time.time()
    if now - last_log >= 5:
        throughput_kbps = sent_bytes / (now - last_log) / 1000
        print(f"[{time.strftime('%H:%M:%S')}] Throughput: {throughput_kbps:.2f} KB/s | RAM: {psutil.virtual_memory().percent}%")
        sent_bytes = 0
        last_log = now

print("Done. Final checksum:", checksum)
