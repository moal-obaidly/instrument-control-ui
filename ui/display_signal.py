import paho.mqtt.client as mqtt
import matplotlib.pyplot as plt
from collections import deque
import time
from datetime import datetime

# Settings
broker_ip = "192.168.1.36"  
topic = "experiment/data"

# Signal buffer
data = deque(maxlen=1000)

# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connection successful. Listening to", topic)
        client.subscribe(topic)
    else:
        print("Connection failed. Please restart.")

def on_message(client, userdata, msg):
    try:
        value = float(msg.payload.decode())
        data.append(value)
        #save to CSV. Maybe change this later.
        with open("signal.csv", "a") as f:
            timestamp = datetime.now().isoformat() # gets the current date and time
            f.write(f"{timestamp},{value}\n") # saves the time as well as the value in csv. useful for logging maybe
    except Exception as e:
        print("Error:", e)

# Setup MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker_ip, 1883, 60)
client.loop_start()

# Plot setup
plt.ion()
fig, ax = plt.subplots()
line, = ax.plot([], [], lw=2)
ax.set_ylim(-1.5, 1.5)
ax.set_xlim(0, 1000)

# Main loop updates the plot (not MQTT thread!)
try:
    while True:
        y_data = list(data)
        x_data = list(range(len(y_data)))
        line.set_xdata(x_data)
        line.set_ydata(y_data)
        ax.set_xlim(max(0, len(y_data) - 1000), len(y_data))

        fig.canvas.draw()
        fig.canvas.flush_events()
        time.sleep(0.02)  # 50 fps
except KeyboardInterrupt:
    client.loop_stop()
    plt.ioff()
    plt.show()