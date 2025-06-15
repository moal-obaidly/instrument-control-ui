import numpy as np
import time
import threading
import zmq

# globals
running = False
signal_thread = None
rtt_thread = None
freq = 10
rate = 100

#zmq setup
context = zmq.Context()

# publisher that sends data
pub_socket = context.socket(zmq.PUB)
pub_socket.bind("tcp://*:5556")  

#publisher for rtt
rtt_socket = context.socket(zmq.PUB)
rtt_socket.bind("tcp://*:5558") 

# subscriber logic to get control from ui
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://192.168.1.36:5557")  # 36 for laptop, 82 for rpi 4, 66 for reterminal
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/control")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/slider")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/rateslider")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/rate")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/rtt/response")

def rtt():
    while running:
        rtt_socket.send_string(f"experiment/rtt {time.time()}")
        time.sleep(5)

def start_signal():
    global running, rtt_thread
    t = np.linspace(0, 1, 1000)
    running = True
    if rtt_thread is None or not rtt_thread.is_alive():
        rtt_thread = threading.Thread(target=rtt, daemon=True)
        rtt_thread.start()

    while running:
        signal = np.sin(2 * np.pi * freq * t)
        for value in signal:
            if not running:
                break
            pub_socket.send_string(f"experiment/data {value}")
            print("Sent:", value)
            time.sleep(1 / rate)

def stop_signal():
    global running
    running = False
    print("Signal stopped")

def ui_controls():
    while True:
        try:
            msg = sub_socket.recv_string()
            parts = msg.split(" ", 1)
            topic = parts[0]
            payload = parts[1] if len(parts) > 1 else ""

            print(f"Received on {topic}: {payload}")

            if topic == "experiment/control":
                if payload == "1":
                    global signal_thread
                    if signal_thread is None or not signal_thread.is_alive():
                        signal_thread = threading.Thread(target=start_signal, daemon=True)
                        signal_thread.start()
                elif payload == "0":
                    stop_signal()

            elif topic == "experiment/slider":
                try:
                    global freq
                    freq = float(payload)
                    print("Updated frequency to:", freq)
                except ValueError:
                    print("Invalid frequency value:", payload)

            elif topic in ["experiment/rateslider", "experiment/rate"]:
                try:
                    global rate
                    rate = float(payload)
                    print("Updated sampling rate to:", rate)
                except ValueError:
                    print("Invalid rate value:", payload)

            elif topic == "experiment/rtt/response":
                try:
                    orig_time = float(payload)
                    rtt_ms = (time.time() - orig_time) * 1000
                    # pub_socket.send_string(f"experiment/rtt/display {rtt_ms}")
                    print(f"RTT: {rtt_ms:.2f} ms")
                except ValueError:
                    print("Invalid RTT response value:", payload)

        except zmq.ZMQError as e:
            print("ZMQ error:", e)
            break

# Start control listener in background
ui_thread = threading.Thread(target=ui_controls, daemon=True)
ui_thread.start()

rtt_thread = threading.Thread(target=rtt, daemon=True)
rtt_thread.start()

# Keep main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down")
    running = False
