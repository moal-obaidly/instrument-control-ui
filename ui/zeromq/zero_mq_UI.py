import sys
import paho.mqtt.client as mqtt
import time
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QTimer
from datetime import datetime
import zmq
import threading
import struct
import os
from zplot_signal import plot_experiment
import matplotlib 
matplotlib.use("Qt5Agg") 
import matplotlib.pyplot as plt

from collections import deque
import sys

#globals
record = 0
csv_status = 1
count = 0
sample_count=0

####################################################################################
current_working_directory = os.getcwd()
experiments_folder = f"{current_working_directory}/Experiments"
past_experiments = 0
# Count the number of files in the *experiments* directory
for path in os.listdir(experiments_folder):
    if os.path.isfile(os.path.join(experiments_folder,path)):
        past_experiments+=1

print(past_experiments)


#############################################################################



class zmq_Subscriber:
    def __init__(self,socket_address,topic):
        
        #creating a zmq subscriber which connects to a socket and then listens to certain topics
        self.rtt = 0
        self.data = []
        self.buffer = 0
        self.checksum = 0
        self.expected_checksum = 0
        self.ordering = True
        self.old_seq = 0
        self.received_seqs = set()

        #for sample rate
        self.old_time = time.time()
        self.sample_rate= 0

        #for csv
        self.record_buffer = []

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(socket_address) 
        self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        self.socket.setsockopt(zmq.RCVHWM, 10000)

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)

        

    def get_all_messages(self):
        global count,sample_count
        self.data = []
        while True:
            socks = dict(self.poller.poll(0))
            if self.socket in socks:
                try:
                    topic, payload = self.socket.recv_multipart(flags=zmq.NOBLOCK)
                    if topic == b"experiment/data":
                        for i in range (0,len(payload),12) : 
                            
                            value,seq = struct.unpack('dI',payload[i:i+12]) 
                            if seq not in self.received_seqs:
                                self.received_seqs.add(seq)
                                if self.old_seq != 0:
                                    if seq < self.old_seq:
                                        print(f" Out of order packet: current seq = {seq}, previous = {self.old_seq}")
                                        self.ordering = False
                                    elif seq > self.old_seq + 1:
                                        missed = seq - self.old_seq - 1
                                        print(f"Missed {missed} packets (dropped between {self.old_seq} and {seq})")
                                        self.ordering = False
                                self.checksum += sum(payload[i:i+12])
                                self.data.append(value)
                                count += 1
                                sample_count +=1
                                current_time = time.time()
                                
                                self.buffer= value

                                #checks if one second has passed then updates the sample rate
                                if current_time - self.old_time >= 1.0:
                                    self.sample_rate = sample_count
                                    sample_count = 0
                                    self.old_time = current_time

                                #if recording then save to file
                                if record == 1:

                                    timestamp = datetime.now().isoformat() # gets the current date and time
                                    self.record_buffer.append(f"{timestamp},{value}\n")

                                    if len(self.record_buffer) > 100:
                                        self.save_to_file()
                    elif topic == b"experiment/checksum":
                        try:
                            self.expected_checksum = int(payload.decode())
                            
                            print(payload)
                        except Exception as e:
                            print("Bad message:", payload, "| Error:", e)

                    
                                
                            
    
                except zmq.Again:
                    break
            else:
                break
        return self.data
    

    def compare_checksum(self):
        
        if int(self.checksum) == self.expected_checksum:
            
            return 1
        else:
            
            return 0
    def save_to_file(self):
        try:
            with open(f"Experiments/Experiment{past_experiments}.csv", "a") as f:
                csv_status = 1
                for i in self.record_buffer:
                    f.write(i)
                self.record_buffer.clear()
        except IOError:
                print("Could not write to CSV. Please close CSV file and try again")
                csv_status = 0
    

