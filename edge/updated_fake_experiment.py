import numpy as np
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import time
import threading

# MQTT setup
broker = "192.168.1.82" #.36 for laptop, .82 for rpi4
port = 1883
topic = "experiment/data"


# Globals (remember to add to onMessage function)
running = False
signal_thread = None
rtt_thread = None
count = 0

freq = 10
rate = 100

def rtt():
    while True:

        client.publish("experiment/rtt",time.time())
        time.sleep(5)

def start_signal():
    global running, freq, rtt_thread, count
    t = np.linspace(0, 1, 1000)
    running = True
    if rtt_thread is None:
        rtt_thread = threading.Thread(target = rtt, daemon=True)
        rtt_thread.start()
    while running:
        signal = np.sin(2 * np.pi * freq * t)  # dynamically use current freq
        for value in signal:
            if not running:
                break
            client.publish(topic, f"{time.time()},{value}")
            count+=1
            #### Checking RTT
            #client.publish("experiment/rtt",time.time())
            ####
            print("Sent:", value)
            time.sleep(1/rate)
            print("rate:", 1/rate)

def stop_signal():
    global running
    running = False
    print("Signal stopped")
    print(count)

def on_connect(client, userdata, flags, rc):
    print("Connected:", rc)
    client.subscribe("experiment/control")
    client.subscribe("experiment/slider")
    client.subscribe("experiment/rateslider")
    client.subscribe("experiment/rate")
    client.subscribe("experiment/rtt/response")

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

    elif msg.topic == "experiment/rtt/response":
        try:
            orig_time = float(command)
            rtt = (time.time() - orig_time) * 1000
            client.publish("experiment/rtt/display",rtt)
            print(f"RTT: {rtt:.2f} ms")
        except ValueError:
            print("Invalid time value:", command)
        

# MQTT client setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, port, 60)
client.loop_start()

# Keep main thread ALIVE
while True:
    time.sleep(1)