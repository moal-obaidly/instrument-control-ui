# pub.py
import zmq

context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:5556")  # binds to port 5556

print("Publisher ready. Type messages and press Enter to send.")
while True:
    msg = input("> ")
    socket.send_string(msg)
