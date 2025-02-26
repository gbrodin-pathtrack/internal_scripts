import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_GPS"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_Pressure_Immersion"+wantedExtension)]

for fileName in wantedFiles:
    if USE_PICKLE:
        df = pd.read_pickle(fileName)
    else:
        df = pd.read_csv(fileName)

    tagID = fileName[-len("TagXXXXX_Pressure_Immersion.pkl"):-len("_Pressure_Immersion.pkl")]

    plt.plot(df.time, df.pressure, label=tagID)

plt.title("Pressure Over Time")
plt.ylabel("Pressure (mbar)")
plt.xlabel("DateTime")
plt.legend(loc="best")
plt.show()