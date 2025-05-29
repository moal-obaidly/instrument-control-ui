import sys
import paho.mqtt.client as mqtt

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5 import QtWidgets, QtCore

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
        import pyqtgraph as pg
        super().__init__()
        self.setWindowTitle("Signal Monitor")
        self.resize(900, 600)

        # MQTT
        self.mqtt_client = MQTTClient()
        self.mqtt_client.start()

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

        self.last_values_label = QtWidgets.QLabel("Last 5 Values:\n")
        

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

    def start_experiment(self):
        self.mqtt_client.client.publish("experiment/control", "1")

    def stop_experiment(self):
        self.mqtt_client.client.publish("experiment/control", "0")

app = QApplication(sys.argv)
# Main app
def main():
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
