import zmq
import struct
import random
import time

# --- Configuration ---
ADDRESS = "tcp://*:5556"  
PAYLOAD_SIZE = 1024  # <-- Set this to desired size in bytes
DURATION = 90  # seconds to run

# --- Setup ---
context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.setsockopt(zmq.SNDHWM, 0)
socket.bind(ADDRESS)

seq = 1
dummy_data_size = PAYLOAD_SIZE - 12
dummy_data = bytearray([random.randint(0, 255) for _ in range(dummy_data_size)])

print(f"\nSending {PAYLOAD_SIZE}-byte payloads for {DURATION}s...")
start = time.time()
sent = 0

while time.time() - start < DURATION:
    val = random.uniform(0, 4095)
    packed = struct.pack('dI', val, seq) + dummy_data
    socket.send(packed)
    seq += 1
    sent += 1

print(f"Sent {sent} messages of {PAYLOAD_SIZE} bytes")
