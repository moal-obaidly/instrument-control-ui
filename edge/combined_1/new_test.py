import numpy as np
import time
import threading
import struct
from collections import deque
import serial
import psutil
import paho.mqtt.client as mqtt
import zmq

# UART setup
ser = serial.Serial('/dev/ttyAMA0', 3000000, timeout=0.00005)

# Globals
running = False
signal_thread = None
rtt_thread = None
buffer_thread = None
freq = 10
rate = 100
checksum = 0
count = 0
singles_sent = 0
batches_sent = 0
seq_num = 1
buffered_data = deque()

# MQTT setup
broker = "100.106.113.72"
port = 1883
topic = "experiment/data"
client = mqtt.Client()

# ZeroMQ setup
context = zmq.Context()
zmq_pub = context.socket(zmq.PUB)
zmq_pub.bind("tcp://*:5556")
rtt_socket = context.socket(zmq.PUB)
rtt_socket.bind("tcp://*:5558")

sub_socket = context.socket(zmq.SUB)
sub_addrs = [
    "tcp://192.168.1.66:5557",
    "tcp://192.168.1.36:5557",
    "tcp://192.168.1.62:5557",
    "tcp://100.85.112.65:5557",
    "tcp://100.113.46.57:5557"
]
for addr in sub_addrs:
    sub_socket.connect(addr)

subscriptions = [
    "experiment/control", "experiment/slider", "experiment/rateslider",
    "experiment/rate", "experiment/rtt/response", "experiment/reset"
]
for topic in subscriptions:
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)

def rtt():
    while running:
        now = time.time()
        client.publish("experiment/rtt", now)
        rtt_socket.send_string(f"experiment/rtt {now}")

        cpu = psutil.cpu_percent(interval=0)
        ram = psutil.virtual_memory().percent
        client.publish("experiment/system/cpu", str(cpu))
        client.publish("experiment/system/ram", str(ram))
        rtt_socket.send_string(f"experiment/system/cpu {cpu}")
        rtt_socket.send_string(f"experiment/system/ram {ram}")
        time.sleep(1)

def publish_buffer():
    global batches_sent, singles_sent
    batch_size = 1
    while True:
        if running and len(buffered_data) >= batch_size:
            batch = [buffered_data.popleft() for _ in range(batch_size)]
            payload = b''.join(batch)

            # MQTT first
            if client.is_connected():
                result = client.publish(topic, payload, qos=1)
                if result.rc == 0:
                    zmq_pub.send_multipart([b"experiment/data", payload])
                    batches_sent += 1
                else:
                    for p in reversed(batch): buffered_data.appendleft(p)
                    time.sleep(0.01)
            else:
                for p in reversed(batch): buffered_data.appendleft(p)
                time.sleep(0.01)

        elif buffered_data and not running:
            payload = buffered_data.popleft()
            if client.is_connected():
                result = client.publish(topic, payload, qos=1)
                if result.rc == 0:
                    zmq_pub.send_multipart([b"experiment/data", payload])
                    singles_sent += 1
                else:
                    buffered_data.appendleft(payload)
                    time.sleep(0.01)
            else:
                buffered_data.appendleft(payload)
                time.sleep(0.01)
        else:
            time.sleep(0.001)

def start_signal():
    global running, signal_thread, rtt_thread, buffer_thread, seq_num, checksum, count
    running = True

    if not rtt_thread or not rtt_thread.is_alive():
        rtt_thread = threading.Thread(target=rtt, daemon=True)
        rtt_thread.start()
    if not buffer_thread or not buffer_thread.is_alive():
        buffer_thread = threading.Thread(target=publish_buffer, daemon=True)
        buffer_thread.start()

    def loop():
        global seq_num, checksum, count
        BATCH_SIZE = 512
        while running:
            batch = []
            for _ in range(BATCH_SIZE):
                val = 123.456
                payload = struct.pack('dI', val, seq_num)
                batch.append(payload)
                checksum += sum(payload)
                seq_num += 1
            buffered_data.append(b''.join(batch))
            count += BATCH_SIZE
            time.sleep(0.0001)

    signal_thread = threading.Thread(target=loop, daemon=True)
    signal_thread.start()

def stop_signal():
    global running
    running = False
    print("Signal stopped")
    print(f"Total sent: {count}, Batches: {batches_sent}, Singles: {singles_sent}, Checksum: {checksum}")
    client.publish("experiment/checksum", checksum)
    zmq_pub.send_multipart([b"experiment/checksum", str(checksum).encode()])

def ui_controls():
    global freq, rate, seq_num, checksum, count, batches_sent, singles_sent, buffered_data
    while True:
        try:
            msg = sub_socket.recv_string()
            topic, payload = msg.split(" ", 1)

            if topic == "experiment/control":
                if payload == "1":
                    if not signal_thread or not signal_thread.is_alive():
                        start_signal()
                elif payload == "0":
                    stop_signal()

            elif topic == "experiment/slider":
                try: freq = float(payload)
                except: pass
            elif topic in ["experiment/rateslider", "experiment/rate"]:
                try: rate = float(payload)
                except: pass
            elif topic == "experiment/rtt/response":
                try:
                    rtt_val = (time.time() - float(payload)) * 1000
                    rtt_socket.send_string(f"experiment/rtt/display {rtt_val}")
                except: pass
            elif topic == "experiment/reset" and payload == "1":
                checksum = count = singles_sent = batches_sent = 0
                seq_num = 1
                buffered_data.clear()
        except Exception as e:
            print("Control loop error:", e)
            break

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT", rc)
    for topic in subscriptions:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    try:
        ui_controls()  # reuse the same logic
    except:
        pass

client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, port, keepalive=2)
client.loop_start()

ui_thread = threading.Thread(target=ui_controls, daemon=True)
ui_thread.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    running = False
    print("Exiting")
