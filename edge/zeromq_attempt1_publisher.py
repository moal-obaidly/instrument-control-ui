# zeromq_sender.py
import zmq
import time
import numpy as np

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:5555")  # Binds to all interfaces

# Generate one second of sine wave
t = np.linspace(0, 1, 1000)
signal = np.sin(2 * np.pi * 5 * t)

while True:
    for value in signal:
        timestamp = time.time()
        message = f"{timestamp},{value}"
        socket.send_string(message)
        time.sleep(0.01)  # simulate 100 Hz
