import sys
import paho.mqtt.client as mqtt
import time
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5 import QtWidgets, QtCore
from datetime import datetime
import zmq
import threading

from collections import deque
import sys

#globals
record = 0
csv_status = 1
count = 0

####################################################################################
# MQTT Client Setup
class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.data = []
        self.rtt = 0
        self.buffer = 0
        

        

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code", rc)
        client.subscribe("experiment/data")
        client.subscribe("experiment/rtt")
        client.subscribe("experiment/rtt/display")

    def on_message(self, client, userdata, msg):
        global csv_status
        if msg.topic == "experiment/data":
            try:
                payload = msg.payload.decode()
                sent_time_str, value_str = payload.split(",")
                sent_time = float(sent_time_str)
                value = float(value_str)
                #timerec = int(time.time()*1000.0)

                self.data.append(value)
                self.buffer= value
                #print(f"Value at time{timerec}= {value}")

                #latency = (time.time() - sent_time) * 1000
                #print(f"Latency: {latency:.2f} ms")

                if record == 1:
                    try:
                        with open("signal.csv", "a") as f:
                            csv_status = 1
                            timestamp = datetime.now().isoformat() # gets the current date and time
                            f.write(f"{timestamp},{value}\n")
                            
                    except IOError:
                        print("Could not write to CSV. Please close CSV file and try again")
                        csv_status = 0


                if len(self.data) > 1000:
                    self.data.pop(0)
            except Exception as e:
                print("Bad message:", msg.payload, "| Error:", e)
        elif msg.topic == "experiment/rtt":
            try:
                payload = msg.payload.decode()
                orig_time = float(payload)
                client.publish("experiment/rtt/response",orig_time)

            except Exception as e:
                print("Bad message:", msg.payload, "| Error:", e)
        
        elif msg.topic == "experiment/rtt/display":
            try:
                payload = msg.payload.decode()
                self.rtt = float(payload)
                

            except Exception as e:
                print("Bad message:", msg.payload, "| Error:", e)
           

    def start(self):
        self.client.connect("192.168.1.36", 1883, 60) #.36 for laptop, .82 for rpi4
        self.client.loop_start()



#############################################################################



class zmq_Subscriber:
    def __init__(self,socket_address,topic):
        
        #creating a zmq subscriber which connects to a socket and then listens to certain topics
        self.rtt = 0

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(socket_address) #36 for laptop, 82 for rpi4
        self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        self.socket.setsockopt(zmq.RCVHWM, 10000)

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

        

    def get_all_messages(self):
        values = []
        while True:
            socks = dict(self.poller.poll(0))
            if self.socket in socks:
                try:
                    msg = self.socket.recv_string(flags=zmq.NOBLOCK)
                    parts = msg.split(" ", 1)
                    topic = parts[0]
                    payload = parts[1]
                    values.append(float(payload))  
                except zmq.Again:
                    break
            else:
                break
        return values
    

class zmq_Publisher():
    def __init__(self):
        #creating a zmq pub which binds to a socket to publish messages
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:5557") #36 for laptop, 82 for rpi4
        

#class Worker(QObject):
#    finished = pyqtSignal()
#    progress = pyqtSignal(int)

    #def run(self):
        
    #    self.finished.emit()

# PyQt GUI



