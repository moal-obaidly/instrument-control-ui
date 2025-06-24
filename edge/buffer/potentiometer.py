import numpy as np
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import time
import threading
import struct
from collections import deque
import serial

# MQTT setup
broker = "192.168.1.82" #.36 for laptop, .82 for rpi4
port = 1883
topic = "experiment/data"

# ADC UART setup
ser = serial.Serial('/dev/ttyAMA0', 115200, timeout=0.1)
# Globals (remember to add to onMessage function)
running = False
signal_thread = None
rtt_thread = None
buffer_thread = None
checksum = 0
count = 0
singles_sent = 0
batches_sent = 0
seq_num = 1

freq = 10
rate = 100
buffered_data = deque()
def rtt():
    while True:

        client.publish("experiment/rtt",time.time())
        time.sleep(5)

def publish_buffer():
    global topic,batches_sent,singles_sent,running
    batch_size = 10
    

    while True:

        # if len(buffered_data) >= batch_size:
        #     batch = [buffered_data.pop(0) for i in range(batch_size)]
        #     multi_payload = b''.join(batch)
        #     client.publish(topic,multi_payload)
        #     time.sleep(0.0001)

        
        # elif buffered_data:
        #     payload = buffered_data.pop(0)

        #     client.publish(topic, payload)
        #     time.sleep(0.0001)  
        # else:
        #     time.sleep(0.001) 
    

        
            if len(buffered_data) >= batch_size and running:
                batch = [buffered_data.popleft() for i in range(batch_size)]
                multi_payload = b''.join(batch)

                if client.is_connected():
                    # client.publish(topic, multi_payload,qos=1)
                    # time.sleep(0.0001)  # prevent flooding


                    result = client.publish(topic, multi_payload,qos=1)
                    if result.rc != 0:
                        print(f"Publish failed (rc={result.rc}) — rebuffering batch")
                        for payload in reversed(batch):
                            buffered_data.appendleft(payload)
                        time.sleep(0.0001)  # cpu safety
                    else:
                        batches_sent+=1
                        time.sleep(0.0001)  # cpu safety

                else:
                    # Re-buffer the batch
                    for payload in reversed(batch):
                        buffered_data.appendleft(payload)
                    time.sleep(0.01)  # back off a little

            # elif buffered_data:
            #     payload = buffered_data.pop(0)

            #     if client.is_connected():
            #         # client.publish(topic, payload)
            #         result = client.publish(topic, payload,qos=1)
            #         if result.rc != 0:
            #             print(f"Publish failed (rc={result.rc}) — rebuffering single")
            #             buffered_data.insert(0, payload)
            #             time.sleep(0.0001)  # cpu safety
            #         else:
            #             single+=1
            #             time.sleep(0.0001) # cpu safety

   
            #     else:
            #         buffered_data.insert(0, payload)
            #         time.sleep(0.01)

            elif buffered_data and running == False:
                payload = buffered_data.popleft()

                if client.is_connected():
                    # client.publish(topic, payload)
                    result = client.publish(topic, payload,qos=1)
                    if result.rc != 0:
                        print(f"Publish failed (rc={result.rc}) — rebuffering single")
                        buffered_data.appendleft(payload)
                        time.sleep(0.0001)  # cpu safety
                    else:
                        singles_sent+=1
                        time.sleep(0.0001) # cpu safety

   
                else:
                    buffered_data.insert(0, payload)
                    time.sleep(0.01)

            else:
                time.sleep(0.001)

            
        


def start_signal():
    global running, freq, rtt_thread, count, buffer_thread,checksum,seq_num
    t = np.linspace(0, 1, 1000)
    
    running = True
    if rtt_thread is None:
        rtt_thread = threading.Thread(target = rtt, daemon=True)
        rtt_thread.start()
    if buffer_thread is None:
        buffer_thread = threading.Thread(target = publish_buffer, daemon=True)
        buffer_thread.start()
    while running:
        line = ser.readline()
        if line:
            try:
                value_str = line.decode(errors='ignore').strip()
                if value_str:
                    adc_value = float(value_str)  # or int(value_str) if ADC is int
                    payload = struct.pack('fI', adc_value, seq_num)  # pack float + seq_num
                    seq_num += 1
                    checksum += sum(payload)
                    buffered_data.append(payload)
                    count += 1
                    time.sleep(1 / rate)  # optional, if you want to slow down to match rate
            except Exception as e:
                print("Error decoding ADC value:", e)


def stop_signal():
    global running, count,singles_sent,batches_sent,checksum
    running = False
    print("Signal stopped")
    print(count)
    print(f"batches sent: {batches_sent}")
    print(f"singles sent: {singles_sent}")
    print(checksum)
    client.publish("experiment/checksum", checksum)



def on_connect(client, userdata, flags, rc):
    print("Connected:", rc)
    client.subscribe("experiment/control")
    client.subscribe("experiment/slider")
    client.subscribe("experiment/rateslider")
    client.subscribe("experiment/rate")
    client.subscribe("experiment/rtt/response")


    #check to see if buffer is empty. if not then send publish all that data
    while len(buffered_data) > 100:
        print(f"{len(buffered_data)} left to send")
        batch_size = 100
        batch = [buffered_data.popleft() for i in range(batch_size)]
        multi_payload = b''.join(batch)

        if client.is_connected():
            client.publish(topic, multi_payload,qos=1)
            time.sleep(0.0001)  # prevent flooding
        # payload = buffered_data.pop(0)
        # client.publish(topic, payload)
    print("Sent buffered data!")


def on_disconnect(client, userdata, rc):
    print("Disconnected! Buffering until reconnected.")


def on_message(client, userdata, msg):
    global signal_thread, freq,rate
    command = msg.payload.decode()
    print(f"Received on {msg.topic}: {command}")
    if msg.topic == "experiment/control":
        if command == "1" and (signal_thread is None or not signal_thread.is_alive()):
            signal_thread = threading.Thread(target=start_signal)
            signal_thread.start()
        elif command == "0":
            stop_signal()
    elif msg.topic == "experiment/slider":
        try:
            freq = float(command)
            print("Updated frequency to:", freq)
        except ValueError:
            print("Invalid frequency value:", command)
    elif msg.topic == "experiment/rateslider":
        try:
            rate = float(command)
            print("Updated sampling rate to:", rate)
        except ValueError:
            print("Invalid sampling rate value:", command)

    elif msg.topic == "experiment/rate":
        try:
            rate = float(command)
            print("Updated sampling rate to:", rate)
        except ValueError:
            print("Invalid sampling rate value:", command)

    elif msg.topic == "experiment/rtt/response":
        try:
            orig_time = float(command)
            rtt = (time.time() - orig_time) * 1000
            client.publish("experiment/rtt/display",rtt)
            print(f"RTT: {rtt:.2f} ms")
        except ValueError:
            print("Invalid time value:", command)
        

# MQTT client setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, port, 2)
client.on_disconnect = on_disconnect

client.loop_start()

# Keep main thread ALIVE
while True:
    time.sleep(1)