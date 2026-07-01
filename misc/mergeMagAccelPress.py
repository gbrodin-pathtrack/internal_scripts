import pandas as pd
import sys

ROOT = "./"
BASE_NAME = "Obs240626_120700_Tag10597"

if len(sys.argv) > 1:
    BASE_NAME = sys.argv[1]

accelDF = pd.read_pickle(ROOT+BASE_NAME+"_Accel.pkl")
magDF = pd.read_pickle(ROOT+BASE_NAME+"_Magnetometer.pkl")
pressDF = pd.read_pickle(ROOT+BASE_NAME+"_Differential_Pressure.pkl")

accelDF.rename(columns={"X":"accX", "Y":"accY", "Z":"accZ"}, inplace=True)

accelDF.drop(columns=["line", "validation", "mag"], inplace=True)

def assignMagToAccel(magRow):
    global accelDF
    timeDiff = abs(accelDF["datetime"] - magRow["datetime"])
    accelDF.loc[timeDiff.idxmin(), ["magX","magY","magZ"]] = (magRow["X"], magRow["Y"], magRow["Z"])

def assignPressToAccel(pressRow):
    global accelDF
    timeDiff = abs(accelDF["datetime"] - pressRow["datetime"])
    accelDF.loc[timeDiff.idxmin(), ["pressure"]] = pressRow["pressure"]

magDF.apply(lambda row: assignMagToAccel(row),axis=1)

pressDF.apply(lambda row: assignPressToAccel(row),axis=1)

accelDF.to_csv(BASE_NAME+"_merged.csv",index=False)