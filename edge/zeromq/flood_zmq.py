import time
import zmq
import random

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.setsockopt(zmq.SNDHWM, 0)
socket.bind("tcp://*:5556")

PAYLOAD_SIZES = [64, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]
DURATION = 10  # seconds

# Warm up
time.sleep(1)

for size in PAYLOAD_SIZES:
    payload = bytes(random.getrandbits(8) for _ in range(size))
    start = time.time()
    count = 0

    print(f"Testing {size}B payload...")

    while time.time() - start < DURATION:
        socket.send(payload)
        count += 1

    total_bytes = count * size
    throughput_kbps = (total_bytes / DURATION) / 1000
    print(f"{size}B payload: {throughput_kbps:.2f} KB/s")

socket.close()
context.term()
