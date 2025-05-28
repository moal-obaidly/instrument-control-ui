import numpy as np
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import time
#MQTT setup
broker_ip = "192.168.1.36" 
port = 1883
topic = "experiment/data"

client = mqtt.Client()
client.connect(broker_ip, port, 60)

t = np.linspace(0, 1, 1000)
signal = np.sin(2 * np.pi * 10 * t)
while True:
    for value in signal:
        client.publish(topic, str(value))
        print("Sent:", value)
        time.sleep(0.001)  # simulate 1 kHz sample rate

plt.plot(t, signal)
plt.title("Sine Wave")
plt.xlabel("Time (s)")
plt.ylabel("Amplitude")
plt.grid(True)
#plt.show()

