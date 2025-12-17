import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

#PRESSURE_FILE = "./z MiniPI st kilda/Tag64025/Obs060725_154653_Tag64025_Pressure_Immersion.pkl"
#ACCEL_FILE = "./z MiniPI st kilda/Tag64025/Obs060725_154653_Tag64025_Accel.pkl"
#PRESSURE_FILE = "./z MiniPI st kilda/Tag64023/Obs130725_160250_Tag64023_combined_Pressure_Immersion.pkl"
#ACCEL_FILE = "./z MiniPI st kilda/Tag64023/Obs130725_160250_Tag64023_combined_Accel.pkl"
PRESSURE_FILE = "./z MiniPI st kilda/Tag60428/Obs120725_143245_Tag64028_Pressure_Immersion.pkl"
ACCEL_FILE = "./z MiniPI st kilda/Tag60428/Obs120725_143245_Tag64028_Accel.pkl"

SMOOTHED = True
SPLIT_AXES = False

pressDF = pd.read_pickle(PRESSURE_FILE)
accelDF = pd.read_pickle(ACCEL_FILE)

fig, (ax1, ax2) = plt.subplots(nrows=2, sharex=True, height_ratios=[1,1])

ax1.set_ylabel("Pressure")
ax1.set_title("Pressure over time")
ax1.plot(pressDF.datetime, pressDF.pressure)

ax2.set_xlabel("DateTime")
ax2.set_ylabel("Magnitude of acceleration")
ax2.set_title("Acceleration over time")

if SMOOTHED and SPLIT_AXES:
    accelDF["smoothed_x"] = accelDF["X"].rolling(window=100, min_periods=0, center=True).mean()
    accelDF["smoothed_y"] = accelDF["Y"].rolling(window=100, min_periods=0, center=True).mean()
    accelDF["smoothed_z"] = accelDF["Z"].rolling(window=100, min_periods=0, center=True).mean()
    ax2.plot(accelDF.datetime, accelDF.smoothed_x, label="X", color="red")
    ax2.plot(accelDF.datetime, accelDF.smoothed_y, label="Y", color="green")
    ax2.plot(accelDF.datetime, accelDF.smoothed_z, label="Z", color="blue")
    ax2.legend(loc="best")
elif SMOOTHED:
    accelDF["smoothed_mag"] = accelDF["mag"].rolling(window=100, min_periods=0, center=True).mean()
    ax2.plot(accelDF.datetime, accelDF.smoothed_mag, color="red")
elif SPLIT_AXES:
    ax2.plot(accelDF.datetime, accelDF.X, label="X", color="red")
    ax2.plot(accelDF.datetime, accelDF.Y, label="Y", color="green")
    ax2.plot(accelDF.datetime, accelDF.Z, label="Z", color="blue")
    ax2.legend(loc="best")
else:
    ax2.plot(accelDF.datetime, accelDF.mag, color="red")

plt.show()