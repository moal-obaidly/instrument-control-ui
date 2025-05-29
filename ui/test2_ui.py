import sys
import paho.mqtt.client as mqtt
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore

app = QtWidgets.QApplication([])
# MQTT Configuration
broker_ip = "192.168.1.36"
topic = "experiment/data"

# MQTT Client Setup
class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.data = []

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        try:
            value = float(msg.payload.decode())
            self.data.append(value)
            if len(self.data) > 1000:
                self.data.pop(0)
        except:
            print("Bad message:", msg.payload)

    def start(self):
        self.client.connect(broker_ip, 1883, 60)
        self.client.loop_start()


# Create MQTT client instance
mqtt_client = MQTTClient()
mqtt_client.start()

# PyQt GUI
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Signal Monitor")
        self.resize(900, 600)

        # Layouts
        main_layout = QtWidgets.QVBoxLayout(self)
        control_layout = QtWidgets.QHBoxLayout()
        experiment_layout = QtWidgets.QHBoxLayout()

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

        # Slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(self.on_slider_change)

        self.slider_label = QtWidgets.QLabel("Slider Value: 50")

        # Layout setup
        main_layout.addWidget(self.plot_widget)
        control_layout.addWidget(self.reset_btn)
        control_layout.addWidget(self.slider_label)
        control_layout.addWidget(self.slider)
        main_layout.addLayout(control_layout)
        experiment_layout.addWidget(self.start_button)
        experiment_layout.addWidget(self.stop_button)
        main_layout.addLayout(experiment_layout)


        # Timer to update plot
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)

    def update_plot(self):
        self.curve.setData(mqtt_client.data)

    def reset_graph(self):
        mqtt_client.data = []

    def on_slider_change(self, value):
        self.slider_label.setText(f"Slider Value: {value}")
        # You can use this value to send commands later
    def start_experiment():
       mqtt_client.publish("experiment/control", "1")
    def stop_experiment():
        mqtt_client.publish("experiment/control", "0")



# Run the App

window = MainWindow()
window.show()
sys.exit(app.exec_())