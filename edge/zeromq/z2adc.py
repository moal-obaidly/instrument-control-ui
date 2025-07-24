import numpy as np
import time
import threading
import zmq
import serial
import struct
from collections import deque
import psutil

# globals
running = False
signal_thread = None
rtt_thread = None
buffer_thread = None
freq = 10
rate = 100
checksum = 0
count = 0
singles_sent = 0
batches_sent = 0
seq_num = 1
buffered_data = deque()
#zmq setup
context = zmq.Context()
# ser = serial.Serial('/dev/ttyAMA0', 1000000, timeout=0.0001)
ser = serial.Serial('/dev/ttyAMA0', 3000000, timeout=0.00005)

# publisher that sends data
pub_socket = context.socket(zmq.PUB)
#pub_socket.connect("tcp://localhost:6000")  # connects to XSUB of the proxy old code was :
pub_socket.bind("tcp://*:5556")

#publisher for rtt
rtt_socket = context.socket(zmq.PUB)
rtt_socket.bind("tcp://*:5558") 

# subscriber logic to get control from ui
sub_socket = context.socket(zmq.SUB)
sub_socket.connect("tcp://192.168.1.66:5557")  # 36 for laptop, 82 for rpi 4, 66 for reterminal, 65 for reterminal ethernet, tailscale:100.113.46.57
sub_socket.connect("tcp://192.168.1.36:5557")
sub_socket.connect("tcp://192.168.1.62:5557")
sub_socket.connect("tcp://100.113.46.57:5557")

sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/control")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/slider")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/rateslider")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/rate")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/rtt/response")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "experiment/reset")

def rtt():
    while running:
        rtt_socket.send_string(f"experiment/rtt {time.time()}")
        # CPU usage in %
        cpu_usage = psutil.cpu_percent(interval=0)
        # RAM usage in %
        ram_usage = psutil.virtual_memory().percent

        print(f"CPU Usage: {cpu_usage}%")
        print(f"RAM Usage: {ram_usage}%")
        rtt_socket.send_string(f"experiment/system/cpu {cpu_usage}")
        rtt_socket.send_string(f"experiment/system/ram {ram_usage}")
        time.sleep(1)


def publish_buffer():
    global topic,batches_sent,singles_sent,running
    batch_size = 100
    

    while True:
                   
            if len(buffered_data) >= batch_size and running:
                batch = [buffered_data.popleft() for i in range(batch_size)]
                multi_payload = b''.join(batch)
                result = pub_socket.send_multipart([b"experiment/data", multi_payload])             
                batches_sent+=1
                time.sleep(0.0001)  # cpu safety

                # else:
                #     # Re-buffer the batch
                #     for payload in reversed(batch):
                #         buffered_data.appendleft(payload)
                #     time.sleep(0.01)  # back off a little


            elif buffered_data and running == False:
                payload = buffered_data.popleft()

                
                    
                result = pub_socket.send_multipart([b"experiment/data", payload])
                   
                singles_sent+=1
                time.sleep(0.0001) # cpu safety

   
                # else:
                #     buffered_data.insert(0, payload)
                #     time.sleep(0.01)

            else:
                time.sleep(0.001)

def start_signal():
    global running, rtt_thread, count, buffer_thread,checksum,seq_num
    ser.reset_input_buffer()
    t = np.linspace(0, 1, 1000)
    running = True
    if rtt_thread is None or not rtt_thread.is_alive():
        rtt_thread = threading.Thread(target=rtt, daemon=True)
        rtt_thread.start()
    if buffer_thread is None:
        buffer_thread = threading.Thread(target = publish_buffer, daemon=True)
        buffer_thread.start()

    while running:
            line = ser.readline()
            if line:
                try:
                    value = line.decode(errors='ignore').strip()
                    if value:
                        adc_value = float(value)
                        payload = struct.pack('dI', adc_value,seq_num)
                        seq_num += 1
                        checksum += sum(payload)
                        buffered_data.append(payload)
                        count += 1
                except Exception as e:
                    print("Error:", e)

def stop_signal():
    global running,batches_sent,singles_sent,checksum
    running = False
    print("Signal stopped")
    time.sleep(0.1)
    print(count)
    print(f"batches sent: {batches_sent}")
    print(f"singles sent: {singles_sent}")
    print(checksum)
    pub_socket.send_multipart([b"experiment/checksum", str(checksum).encode()])

def ui_controls():
    global checksum,count,singles_sent,batches_sent,seq_num,buffered_data
    
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
                    rtt_socket.send_string(f"experiment/rtt/display {rtt_ms}")
                    print(f"RTT: {rtt_ms:.2f} ms")
                except ValueError:
                    print("Invalid RTT response value:", payload)
            elif topic == "experiment/reset":
                try:
                    if payload == "1" :
                        checksum = 0
                        count = 0
                        singles_sent = 0
                        batches_sent = 0
                        seq_num = 1
                        buffered_data.clear()
                        
                    
                except ValueError:
                    print("Invalid time value:", payload)

        except zmq.ZMQError as e:
            print("ZMQ error:", e)
            break

# Start control listener in background
ui_thread = threading.Thread(target=ui_controls, daemon=True)
ui_thread.start()



# Keep main thread alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down")
    running = False
