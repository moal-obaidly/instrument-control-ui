import time
import paho.mqtt.client as mqtt
import random

BROKER = "100.106.113.72"
PORT = 1883
TOPIC = "experiment/data"
PAYLOAD_SIZES = [64, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]
DURATION = 10  # seconds

client = mqtt.Client()
client.connect(BROKER, PORT)
client.loop_start()

for size in PAYLOAD_SIZES:
    payload = bytes(random.getrandbits(8) for _ in range(size))
    start = time.time()
    count = 0

    print(f"Testing {size}B payload...")

    while time.time() - start < DURATION:
        client.publish(TOPIC, payload, qos=0)
        count += 1
        client.loop(timeout=0.001)

    total_bytes = count * size
    throughput_kbps = (total_bytes / DURATION) / 1000
    print(f"{size}B payload: {throughput_kbps:.2f} KB/s")

client.loop_stop()
