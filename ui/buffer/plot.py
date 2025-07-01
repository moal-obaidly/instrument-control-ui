import numpy as np
import os
import csv
import matplotlib.pyplot as plt

data = []
rate = 10000
current_working_directory = os.getcwd()
experiment_file = f"{current_working_directory}/Experiments/Experiment12.csv"

# with open(experiment_file, newline='') as csvfile:

#     reader = csv.DictReader(csvfile,delimiter=',')

#     for row in reader:
        
#         value = data.append( reader.split(",")[1])


#         print(value)

with open(experiment_file) as infile:
    reader = csv.reader(infile) 
    next(reader) 
    for row in reader:
        data.append(float(row[1]))


    print(data)

new_data = np.array(data)
volt = new_data *3.3/4096
    
print (data)

t = np.arange(len(volt))/rate

non_zero_val = [] 
for i in data:
    if i != 0:
        non_zero_val.append(i)

print(f"seconds = {len(t)/rate}")
adc_res = 4095
v_ref = 3.3
max_val = max(data)
min_val = min(data)
average = np.mean(non_zero_val)
amplitude = (max_val - min_val) * v_ref / adc_res


print(f"min = {min_val}")
print(f"max= {max_val}")
print(f"average= {average} ")
print(f"amp= {amplitude} ")


variation = np.std(non_zero_val)
print(variation)

plt.plot(t,volt)

# plt.xlim(0,len(data))
# plt.ylim(0, max(data))

plt.show()


# self.curve.setData(self.mqtt_client.data)
# self.plot_widget.setYRange(-1, 4096, padding=0) # change if using adc or sine simu.
# self.plot_widget.setLabel('left', 'ADC Value')