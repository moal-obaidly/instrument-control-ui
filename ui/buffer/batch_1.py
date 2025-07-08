import sys
import paho.mqtt.client as mqtt
import time
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QTimer
from datetime import datetime
import struct
import numpy as np
import os
from plot_signal import plot_experiment
import matplotlib 
matplotlib.use("Qt5Agg") 
import matplotlib.pyplot as plt
import psutil


# experiment_file = f"{current_working_directory}/Experiments/Experiment12.csv"
#globals
record = 0
csv_status = 1
count = 0
sample_count = 0



current_working_directory = os.getcwd()
experiments_folder = f"{current_working_directory}/Experiments"
past_experiments = 0
# Count the number of files in the *experiments* directory
for path in os.listdir(experiments_folder):
    if os.path.isfile(os.path.join(experiments_folder,path)):
        past_experiments+=1

print(past_experiments)


# MQTT Client Setup
class MQTTClient:
    
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.data = []
        self.rtt = 0
        self.buffer = 0
        self.checksum = 0
        self.expected_checksum = 0
        self.old_seq = 0
        self.received_seqs = set()
        #for sample rate
        self.old_time = time.time
        self.sample_rate= 0
        #for saving to csv
        self.record_buffer = []

        #system specs
        self.publisher_cpu_usage = 0
        self.publisher_ram_usage = 0

        
        

    def on_connect(self, client, userdata, flags, rc):


        print("Connected with result code", rc)
        client.subscribe("experiment/data",qos=0)
        client.subscribe("experiment/rtt")
        client.subscribe("experiment/rtt/display")
        client.subscribe("experiment/checksum")
        client.subscribe("experiment/system/cpu")
        client.subscribe("experiment/system/ram")


    def on_message(self, client, userdata, msg):


        global csv_status, count,past_experiments,sample_count


        if msg.topic == "experiment/data":
            try:                                                  #
                # payload = msg.payload.decode()                  # with time sent 
                # sent_time_str, value_str = payload.split(",")   #
                # sent_time = float(sent_time_str)                # 
                # value = float(value_str) 
                #
                
                payload = msg.payload
                for i in range (0,len(payload),12) :                      #

                    value,seq = struct.unpack('dI',payload[i:i+12])                   # without time sent... only the data
                    
                
                                           #
                #timerec = int(time.time()*1000.0)
                    if seq not in self.received_seqs:
                        self.received_seqs.add(seq)
                        self.checksum += sum(payload[i:i+12])
                        self.data.append(value)
                        # print(value)
                        count += 1
                        sample_count +=1
                        self.buffer= value
                        current_time = time.time()



                        

                        if current_time - self.old_time >= 1.0:
                            self.sample_rate = sample_count
                            sample_count = 0
                            self.old_time = current_time
                        
                            


                        if record == 1:

                            timestamp = datetime.now().isoformat() # gets the current date and time
                            self.record_buffer.append(f"{timestamp},{value}\n")

                            if len(self.record_buffer) > 100:
                                self.save_to_file()
                    
                                # try:
                                #     with open(f"Experiments/Experiment{past_experiments}.csv", "a") as f:
                                #         csv_status = 1
                                #         for i in self.record_buffer:
                                #             f.write(i)
                                #         self.record_buffer.clear()
                                #         # timestamp = datetime.now().isoformat() # gets the current date and time
                                #         # f.write(f"{timestamp},{value}\n")
                                        
                                        
                                # except IOError:
                                #     print("Could not write to CSV. Please close CSV file and try again")
                                #     csv_status = 0



                    else:
                        print(f"Duplicate or old packet seq={seq} ignored")
                #print(f"Value at time{timerec}= {value}")

                #latency = (time.time() - sent_time) * 1000
                #print(f"Latency: {latency:.2f} ms")

                # if record == 1:
                    
                #     try:
                #         with open(f"Experiments/Experiment{past_experiments}.csv", "a") as f:
                #             csv_status = 1
                #             timestamp = datetime.now().isoformat() # gets the current date and time
                #             f.write(f"{timestamp},{self.data}\n")
                            
                            
                #     except IOError:
                #         print("Could not write to CSV. Please close CSV file and try again")
                #         csv_status = 0

                self.data = self.data[-1000:]
                # if len(self.data) > 1000:    IT WAS NOT ENOUGH WITH BATCH SENDING. ONLY POPPING ONE AT A TIME WASNT REMOVING ENOUGH
                #     self.data.pop(0)
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


        elif msg.topic == "experiment/checksum":
            try:
                self.expected_checksum = int(msg.payload.decode())
                
                print(msg.payload)
             
            except Exception as e:
                print("Bad message:", msg.payload, "| Error:", e)

            
        elif msg.topic == "experiment/system/cpu":
            try:
                self.publisher_cpu_usage = float(msg.payload.decode())
                ####prints ui cpu and ram
                cpu_usage = psutil.cpu_percent(interval=0)
                # RAM usage in %
                ram_usage = psutil.virtual_memory().percent

                cpu_usage = psutil.cpu_percent(interval=0)
                # RAM usage in %
                ram_usage = psutil.virtual_memory().percent

                print(f"CPU Usage: {cpu_usage}%")
                print(f"RAM Usage: {ram_usage}%")

                # print(f"CPU Usage: {cpu_usage}%")
                # print(f"RAM Usage: {ram_usage}%")
                ####
                # print(msg.payload)
             
            except Exception as e:
                print("Bad message:", msg.payload, "| Error:", e)


        elif msg.topic == "experiment/system/ram":
            try:
                self.publisher_ram_usage = float(msg.payload.decode())
                
                # print(msg.payload)
             
            except Exception as e:
                print("Bad message:", msg.payload, "| Error:", e)

           
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
                                        # timestamp = datetime.now().isoformat() # gets the current date and time
                                        # f.write(f"{timestamp},{value}\n")
                                        
                                        
        except IOError:
                print("Could not write to CSV. Please close CSV file and try again")
                csv_status = 0
                                        
    

    def start(self):


        self.client.connect("192.168.1.82", 1883, 60) #.36 for laptop, .82 for rpi4   taliscale: 100.106.113.72
        self.client.loop_start()



