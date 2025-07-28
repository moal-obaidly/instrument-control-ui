import numpy as np
import time
import threading
import struct
from collections import deque
import psutil
import paho.mqtt.client as mqtt
import zmq
import random

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
buffered_data_mqtt = deque()
buffered_data_zmq = deque()


# MQTT setup
broker = "100.106.113.72"
port = 1883
topic = "experiment/data"
client = mqtt.Client()

# ZeroMQ setup
context = zmq.Context()
zmq_pub = context.socket(zmq.PUB)
zmq_pub.bind("tcp://*:5556")
#publisher for rtt
rtt_socket = context.socket(zmq.PUB)
rtt_socket.bind("tcp://*:5558") 

# subscriber logic to get control from ui
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://192.168.1.66:5557")
sub_socket.connect("tcp://192.168.1.36:5557")
sub_socket.connect("tcp://192.168.1.62:5557")
sub_socket.connect("tcp://100.85.112.65:5557")
sub_socket.connect("tcp://100.113.46.57:5557")

sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/control")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/slider")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/rateslider")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/rate")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/rtt/response")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/reset")

# main Functions
def rtt():
    while running:
        ts = time.time()
        client.publish("experiment/rtt", ts)
        rtt_socket.send_string(f"experiment/rtt {time.time()}")

        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent

        client.publish("experiment/system/cpu", str(cpu))
        client.publish("experiment/system/ram", str(ram))
        rtt_socket.send_string(f"experiment/system/cpu {cpu}")
        rtt_socket.send_string(f"experiment/system/ram {ram}")
        time.sleep(1)

def mqtt_publish_buffer():
    global batches_sent, singles_sent
    batch_size = 100

    while True:
        if running and len(buffered_data_mqtt) >= batch_size:
            batch = [buffered_data_mqtt.popleft() for _ in range(batch_size)]
            payload = b''.join(batch)

            success = False
            while not success:
                if client.is_connected():
                    res = client.publish(topic, payload, qos=1)
                    if res.rc == 0:
                        success = True
                        batches_sent += 1
                        time.sleep(0.0001)
                    else:
                        print("MQTT batch failed, retrying...")
                else:
                    print("MQTT disconnected, retrying...")

                if not success:
                    for p in reversed(batch):
                        buffered_data_mqtt.appendleft(p)
                    time.sleep(0.000001)

        elif not running and buffered_data_mqtt:
            small_batch = [buffered_data_mqtt.popleft() for _ in range(min(100, len(buffered_data_mqtt)))]
            payload = b''.join(small_batch)

            if client.is_connected():
                res = client.publish(topic, payload, qos=1)
                if res.rc == 0:
                    singles_sent += 1
                else:
                    for p in reversed(small_batch):
                        buffered_data_mqtt.appendleft(p)
                    time.sleep(0.1)
            else:
                for p in reversed(small_batch):
                    buffered_data_mqtt.appendleft(p)
                time.sleep(0.1)
        else:
            time.sleep(0.001)

def zmq_publish_buffer():
    while True:
        if running and buffered_data_zmq:
            payload = buffered_data_zmq.popleft()
            zmq_pub.send_multipart([b"experiment/data", payload])
        elif not running and buffered_data_zmq:
            payload = buffered_data_zmq.popleft()
            zmq_pub.send_multipart([b"experiment/data", payload])
        else:
            time.sleep(0.0001)



def start_signal():
    global running, count, checksum, seq_num
    running = True

    if rtt_thread is None or not rtt_thread.is_alive():
        threading.Thread(target=rtt, daemon=True).start()
    if buffer_thread is None or not buffer_thread.is_alive():
            threading.Thread(target=mqtt_publish_buffer, daemon=True).start()
            threading.Thread(target=zmq_publish_buffer, daemon=True).start()

    BATCH_SIZE = 100
    while running:
        batch = []
        for _ in range(BATCH_SIZE):
            adc = 123.456
            payload = struct.pack('dI', adc, seq_num)
            checksum += sum(payload)
            batch.append(payload)
            seq_num += 1
        joined = b''.join(batch)
        buffered_data_mqtt.append(joined)
        buffered_data_zmq.append(joined)

        count += BATCH_SIZE
        time.sleep(0.0001)

