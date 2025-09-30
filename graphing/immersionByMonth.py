import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"

immersionWantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_ImmersionAccel"+wantedExtension)]
immersionFileName = immersionWantedFiles[0]

if USE_PICKLE:
    df = pd.read_pickle(immersionFileName)
else:
    df = pd.read_csv(immersionFileName)

months = df.month.unique()

monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

xLabels = []
yValues = []

for month in months:
    monthDF = df[df.month == month]
    immersedPortion = (monthDF[monthDF.immersed == 1].size / monthDF.size)*100
    xLabels.append(monthNames[month-1])
    yValues.append(immersedPortion)

plt.title("Percentage of Time Immersed by Month")
plt.xlabel("Month")
plt.ylabel("Time Immersed")
plt.ylim(0,100)
plt.yticks(np.arange(0,101,5))
plt.bar(xLabels, yValues,width=0.5,zorder=3)
plt.grid(axis='y',zorder=0)
plt.gca().yaxis.set_major_formatter(mtick.PercentFormatter())
plt.show()