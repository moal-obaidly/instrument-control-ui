import numpy as np
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import time
import threading

# MQTT setup
broker = "192.168.1.36"
port = 1883
topic = "experiment/data"

# Signal flag
running = False
signal_thread = None

def start_signal():
    global running
    t = np.linspace(0, 1, 1000)
    signal = np.sin(2 * np.pi * 10 * t)
    running = True
    while running:
        for value in signal:
            if not running:
                break
            client.publish(topic, str(value))
            print("Sent:", value)
            time.sleep(0.0001)

def stop_signal():
    global running
    running = False
    print("Signal stopped")

def on_connect(client, userdata, flags, rc):
    print("Connected:", rc)
    client.subscribe("experiment/control")

def on_message(client, userdata, msg):
    global signal_thread
    command = msg.payload.decode()
    print("Received control:", command)

    if command == "1" and (signal_thread is None or not signal_thread.is_alive()):
        signal_thread = threading.Thread(target=start_signal)
        signal_thread.start()
    elif command == "0":
        stop_signal()

# MQTT client setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, port, 60)
client.loop_start()

# Keep main thread alive
while True:
    time.sleep(1)