def stop_signal():
    global running
    running = False
    print("Signal stopped.")
    time.sleep(0.5)
    print(f"Count: {count}, Batches: {batches_sent}, Singles: {singles_sent}, Checksum: {checksum}")
    client.publish("experiment/checksum", checksum)
    zmq_pub.send_multipart([b"experiment/checksum", str(checksum).encode()])

def on_connect(client, userdata, flags, rc):
    print("Connected:", rc)
    topics = [
        "experiment/control",
        "experiment/slider",
        "experiment/rateslider",
        "experiment/rate",
        "experiment/rtt/response",
        "experiment/reset"
    ]
    for t in topics:
        client.subscribe(t)

def on_message(client, userdata, msg):
    global freq, rate, signal_thread, checksum, count, singles_sent, batches_sent, seq_num
    command = msg.payload.decode()
    print(f"MQTT msg on {msg.topic}: {command}")

    if msg.topic == "experiment/control":
        if command == "1":
            if signal_thread is None or not signal_thread.is_alive():
                signal_thread = threading.Thread(target=start_signal, daemon=True)
                signal_thread.start()
        elif command == "0":
            stop_signal()
            zmq_pub.send_multipart([b"experiment/stopped", str(checksum).encode()])

    elif msg.topic == "experiment/slider":
        try: freq = float(command)
        except: print("Bad frequency")

    elif msg.topic in ["experiment/rateslider", "experiment/rate"]:
        try: rate = float(command)
        except: print("Bad rate")

    elif msg.topic == "experiment/rtt/response":
        try:
            orig = float(command)
            rtt_ms = (time.time() - orig) * 1000
            client.publish("experiment/rtt/display", rtt_ms)
            print(f"RTT: {rtt_ms:.2f} ms")
        except:
            print("Bad RTT response")

    elif msg.topic == "experiment/reset" and command == "1":
        checksum = count = singles_sent = batches_sent = 0
        seq_num = 1
        buffered_data.clear()

def ui_controls():
    global checksum,count,singles_sent,batches_sent,seq_num,buffered_data

    while True:
        try:
            msg = sub_socket.recv_string()
            parts = msg.split(" ", 1)
            topic = parts[0]
            payload = parts[1] if len(parts) > 1 else ""

            print(f"Received on {topic}: {payload}")

            if topic == "experiment/control":
                if payload == "1":
                    global signal_thread
                    if signal_thread is None or not signal_thread.is_alive():
                        signal_thread = threading.Thread(target=start_signal, daemon=True)
                        signal_thread.start()
                elif payload == "0":
                    stop_signal()

            elif topic == "experiment/slider":
                try:
                    global freq
                    freq = float(payload)
                    print("Updated frequency to:", freq)
                except ValueError:
                    print("Invalid frequency value:", payload)

            elif topic in ["experiment/rateslider", "experiment/rate"]:
                try:
                    global rate
                    rate = float(payload)
                    print("Updated sampling rate to:", rate)
                except ValueError:
                    print("Invalid rate value:", payload)

            elif topic == "experiment/rtt/response":
                try:
                    orig_time = float(payload)
                    rtt_ms = (time.time() - orig_time) * 1000
                    rtt_socket.send_string(f"experiment/rtt/display {rtt_ms}")
                    print(f"RTT: {rtt_ms:.2f} ms")
                except ValueError:
                    print("Invalid RTT response value:", payload)
            elif topic == "experiment/reset":
                try:
                    if payload == "1" :
                        checksum = 0
                        count = 0
                        singles_sent = 0
                        batches_sent = 0
                        seq_num = 1
                        buffered_data.clear()

                except ValueError:
                    print("Invalid time value:", payload)

        except zmq.ZMQError as e:
            print("ZMQ error:", e)
            break

# Start control listener in background
ui_thread = threading.Thread(target=ui_controls, daemon=True)
ui_thread.start()

# MQTT init
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, port, keepalive=2)
client.loop_start()

#Keep Alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down...")
    running = False
