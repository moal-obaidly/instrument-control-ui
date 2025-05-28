import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
from collections import deque

# Settings
broker_ip = "192.168.1.36"  
topic = "experiment/data"

# Signal buffer
data = deque(maxlen=1000)

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe(topic)

def on_message(client, userdata, msg):
    try:
        value = float(msg.payload.decode())
        data.append(value)
        plt.cla()
        plt.plot(data)
        plt.pause(0.001)
    except Exception as e:
        print("Error:", e)

# Setup MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker_ip, 1883, 60)

# Plot live
plt.ion()
plt.figure()
client.loop_start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    client.loop_stop()
    plt.ioff()
    plt.show()