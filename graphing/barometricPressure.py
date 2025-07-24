import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from os import listdir
from os.path import isfile, join
import xarray as xr
import cfgrib

LR = -0.0065
R = 8.3144598
M = 0.0289644
G = 9.80665

def barometricHeight(t0, p0, p):
    return (t0/LR)*(1-pow(p/p0,(R*LR)/(M*G)))

dfDict = {}

ROOT = "./z 190525 pressure test/"

wantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith(".pkl") and "Press" in f and "35911" not in f]

wantedFilesTxt = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith("Press.txt")]

for f in wantedFiles:
    tagIDIndex = f.find("Tag")
    tagID = f[tagIDIndex:tagIDIndex+8]
    dfDict[tagID] = pd.read_pickle(ROOT+f)

# dfDict["Tag64013"]["pressure"] += 22
# dfDict["Tag64013 + 22"] = dfDict.pop("Tag64013")

# for f in wantedFilesTxt:
#     tagIDIndex = f.find("Tag")
#     tagID = f[tagIDIndex:tagIDIndex+8]
#     df = pd.read_csv(f, sep=',', skiprows=5, names=["year","month","day","hour","minute","second","zero","pressure","height"])
#     df["year"] += 2000
#     df["datetime"] = pd.to_datetime(df[["year","month","day","hour","minute","second"]])
#     dfDict[tagID] = df

# dfDict["meteomatics"] = pd.read_csv("meteomatics.csv",sep=";")
# dfDict["meteomatics"]["datetime"] = pd.to_datetime(dfDict["meteomatics"]["datetime"])
# dfDict["meteomatics"]["pressure"] -= 16.7

ds = cfgrib.open_dataset(ROOT+"msl.grib")
print(ds)

#print(ds.msl.sel(latitude = 53.75, longitude = -1.5, time = np.datetime64("2025-05-19T12:00:00")))
#print(ds.msl.to_dataframe())

exit(0)
ds = ds/100
#ds -= 16.7
msl = ds.msl.sel(latitude = 53.855, longitude = -1.587, method = "nearest")

mslDF = msl.to_dataframe()

for tagID, df in dfDict.items():
    #print(df.loc[df.duplicated(subset="datetime")])
    mslSeries = mslDF.reindex(mslDF.index.union(df.datetime)).msl.interpolate(method='time').reindex(df.datetime)
    df["msl"] = mslSeries.values
    df["pressureDiff"] = df["pressure"] - df["msl"]
    df["pressureDiff"] -= df["pressureDiff"][0]
    # df["pressure"] -= df["pressureDiff"][0]
    # df["height"] = df.apply(lambda x: barometricHeight(285, x.msl, x.pressure), axis=1)
    plt.plot(df.datetime, df.pressureDiff, label=tagID)
    #df["temp"] = df["temp"].interpolate()
    #plt.plot(df.datetime, df.temp, label=tagID)


#ds.msl.sel(latitude = 53.855, longitude = -1.587, method = "nearest").plot(label = "ERA5")

plt.title("Pressure Over Time")
plt.ylabel("Pressure (mbar)")
plt.xlabel("DateTime")
plt.legend(loc="best")
plt.show()