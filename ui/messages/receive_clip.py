# sub.py
import zmq

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://192.168.1.36:5556")  # connect to publisher
socket.setsockopt_string(zmq.SUBSCRIBE, "")  # subscribe to all messages

print("Subscriber connected. Waiting for messages...")
while True:
    msg = socket.recv_string()
    print(f"Received: {msg}")
