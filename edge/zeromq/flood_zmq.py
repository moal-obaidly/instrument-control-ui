import zmq
import time
import struct

SAMPLE_RATE = 100_000              # 100 kHz
PAYLOAD_SIZE = 12                  # 1 sample = 12 bytes (double + int)
DURATION = 30                      # seconds
PUB_PORT = 5556

context = zmq.Context()
socket  = context.socket(zmq.PUB)
socket.setsockopt(zmq.SNDHWM, 1000)
socket.bind(f"tcp://*:{PUB_PORT}")
time.sleep(1.0)  # Give subscriber time to connect

interval = 1.0 / SAMPLE_RATE
sample = struct.pack('dI', 123.456, 1)   # any sample
start = time.perf_counter()
sent = 0

print(f"Sending at 100 kHz for {DURATION}s…")

while time.perf_counter() - start < DURATION:
    now = time.perf_counter()
    socket.send(sample, copy=False)
    sent += len(sample)

    # Wait until next tick
    elapsed = time.perf_counter() - now
    sleep_time = interval - elapsed
    if sleep_time > 0:
        time.sleep(sleep_time)

print(f"Done. Sent {sent:,} bytes ({sent / DURATION / 1e6:.2f} MB/s)")