class zmq_Publisher():
    def __init__(self):
        #creating a zmq pub which binds to a socket to publish messages
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind("tcp://*:5557") 
        

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
            
        
        




        # self.context = zmq.Context()
        # self.socket = self.context.socket(zmq.SUB)
        # self.socket.connect("tcp://192.168.1.82:5556")
        # self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        # self.socket.setsockopt(zmq.RCVHWM, 10000)

        # self.poller = zmq.Poller()
        # self.poller.register(self.socket, zmq.POLLIN)

        self.zmq_sub_client = zmq_Subscriber("tcp://192.168.1.34:5556","experiment/")#34 for rpi5, 33 for rpi ethernet, 82 for pi4 # tailscale: 100.113.46.57
        self.zmq_pub_client = zmq_Publisher()

        self.rtt_client = zmq_Subscriber("tcp://192.168.1.34:5558","")


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

        self.high_sample_rate_btn = QtWidgets.QPushButton("View last experiment")
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

        self.recording_led = QtWidgets.QFrame()
        self.recording_led.setFixedSize(20, 20)
        self.recording_led.setStyleSheet("background-color: grey; border-radius: 10px;")

        self.number_of_experiments_label = QtWidgets.QLabel(f"Number of past  experiments: {past_experiments}")

        self.rtt_label = QtWidgets.QLabel(f"RTT:{str(self.rtt_client.rtt)}ms")

        self.count_label = QtWidgets.QLabel("Samples received:\n")

        self.checksum_label = QtWidgets.QLabel("Validation:\n")
        

         # Slider for sampling rate
        self.rate_slider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        self.rate_slider.setMinimum(1)
        self.rate_slider.setMaximum(10000)
        self.rate_slider.setValue(100)
        self.rate_slider.valueChanged.connect(self.on_rate_slider_change)
        self.rate_slider_label = QtWidgets.QLabel("Sampling rate: 100 Hz")
        self.sampling_rate_label = QtWidgets.QLabel(f"Current sampling rate: {self.zmq_sub_client.sample_rate}Hz")
        
        

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
        main_layout.addWidget(self.count_label)
        main_layout.addWidget(self.checksum_label)
        #main_layout.addWidget(self.last_values_label)
        main_layout.addLayout(experiment_layout)
        main_layout.addLayout(record_layout)
        main_layout.addWidget(self.number_of_experiments_label)

        experiment_layout.addWidget(self.start_button)
        experiment_layout.addWidget(self.stop_button)
        
        rate_layout.addWidget(self.sampling_rate_label)
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
        record_layout.addWidget(self.recording_led)
        

        
        

        # Timer to update plot
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(10)

    # def update_last_values_display(self):
    #     recent_values = self.mqtt_client.data[-5:]
    #     text = "\n".join([f"{v:.4f}" for v in recent_values])
    #     self.last_values_label.setText(f"Last 5 Values:\n{text}")

    def rtt(self):
        self.publisher_cpu_usage = 0
        self.publisher_ram_usage = 0
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
                    self.rtt_label.setText(f"RTT: {self.rtt_client.rtt:.2f} ms          CPU:{self.publisher_cpu_usage}%        Ram:{self.publisher_ram_usage}%")

                elif topic == "experiment/system/cpu":
                        try:
                            self.publisher_cpu_usage = float(payload)   
                        except Exception as e:
                            print("Bad message:", payload, "| Error:", e)

                elif topic == "experiment/system/ram":
                        try:
                            self.publisher_ram_usage = float(payload)
                        except Exception as e:
                            print("Bad message:", payload, "| Error:", e)
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
            
        
        if self.data:
            self.curve.setData(list(range(len(self.data))), list(self.data))
            self.plot_widget.setYRange(-1, 4096, padding=0)

        self.update_count_display()
        self.update_checksum_display()
        self.update_sample_rate_display()

        
            
            
    def update_checksum_display(self):
        result = self.zmq_sub_client.compare_checksum()
        if result == 1:
            self.checksum_label.setText(f"Validation: successful")

        else:
            self.checksum_label.setText(f"Validation: pending")
       
    def update_count_display(self):
            global count
            
            self.count_label.setText(f"Samples Received:\n{count}")
    def update_sample_rate_display(self):
        global count
        
        self.sampling_rate_label.setText(f"Current sampling rate: {self.zmq_sub_client.sample_rate}Hz")

    def reset_graph(self):
        global count
        self.zmq_sub_client.data = []
        self.zmq_pub_client.socket.send_string(f"experiment/reset {1}")
        count = 0
        self.zmq_sub_client.checksum = 0
        self.zmq_sub_client.old_seq=0
        self.zmq_sub_client.received_seqs.clear()

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
        recent_values = self.zmq_sub_client.data[-5:]
        print(recent_values)
        print(self.zmq_sub_client.buffer)
        print(count)
        print(self.zmq_sub_client.checksum)
# Different possible simulated sampling rates
    def low_sample_rate(self):
        self.zmq_pub_client.socket.send_string("experiment/rate 100")

    def med_sample_rate(self):
        self.zmq_pub_client.socket.send_string("experiment/rate 1000")

    def high_sample_rate(self):
        # self.zmq_pub_client.socket.send_string("experiment/rate 10000")
        experiment_file = f"{current_working_directory}/Experiments/Experiment{past_experiments}.csv"
        plot_experiment(experiment_file)
    
    def start_record(self): 
        global record, csv_status,past_experiments
        record = 1
        past_experiments+=1
        if csv_status == 1:
            self.recording_label.setText("Recording")
            self.set_recording_led(record)
        else:
            self.recording_label.setText("Failed to record")

    def stop_record(self): 
        global record
        record = 0
        self.recording_label.setText("Stopped Recording")
        self.set_recording_led(record)
        if self.zmq_sub_client.record_buffer:
            self.zmq_sub_client.save_to_file()
        self.show_temp_message(self.number_of_experiments_label,f"Saved to Experiments/Experiment{past_experiments}.csv")
    
    def show_temp_message(self,label,temp_msg,show_duration = 2000):
        original_msg = label.text()
        label.setText(temp_msg)
        QTimer.singleShot(show_duration, lambda: label.setText(f"Number of past  experiments: {past_experiments}"))

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

            
    def set_recording_led(self, recording):
        if record:
            self.recording_led.setStyleSheet("background-color: red; border-radius: 10px;")
        else:
            self.recording_led.setStyleSheet("background-color: grey; border-radius: 10px;")

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
