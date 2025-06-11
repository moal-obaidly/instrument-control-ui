# zeromq_receiver.py
import zmq
import time

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://192.168.1.34:5555")  
socket.setsockopt_string(zmq.SUBSCRIBE, "")

while True:
    msg = socket.recv_string()
    sent_time_str, value_str = msg.split(",")
    sent_time = float(sent_time_str)
    latency_ms = (time.time() - sent_time) * 1000
    print(f"Latency: {latency_ms:.3f} ms | Value: {value_str}")
