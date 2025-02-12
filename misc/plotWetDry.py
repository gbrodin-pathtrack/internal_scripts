import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def convertDatetime(x):
    dt = datetime(year=int(x.year), month=1, day=1)
    offset = timedelta(days=(int(x.day) - 1),seconds=int(x.second))
    dt += offset
    return pd.to_datetime(dt)

accelImmersionDF = pd.read_csv("Obs100225_084510_Tag60940AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)

accelImmersionDF["datetime"] = pd.to_datetime(accelImmersionDF[["year","month","day","hour","minute","second"]])

gpsDF = pd.read_csv("Obs100225_084510_Tag60940.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)

gpsDF["datetime"] = gpsDF.apply(lambda x: convertDatetime(x), axis=1)

#print(gpsDF.head())

#print(df.head())

fig, ax1 = plt.subplots()

plt.title("1 min accel and immersion samples with GPS times marked")

col = "tab:blue"
ax1.set_xlabel("Datetime")
ax1.set_ylabel("Immersed (boolean)", color=col)
ax1.plot(accelImmersionDF["datetime"], accelImmersionDF["immersed"], color=col)
ax1.tick_params(axis="y", labelcolor=col)

plt.vlines(gpsDF.datetime, ymin=0.2, ymax=0.8, colors='green')

ax2 = ax1.twinx()

col = "tab:red"
ax2.set_ylabel("Acceleration magnitude (g)", color=col)
ax2.plot(accelImmersionDF["datetime"],accelImmersionDF["mag"], color=col)
ax2.tick_params(axis="y", labelcolor=col)

plt.show()
