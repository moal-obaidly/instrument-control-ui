import numpy as np
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import time
import threading

# MQTT setup
broker = "192.168.1.36"
port = 1883
topic = "experiment/data"

# Globals (remember to add to onMessage function)
running = False
signal_thread = None
freq = 10
rate = 100

def start_signal():
    global running, freq
    t = np.linspace(0, 1, 1000)
    running = True
    while running:
        signal = np.sin(2 * np.pi * freq * t)  # dynamically use current freq
        for value in signal:
            if not running:
                break
            experiment = client.publish(topic, f"{time.time()},{value}", qos=1)
            if experiment.rc != mqtt.MQTT_ERR_SUCCESS:
                print("Disconnected from broker. Stopping signal.")
                stop_signal()
                break
            print("Sent:", value)
            time.sleep(1/rate)
            print("rate:", 1/rate)

def stop_signal():
    global running
    running = False
    print("Signal stopped")

def on_connect(client, userdata, flags, rc):
    print("Connected:", rc)
    client.subscribe("experiment/control")
    client.subscribe("experiment/slider")
    client.subscribe("experiment/rateslider")
    client.subscribe("experiment/rate")

def on_disconnect(client, userdata, rc):
    print("Disconnected from broker... Stopping experiment")
    stop_signal()

    while True:
        try:
            client.reconnect()
            print("Reconnected!")
            break
        except Exception as e:
            print("Reconnect failed, retrying in 5s:", e)
            time.sleep(5)
    


def on_message(client, userdata, msg):
    global signal_thread, freq,rate
    command = msg.payload.decode()
    print(f"Received on {msg.topic}: {command}")
    if msg.topic == "experiment/control":
        if command == "1" and (signal_thread is None or not signal_thread.is_alive()):
            signal_thread = threading.Thread(target=start_signal)
            signal_thread.start()
        elif command == "0":
            stop_signal()
    elif msg.topic == "experiment/slider":
        try:
            freq = float(command)
            print("Updated frequency to:", freq)
        except ValueError:
            print("Invalid frequency value:", command)
    elif msg.topic == "experiment/rateslider":
        try:
            rate = float(command)
            print("Updated sampling rate to:", rate)
        except ValueError:
            print("Invalid sampling rate value:", command)

    elif msg.topic == "experiment/rate":
        try:
            rate = float(command)
            print("Updated sampling rate to:", rate)
        except ValueError:
            print("Invalid sampling rate value:", command)

# MQTT client setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message
client.connect(broker, port, 10)
client.loop_start()

# Keep main thread ALIVE
while True:
    time.sleep(1)