import pandas as pd
import matplotlib.pyplot as plt

subsampledDF = pd.read_pickle("Obs060725_154653_Tag64025_Accel_subsampled.pkl")

vedbaDF = pd.read_pickle("Obs060725_154653_Tag64025_Accel_vedba.pkl")

fig, ax1 = plt.subplots()

ax1.set_xlabel("Datetime")
ax1.set_ylabel("Acceleration Magnitude (g)")
line1 = ax1.plot(subsampledDF.datetime, subsampledDF.mag, label="1Hz")

ax2 = ax1.twinx()

ax2.set_ylabel("VeDBA (g)")
line2 = ax2.plot(vedbaDF.datetime, vedbaDF.avgVeDBA, label="VeDBA", color="red")

lines = line1+line2
labels = [l.get_label() for l in lines]
plt.legend(lines, labels, loc="best")

plt.show()