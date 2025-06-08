# zeromq_receiver.py
import zmq
import time

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5555")  # Replace <sender_ip> with actual IP or use "localhost" if same machine
socket.setsockopt_string(zmq.SUBSCRIBE, "")

while True:
    msg = socket.recv_string()
    sent_time_str, value_str = msg.split(",")
    sent_time = float(sent_time_str)
    latency_ms = (time.time() - sent_time) * 1000
    print(f"Latency: {latency_ms:.3f} ms | Value: {value_str}")
