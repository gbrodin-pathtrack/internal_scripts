import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import cfgrib
from datetime import datetime, timedelta

#POS_FILE = "./z MiniPI st kilda/Tag64025/Obs060725_154653_Tag64025.pos"
#PRESSURE_FILE = "./z MiniPI st kilda/Tag64025/Obs060725_154653_Tag64025_Pressure_Immersion.pkl"
#POS_FILE = "./z MiniPI st kilda/Tag64023/Obs130725_160250_Tag64023_combined.pos" #cant look at yet because no ERA5 data
#PRESSURE_FILE = "./z MiniPI st kilda/Tag64023/Obs130725_160250_Tag64023_combined_Pressure_Immersion.pkl"
POS_FILE = "./z MiniPI st kilda/Tag60428/Obs120725_143245_Tag64028.pos"
PRESSURE_FILE = "./z MiniPI st kilda/Tag60428/Obs120725_143245_Tag64028_Pressure_Immersion.pkl"

def convertDatetime(x):
    dt = datetime(year=int(x.year+2000), month=int(x.month), day=int(x.day))
    offset = timedelta(seconds = x.secondOfDay)
    dt += offset
    return pd.to_datetime(dt)

posDF = pd.read_csv(POS_FILE, sep=',',skiprows=5,names=["day","month","year","hour","minute","second","secondOfDay","numSV","lat","long","height","clkOffset","acc","vbatt"])
posDF["datetime"] = posDF.apply(lambda x: convertDatetime(x), axis=1)
posDF.drop(posDF[posDF.acc > 1].index, inplace=True)

pressDF = pd.read_pickle(PRESSURE_FILE)

GRIB_FILE = "./z MiniPI st kilda/msl_t2m.grib"
ds = cfgrib.open_dataset(GRIB_FILE)

STEP = 0.25
TIME_STEP = np.timedelta64(3600,"s")
TIME_REF = np.datetime64("1970-01-01T00:00:00")


def interpolateMSLandTemp(lat : np.float64, long : np.float64, time : np.datetime64) -> tuple[np.float32,np.float32]:
    global ds
    lat0Diff = lat%STEP
    long0Diff = long%STEP
    elapsed = time - TIME_REF
    time0Diff = elapsed%TIME_STEP

    lat0 = lat - lat0Diff
    lat1 = lat0 + STEP
    latd = (lat - lat0) / (lat1 - lat0)

    long0 = long - long0Diff
    long1 = long0 + STEP
    longd = (long - long0) / (long1 - long0)

    time0 = time - time0Diff
    time1 = time0 + TIME_STEP
    timed = (time - time0) / (time1 - time0)

    #print(lat0, lat1, long0, long1, time0, time1)
    #print(latd, longd, timed)

    #3D
    msl000 = ds.msl.sel(latitude = lat0, longitude = long0, time = time0).data
    temp000 = ds.t2m.sel(latitude = lat0, longitude = long0, time = time0).data

    msl001 = ds.msl.sel(latitude = lat0, longitude = long0, time = time1).data
    temp001 = ds.t2m.sel(latitude = lat0, longitude = long0, time = time1).data

    msl010 = ds.msl.sel(latitude = lat0, longitude = long1, time = time0).data
    temp010 = ds.t2m.sel(latitude = lat0, longitude = long1, time = time0).data

    msl011 = ds.msl.sel(latitude = lat0, longitude = long1, time = time1).data
    temp011 = ds.t2m.sel(latitude = lat0, longitude = long1, time = time1).data

    msl100 = ds.msl.sel(latitude = lat1, longitude = long0, time = time0).data
    temp100 = ds.t2m.sel(latitude = lat1, longitude = long0, time = time0).data

    msl101 = ds.msl.sel(latitude = lat1, longitude = long0, time = time1).data
    temp101 = ds.t2m.sel(latitude = lat1, longitude = long0, time = time1).data

    msl110 = ds.msl.sel(latitude = lat1, longitude = long1, time = time0).data
    temp110 = ds.t2m.sel(latitude = lat1, longitude = long1, time = time0).data

    msl111 = ds.msl.sel(latitude = lat1, longitude = long1, time = time1).data
    temp111 = ds.t2m.sel(latitude = lat1, longitude = long1, time = time1).data

    #print(msl000,msl001,msl010,msl011,msl100,msl101,msl110,msl111)

    #2D
    msl00 = msl000 * (1-latd) + msl100 * latd
    temp00 = temp000 * (1-latd) + temp100 * latd

    msl01 = msl001 * (1-latd) + msl101 * latd
    temp01 = temp001 * (1-latd) + temp101 * latd

    msl10 = msl010 * (1-latd) + msl110 * latd
    temp10 = temp010 * (1-latd) + temp110 * latd

    msl11 = msl011 * (1-latd) + msl111 * latd
    temp11 = temp011 * (1-latd) + temp111 * latd

    #1D
    msl0 = msl00 * (1-longd) + msl10 * longd
    temp0 = temp00 * (1-longd) + temp10 * longd

    msl1 = msl01 * (1-longd) + msl11 * longd
    temp1 = temp01 * (1-longd) + temp11 * longd

    #0D
    msl = msl0 * (1-timed) + msl1 * timed
    #msln = ds.msl.sel(latitude = lat, longitude = long, time = time, method="nearest")/100
    temp = temp0 * (1-timed) + temp1 * timed

    return msl/100, temp #,msln

posDF["msl"], posDF["temp"] = zip(*posDF.apply(lambda x: interpolateMSLandTemp(x.lat, x.long, x.datetime), axis=1)) #posDF["msln"],

#fig, ax1 = plt.subplots()

# ax1.plot(pressDF.datetime, pressDF.pressure, label="Tag")
# ax1.plot(posDF.datetime, posDF.msl, label="MSL_interpolated")
plt.plot(pressDF.datetime, pressDF.pressure, label="Tag")
plt.plot(posDF.datetime, posDF.msl, label="MSL_interpolated")
#plt.plot(posDF.datetime, posDF.msln, label="MSL_nearest")

# ax2 = ax1.twinx()

# ax2.plot(pressDF.datetime, pressDF.immersed, color="green")
# ax2.set_ylim([0,5])

plt.title("Pressure Over Time")
plt.ylabel("Pressure (mbar)")
plt.xlabel("DateTime")
plt.legend(loc="best")
plt.show()
