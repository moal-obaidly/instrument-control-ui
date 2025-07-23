import struct
import random
import time
import threading
import paho.mqtt.client as mqtt
import psutil

# --- Configuration ---
BROKER = "100.106.113.72"
PORT = 1883
TOPIC = "experiment/data"
CHECKSUM_TOPIC = "experiment/checksum"
RTT_TOPIC = "experiment/rtt"
RTT_RESPONSE_TOPIC = "experiment/rtt/response"
CPU_TOPIC = "experiment/system/cpu"
RAM_TOPIC = "experiment/system/ram"

SAMPLES_PER_BATCH = 100  # 100 × 12B = 1200 bytes
DURATION = 90  # seconds to flood for

# --- MQTT Setup ---
client = mqtt.Client()
rtt_values = []

def on_message(client, userdata, msg):
    if msg.topic == RTT_RESPONSE_TOPIC:
        try:
            sent_time = float(msg.payload.decode())
            rtt = (time.time() - sent_time) * 1000  # ms
            rtt_values.append(rtt)
            print(f"RTT: {rtt:.2f} ms")
        except Exception as e:
            print("RTT decode error:", e)

client.on_message = on_message
client.connect(BROKER, PORT)
client.loop_start()
client.subscribe(RTT_RESPONSE_TOPIC)

# --- RTT Thread ---
def rtt_loop():
    while time.time() - start_time < DURATION:
        client.publish(RTT_TOPIC, str(time.time()))
        time.sleep(1)

# --- CPU/RAM Thread ---
def system_metrics_loop():
    while time.time() - start_time < DURATION:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        client.publish(CPU_TOPIC, str(cpu))
        client.publish(RAM_TOPIC, str(ram))
        time.sleep(1)

# --- Start Threads ---
start_time = time.time()
threading.Thread(target=rtt_loop, daemon=True).start()
threading.Thread(target=system_metrics_loop, daemon=True).start()

# --- Flooding Loop ---
seq_num = 1
checksum = 0

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

# --- Send checksum and print summary ---
client.publish(CHECKSUM_TOPIC, str(checksum))
client.loop_stop()

print("Done flooding. Checksum sent.")
if rtt_values:
    avg_rtt = sum(rtt_values) / len(rtt_values)
    print(f"Average RTT: {avg_rtt:.2f} ms")