#############################################################################

#class Worker(QObject):
#    finished = pyqtSignal()
#    progress = pyqtSignal(int)

    #def run(self):
        
    #    self.finished.emit()

# PyQt GUI
class MainWindow(QWidget):
    def __init__(self):
        global record,screen_size,past_experiments
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
        self.curve.setPen(pg.mkPen(color='#00e676', width=2)) # this changes plot colour

        # Buttons
        self.reset_btn = QtWidgets.QPushButton("Reset Experiment")
        self.reset_btn.clicked.connect(self.reset_experiment)

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

        self.count_label = QtWidgets.QLabel("Samples received:\n")

        self.checksum_label = QtWidgets.QLabel("Validation:\n")

        self.recording_label = QtWidgets.QLabel("Not recording")
        self.recording_led = QtWidgets.QFrame()
        self.recording_led.setFixedSize(20, 20)
        self.recording_led.setStyleSheet("background-color: grey; border-radius: 10px;")

        self.number_of_experiments_label = QtWidgets.QLabel(f"Number of past  experiments: {past_experiments}")


        self.rtt_label = QtWidgets.QLabel(f"RTT:{str(self.mqtt_client.rtt)}ms       CPU:{self.mqtt_client.publisher_cpu_usage}%        Ram:{self.mqtt_client.publisher_ram_usage}%")

        

         # Slider for sampling rate
        self.rate_slider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        self.rate_slider.setMinimum(1)
        self.rate_slider.setMaximum(10000)
        self.rate_slider.setValue(100)
        self.rate_slider.valueChanged.connect(self.on_rate_slider_change)
        self.sampling_rate_label = QtWidgets.QLabel(f"Current sampling rate: {self.mqtt_client.sample_rate}Hz")
        
        

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

        # sampling_layout.addWidget(self.rate_slider_label)
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

    def update_count_display(self):
        global count
        
        self.count_label.setText(f"Samples Received:\n{count}")


    def update_sample_rate_display(self):
        global count
        
        self.sampling_rate_label.setText(f"Current sampling rate: {self.mqtt_client.sample_rate}Hz")


    def update_checksum_display(self):
        result = self.mqtt_client.compare_checksum()
        if result == 1:
            self.checksum_label.setText(f"Validation: successful")

        else:
            self.checksum_label.setText(f"Validation: pending")
        
        

    def update_plot(self):
        x = np.arange(len(self.mqtt_client.data)) * (1 / 10000)
        self.curve.setData(self.mqtt_client.data)
        self.plot_widget.setYRange(-1, 4096, padding=0) # change if using adc or sine simu.
        self.plot_widget.setLabel('left', 'ADC Value')
        


        self.update_count_display()
        self.update_checksum_display()
        self.update_sample_rate_display()
        self.rtt_label.setText(f"RTT:{self.mqtt_client.rtt:.2f}ms       CPU:{self.mqtt_client.publisher_cpu_usage}%        Ram:{self.mqtt_client.publisher_ram_usage}%")
        
        
        #print(f"Current RTT in GUI update: {self.mqtt_client.rtt}")


    def reset_experiment(self):
        global count
        self.mqtt_client.data = []
        self.mqtt_client.client.publish("experiment/reset", "1",qos=1)
        count = 0
        self.mqtt_client.checksum = 0
        self.mqtt_client.old_seq=0
        self.mqtt_client.received_seqs.clear()


    def on_slider_change(self, value):
        self.slider_label.setText(f"Frequency: {value}")
        self.mqtt_client.client.publish("experiment/slider", value)

    
    def on_rate_slider_change(self, value):
        self.sampling_rate_label.setText(f"Sampling rate: {value} Hz")
        self.mqtt_client.client.publish("experiment/rateslider", value)


    def start_experiment(self):
        self.mqtt_client.client.publish("experiment/control", "1",qos=1)
        self.reset_btn.setEnabled(False)
        self.mqtt_client.old_time = time.time()


    def stop_experiment(self):
        global count
        self.mqtt_client.client.publish("experiment/control", "0",qos=1)
        self.reset_btn.setEnabled(True)
        recent_values = self.mqtt_client.data[-5:]
        print(recent_values)
        print(self.mqtt_client.buffer)
        print(count)


# Different possible simulated sampling rates


    def low_sample_rate(self):
        self.mqtt_client.client.publish("experiment/rate", "100")


    def med_sample_rate(self):
        self.mqtt_client.client.publish("experiment/rate", "1000")


    def high_sample_rate(self):
        # self.mqtt_client.client.publish("experiment/rate", "10000")
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

        #flushes whats left in the buffer (if smaller than the batch size)
        if self.mqtt_client.record_buffer:
            self.mqtt_client.save_to_file()

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
        self.close()
        
    
######Compare plot and then subtract them from each other to calculate the error

app = QApplication(sys.argv)
# Main app
def main():
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
