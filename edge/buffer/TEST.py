import struct
import random
import time
import paho.mqtt.client as mqtt

# --- Configuration ---
BROKER = "100.106.113.72"
PORT = 1883
TOPIC = "experiment/data"
CHECKSUM_TOPIC = "experiment/checksum"

SAMPLES_PER_BATCH = 100  # 100 × 12B = 1200 bytes per message
DURATION = 90  # seconds to flood for

# --- MQTT Setup ---
client = mqtt.Client()
client.connect(BROKER, PORT)
client.loop_start()

# --- Flooding Loop ---
seq_num = 1
checksum = 0
start_time = time.time()

print(f"Flooding {TOPIC} with {SAMPLES_PER_BATCH * 12}B messages as fast as possible for {DURATION} seconds...")

while time.time() - start_time < DURATION:
    batch = []
    for _ in range(SAMPLES_PER_BATCH):
        value = random.uniform(0, 4095)
        packed = struct.pack('dI', value, seq_num)
        checksum += sum(packed)
        batch.append(packed)
        seq_num += 1

    payload = b''.join(batch)
    client.publish(TOPIC, payload, qos=1)

# Send checksum at end
client.publish(CHECKSUM_TOPIC, str(checksum))
client.loop_stop()
print("Done flooding. Checksum sent.")