class MainWindow(QWidget):
    def __init__(self):
        global record,screen_size
        screen_size = 0
        import pyqtgraph as pg
        super().__init__()
        self.setWindowTitle("Signal Monitor")
        

        if screen_size == 0:
            self.showNormal()
        else:
            self.showFullScreen()
            
        
        # MQTT
        self.mqtt_client = MQTTClient()
        self.mqtt_client.start()
        #zmq




        # self.context = zmq.Context()
        # self.socket = self.context.socket(zmq.SUB)
        # self.socket.connect("tcp://192.168.1.82:5556")
        # self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        # self.socket.setsockopt(zmq.RCVHWM, 10000)

        # self.poller = zmq.Poller()
        # self.poller.register(self.socket, zmq.POLLIN)

        self.zmq_sub_client = zmq_Subscriber("tcp://192.168.1.33:5556","experiment/data")#34 for rpi5, 33 for rpi ethernet, 82 for pi4
        self.zmq_pub_client = zmq_Publisher()

        self.rtt_client = zmq_Subscriber("tcp://192.168.1.33:5558","")


        self.data = deque(maxlen=1000)






        self.rtt_thread = threading.Thread(target=self.rtt, daemon=True)
        self.rtt_thread.start()
        # Layouts
        horizontal_main_layout = QtWidgets.QHBoxLayout(self)
        main_layout = QtWidgets.QVBoxLayout(self)
        control_layout = QtWidgets.QHBoxLayout()
        experiment_layout = QtWidgets.QHBoxLayout()
        rate_layout = QtWidgets.QVBoxLayout()
        sampling_layout = QtWidgets.QVBoxLayout()
        switch_layout =  QtWidgets.QVBoxLayout()
        record_layout = QtWidgets.QHBoxLayout()

        # Plot
        self.plot_widget = pg.PlotWidget(title="Live Signal")
        self.curve = self.plot_widget.plot()

        # Buttons
        self.reset_btn = QtWidgets.QPushButton("Reset Graph")
        self.reset_btn.clicked.connect(self.reset_graph)

        self.start_button = QtWidgets.QPushButton("Start Experiment")
        self.start_button.clicked.connect(self.start_experiment)

        self.stop_button = QtWidgets.QPushButton("Stop Experiment")
        self.stop_button.clicked.connect(self.stop_experiment)

        self.low_sample_rate_btn = QtWidgets.QPushButton("Sampling rate: 100 Hz")
        self.low_sample_rate_btn.clicked.connect(self.low_sample_rate)

        self.med_sample_rate_btn = QtWidgets.QPushButton("Sampling rate: 1000 Hz")
        self.med_sample_rate_btn.clicked.connect(self.med_sample_rate)

        self.high_sample_rate_btn = QtWidgets.QPushButton("Sampling rate: 10000 Hz")
        self.high_sample_rate_btn.clicked.connect(self.high_sample_rate)

        self.start_record_btn = QtWidgets.QPushButton("Start recording data")
        self.start_record_btn.clicked.connect(self.start_record)
        self.stop_record_btn = QtWidgets.QPushButton("Stop recording data")
        self.stop_record_btn.clicked.connect(self.stop_record)

        self.toggle_layout_btn = QtWidgets.QPushButton("Switch Layout")
        self.toggle_layout_btn.clicked.connect(self.toggle_layout)

        self.toggle_screen_btn = QtWidgets.QPushButton("Toggle screen")
        self.toggle_screen_btn.clicked.connect(self.toggle_screen)

        self.close_screen_btn = QtWidgets.QPushButton("Close screen")
        self.close_screen_btn.clicked.connect(self.close_screen)

        

        # Slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(self.on_slider_change)

        # Labels

        self.slider_label = QtWidgets.QLabel("Frequency: 50")

        self.last_values_label = QtWidgets.QLabel("Last 5 Values:\n")

        self.recording_label = QtWidgets.QLabel("Not recording")

        self.rtt_label = QtWidgets.QLabel(f"RTT:{str(self.rtt_client.rtt)}ms")

        

         # Slider for sampling rate
        self.rate_slider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        self.rate_slider.setMinimum(1)
        self.rate_slider.setMaximum(10000)
        self.rate_slider.setValue(100)
        self.rate_slider.valueChanged.connect(self.on_rate_slider_change)
        self.rate_slider_label = QtWidgets.QLabel("Sampling rate: 100 Hz")
        
        

        # Toggle between slider and button selection for the rate
        self.layout_stack = QtWidgets.QStackedLayout()
        rate_widget = QtWidgets.QWidget()
        rate_widget.setLayout(rate_layout)

        sampling_widget = QtWidgets.QWidget()
        sampling_widget.setLayout(sampling_layout)

        self.layout_stack.addWidget(rate_widget)    
        self.layout_stack.addWidget(sampling_widget)

        
        #Styling

        self.close_screen_btn.setStyleSheet("background-color : red")
        self.toggle_screen_btn.setStyleSheet("background-color : yellow")




        # Layout setup
        main_layout.addWidget(self.plot_widget)

        control_layout.addWidget(self.reset_btn)
        control_layout.addWidget(self.slider_label)
        control_layout.addWidget(self.slider)
        
        
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.rtt_label)
        #main_layout.addWidget(self.last_values_label)

        experiment_layout.addWidget(self.start_button)
        experiment_layout.addWidget(self.stop_button)
        main_layout.addLayout(experiment_layout)

        rate_layout.addWidget(self.low_sample_rate_btn)
        rate_layout.addWidget(self.med_sample_rate_btn)
        rate_layout.addWidget(self.high_sample_rate_btn)
        rate_layout.addWidget(self.toggle_screen_btn)
        rate_layout.addWidget(self.close_screen_btn)
        horizontal_main_layout.addLayout(main_layout)
        #horizontal_main_layout.addLayout(rate_layout)

        sampling_layout.addWidget(self.rate_slider_label)
        sampling_layout.addWidget(self.rate_slider)
        #horizontal_main_layout.addLayout(sampling_layout)
        switch_layout.addWidget(self.toggle_layout_btn)
        switch_layout.addLayout(self.layout_stack)
        horizontal_main_layout.addLayout(switch_layout)


        record_layout.addWidget(self.start_record_btn)
        record_layout.addWidget(self.stop_record_btn)
        record_layout.addWidget(self.recording_label)
        main_layout.addLayout(record_layout)

        
        

        # Timer to update plot
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)

    def update_last_values_display(self):
        recent_values = self.mqtt_client.data[-5:]
        text = "\n".join([f"{v:.4f}" for v in recent_values])
        self.last_values_label.setText(f"Last 5 Values:\n{text}")

    def rtt(self):
        while True:
            try:
                msg = self.rtt_client.socket.recv_string(flags=zmq.NOBLOCK)
                parts = msg.split(" ", 1)
                
                topic = parts[0]
                payload = parts[1]
                if topic == "experiment/rtt":
                    print(f"received {payload}")
                    self.zmq_pub_client.socket.send_string(f"experiment/rtt/response {payload}")
                elif topic == "experiment/rtt/display":
                    self.rtt_client.rtt = float(payload)
                    self.rtt_label.setText(f"RTT: {self.rtt_client.rtt:.2f} ms")
            except zmq.Again:
                
                time.sleep(0.01)

    def update_plot(self):
        global count
        # while True:
        #     socks = dict(self.poller.poll(0))
        #     if self.socket in socks:
        #         try:
        #             msg = self.socket.recv_string(flags=zmq.NOBLOCK)
        #             value = float(msg)
        #             self.data.append(value)
                    
        #         except zmq.Again:
        #             break
        #     else:
        #         break
        
        # if self.data:
        #     self.curve.setData(list(range(len(self.data))), list(self.data))
        
        values = self.zmq_sub_client.get_all_messages()
        for i in values:
            self.data.append(i)
            count+=1
        
        if self.data:
            self.curve.setData(list(range(len(self.data))), list(self.data))

        
            
            

       


    def reset_graph(self):
        self.mqtt_client.data = []

    def on_slider_change(self, value):
        self.slider_label.setText(f"Frequency: {value}")
        self.zmq_pub_client.socket.send_string(f"experiment/slider {value}")
    
    def on_rate_slider_change(self, value):
        self.rate_slider_label.setText(f"Sampling rate: {value} Hz")
        self.zmq_pub_client.socket.send_string(f"experiment/rateslider {value}")

    def start_experiment(self):
        self.zmq_pub_client.socket.send_string("experiment/control 1")

    def stop_experiment(self):
        global count
        self.zmq_pub_client.socket.send_string("experiment/control 0")
        recent_values = self.mqtt_client.data[-5:]
        print(recent_values)
        print(self.mqtt_client.buffer)
        print(count)
# Different possible simulated sampling rates
    def low_sample_rate(self):
        self.zmq_pub_client.socket.send_string("experiment/rate 100")

    def med_sample_rate(self):
        self.zmq_pub_client.socket.send_string("experiment/rate 1000")

    def high_sample_rate(self):
        self.zmq_pub_client.socket.send_string("experiment/rate 10000")
    
    def start_record(self): 
        global record, csv_status
        record = 1
        if csv_status == 1:
            self.recording_label.setText("Recording")
        else:
            self.recording_label.setText("Failed to record")

    def stop_record(self): 
        global record
        record = 0
        self.recording_label.setText("Stopped Recording")

    def toggle_layout(self):
        index = self.layout_stack.currentIndex()
        new_index = (index + 1) % self.layout_stack.count()
        self.layout_stack.setCurrentIndex(new_index)

    def toggle_screen(self):
        global screen_size
        if self.isFullScreen():
            self.showNormal()
            screen_size = 0
        else:
            self.showFullScreen()
            screen_size = 1

    def close_screen(self):
        print(list(self.data)[-10:])

        self.close()
        
    
        

app = QApplication(sys.argv)
# Main app
def main():
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
