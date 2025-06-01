import sys
import paho.mqtt.client as mqtt

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5 import QtWidgets, QtCore
from datetime import datetime


#globals
record = 0

# MQTT Client Setup
class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.data = []

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code", rc)
        client.subscribe("experiment/data")

    def on_message(self, client, userdata, msg):
        try:
            value = float(msg.payload.decode())
            self.data.append(value)

            if record == 1:
                with open("signal.csv", "a") as f:
                    timestamp = datetime.now().isoformat() # gets the current date and time
                    f.write(f"{timestamp},{value}\n")

            if len(self.data) > 1000:
                self.data.pop(0)
        except Exception as e:
            print("Bad message:", msg.payload, "| Error:", e)

    def start(self):
        self.client.connect("192.168.1.36", 1883, 60)
        self.client.loop_start()


# PyQt GUI
class MainWindow(QWidget):
    def __init__(self):
        global record
        import pyqtgraph as pg
        super().__init__()
        self.setWindowTitle("Signal Monitor")
        self.resize(900, 600)

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

        

        # Slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(self.on_slider_change)

        # Labels

        self.slider_label = QtWidgets.QLabel("Slider Value: 50")

        self.last_values_label = QtWidgets.QLabel("Last 5 Values:\n")

        if record == 1:
            self.recording_label = QtWidgets.QLabel("Recording")
        elif record == 0:
            self.recording_label = QtWidgets.QLabel("Not recording")

        

         # Slider for sampling rate
        self.rate_slider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        self.rate_slider.setMinimum(1)
        self.rate_slider.setMaximum(10000)
        self.rate_slider.setValue(100)
        self.rate_slider.valueChanged.connect(self.on_rate_slider_change)
        self.rate_slider_label = QtWidgets.QLabel("Sampling rate: 100 Hz")

        
        

        # Layout setup
        main_layout.addWidget(self.plot_widget)

        control_layout.addWidget(self.reset_btn)
        control_layout.addWidget(self.slider_label)
        control_layout.addWidget(self.slider)
        
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.last_values_label)

        experiment_layout.addWidget(self.start_button)
        experiment_layout.addWidget(self.stop_button)
        main_layout.addLayout(experiment_layout)

        rate_layout.addWidget(self.low_sample_rate_btn)
        rate_layout.addWidget(self.med_sample_rate_btn)
        rate_layout.addWidget(self.high_sample_rate_btn)
        horizontal_main_layout.addLayout(main_layout)
        horizontal_main_layout.addLayout(rate_layout)

        sampling_layout.addWidget(self.rate_slider_label)
        sampling_layout.addWidget(self.rate_slider)
        horizontal_main_layout.addLayout(sampling_layout)

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

    def update_plot(self):
        self.curve.setData(self.mqtt_client.data)
        self.update_last_values_display()

    def reset_graph(self):
        self.mqtt_client.data = []

    def on_slider_change(self, value):
        self.slider_label.setText(f"Slider Value: {value}")
        self.mqtt_client.client.publish("experiment/slider", value)
    
    def on_rate_slider_change(self, value):
        self.rate_slider_label.setText(f"Sampling rate: {value} Hz")
        self.mqtt_client.client.publish("experiment/rateslider", value)

    def start_experiment(self):
        self.mqtt_client.client.publish("experiment/control", "1")

    def stop_experiment(self):
        self.mqtt_client.client.publish("experiment/control", "0")
# Different possible simulated sampling rates
    def low_sample_rate(self):
        self.mqtt_client.client.publish("experiment/rate", "100")

    def med_sample_rate(self):
        self.mqtt_client.client.publish("experiment/rate", "1000")

    def high_sample_rate(self):
        self.mqtt_client.client.publish("experiment/rate", "10000")
    
    def start_record(self): 
        global record
        record = 1
        self.recording_label.setText("Recording")

    def stop_record(self): 
        global record
        record = 0
        self.recording_label.setText("Stopped Recording")
    
        

app = QApplication(sys.argv)
# Main app
def main():
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
