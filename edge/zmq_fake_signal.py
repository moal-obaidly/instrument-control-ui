import numpy as np
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import time
import zmq
#MQTT setup
ctx = zmq.Context()
sock = ctx.socket(zmq.PUB)
sock.bind("tcp://*:5555")


t = np.linspace(0, 1, 1000)
signal = np.sin(2 * np.pi * 10 * t)
while True:
    for value in signal:
        sock.send_string(str(value))
        print("Sent:", value)
        time.sleep(0.0001)  # simulate 10 kHz sample rate

# plt.plot(t, signal)
# plt.title("Sine Wave")
# plt.xlabel("Time (s)")
# plt.ylabel("Amplitude")
# plt.grid(True)
#plt.show()
sock.close()
ctx.term()
