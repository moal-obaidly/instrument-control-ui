import numpy as np
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import time
import threading
import struct
from collections import deque
import serial
import psutil



# MQTT setup
broker = "100.106.113.72" #.36 for laptop, .82 for rpi4, 100.106.113.72
port = 1883
topic = "experiment/data"

# ADC UART setup
#ser = serial.Serial('/dev/ttyAMA0', 1000000, timeout=0.0001)
ser = serial.Serial('/dev/ttyAMA0', 3000000, timeout=0.000005)
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
##########################


def rtt():


    while True:

        client.publish("experiment/rtt",time.time())
        # CPU usage in %
        cpu_usage = psutil.cpu_percent(interval=0)
        # RAM usage in %
        ram_usage = psutil.virtual_memory().percent

        print(f"CPU Usage: {cpu_usage}%")
        print(f"RAM Usage: {ram_usage}%")
        client.publish("experiment/system/cpu", str(cpu_usage))
        client.publish("experiment/system/ram", str(ram_usage))
        time.sleep(1)



def publish_buffer():


    global topic,batches_sent,singles_sent,running
    batch_size = 2000
    

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
##################################################################
            if len(buffered_data) >= batch_size and running:
                batch = [buffered_data.popleft() for _ in range(batch_size)]
                multi_payload = b''.join(batch)

                success = False
                while not success:
                    if client.is_connected():
                        result = client.publish(topic, multi_payload, qos=1)
                        if result.rc == 0:
                            success = True
                            batches_sent += 1
                            time.sleep(0.0001)  
                        else:
                            print(f"Publish failed (rc={result.rc}) — retrying batch")
                    else:
                        print("Waiting for reconnection...")

                    # If failed, rebuffer and pause slightly before retrying
                    if not success:
                        
                        for payload in reversed(batch):
                            buffered_data.appendleft(payload)
                        time.sleep(0.1)  
        
            # if len(buffered_data) >= batch_size and running:
            #     batch = [buffered_data.popleft() for i in range(batch_size)]
            #     multi_payload = b''.join(batch)

            #     if client.is_connected():
            #         # client.publish(topic, multi_payload,qos=1)
            #         # time.sleep(0.0001)  # prevent flooding


            #         result = client.publish(topic, multi_payload,qos=1)
            #         if result.rc != 0:
            #             print(f"Publish failed (rc={result.rc}) — rebuffering batch")
            #             for payload in reversed(batch):
            #                 buffered_data.appendleft(payload)
            #             while not client.is_connected():
            #                 print("Waiting for reconnection...")
            #                 time.sleep(0.1)

            #                 # DO NOT move on — let it retry the same batch on next loop
            #             continue
            #             time.sleep(0.0001)  # cpu safety
            #         else:
            #             batches_sent+=1
            #             time.sleep(0.0001)  # cpu safety

            #     else:
            #         # Re-buffer the batch
            #         for payload in reversed(batch):
            #             buffered_data.appendleft(payload)
            #         time.sleep(0.0001)  # back off a little
            ####################################################################################

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
                batch_size_stopped = min(100, len(buffered_data))
                batch_stopped = [buffered_data.popleft() for i in range(batch_size_stopped)]
                multi_payload_stopped = b''.join(batch_stopped)
                
                

                if client.is_connected():
                    # client.publish(topic, payload)
                    result = client.publish(topic, multi_payload_stopped,qos=1)
                    if result.rc != 0:
                        # print(f"Publish failed (rc={result.rc}) — rebuffering single")
                        for payload in reversed(batch_stopped):
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
    ser.reset_input_buffer()  # resets the uart buffer. so old values are cleared and it can start reading new ones(from when start is pressed)

    
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
                
                adc_value = float(value_str)  # or int(value_str) if ADC is int
                payload = struct.pack('dI', adc_value, seq_num)  # pack float + seq_num
                seq_num += 1
                checksum += sum(payload)
                buffered_data.append(payload)
                count += 1
                # print(f"RAW LINE: {line}")

                    
            except Exception as e:
                print("Error decoding ADC value:", e)
    
    # global running, freq, rtt_thread, count, buffer_thread, checksum, seq_num
    # running = True
    # if rtt_thread is None:
    #     rtt_thread = threading.Thread(target=rtt, daemon=True)
    #     rtt_thread.start()
    # if buffer_thread is None:
    #     buffer_thread = threading.Thread(target=publish_buffer, daemon=True)
    #     buffer_thread.start()

    # buffer = b""
    # while running:
    #     data = ser.read(ser.in_waiting or 1)
    #     buffer += data
    #     while b'\n' in buffer:
    #         line, buffer = buffer.split(b'\n', 1)
    #         line = line.strip()
    #         if line:
    #             try:
    #                 adc_value = int(line)
    #                 payload = struct.pack('dI', adc_value, seq_num)
    #                 seq_num += 1
    #                 checksum += sum(payload)
    #                 buffered_data.append(payload)
    #                 count += 1
    #                 if count % 1000 == 0:
    #                     print(f"Sample {count}: {adc_value}")
    #             except Exception as e:
    #                 print(f"Bad line: {line} | {e}")


def stop_signal():


    global running, count,singles_sent,batches_sent,checksum
    running = False
    print("Signal stopped")
    time.sleep(0.1)
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
    client.subscribe("experiment/reset")


    #check to see if buffer is empty. if not then send publish all that data
    # if buffered_data:
    #     print(f"Draining {len(buffered_data)} buffered samples...")

    # while len(buffered_data) > 0:
    #     batch_size = min(500, len(buffered_data))  # send big batches
    #     batch = [buffered_data.popleft() for _ in range(batch_size)]
    #     multi_payload = b''.join(batch)

    #     if client.is_connected():
    #         result = client.publish(topic, multi_payload, qos=1)
    #         if result.rc != 0:
    #             print(f"Publish failed (rc={result.rc}) — rebuffering batch")
    #             for payload in reversed(batch):
    #                 buffered_data.appendleft(payload)
    #             break  # stop flushing if there's a problem
    #     else:
    #         print("Disconnected while flushing.")
    #         for payload in reversed(batch):
    #             buffered_data.appendleft(payload)
    #         break

    #     #pause
    #     time.sleep(0.001)

    # if not buffered_data:
    #     print("Sent buffered data!")

def on_disconnect(client, userdata, rc):


    print("Disconnected! Buffering until reconnected.")


def on_message(client, userdata, msg):


    global signal_thread, freq,rate,checksum,count,singles_sent,batches_sent,seq_num ,buffered_data

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
    elif msg.topic == "experiment/reset":
        try:
            if command == "1" :
                checksum = 0
                count = 0
                singles_sent = 0
                batches_sent = 0
                seq_num = 1
                buffered_data.clear()
                
            
        except ValueError:
            print("Invalid time value:", command)

# MQTT client setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, port, keepalive=2)
client.on_disconnect = on_disconnect

client.loop_start()

# Keep main thread ALIVE
while True:
    time.sleep(1)