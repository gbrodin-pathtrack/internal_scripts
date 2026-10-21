import pandas as pd
import sys
import os.path

BASE_NAME = "./Obs201026_120808_Tag33279"

if len(sys.argv) > 1:
    BASE_NAME = sys.argv[1]
    if BASE_NAME.endswith(".dat"):
        BASE_NAME = BASE_NAME[:-4]

accelFile = BASE_NAME+"_Accel.pkl"
magFile = BASE_NAME+"_Magnetometer.pkl"
pressFile = BASE_NAME+"_Differential_Pressure.pkl"
if not os.path.isfile(pressFile):
    pressFile = BASE_NAME+"_Pressure_Immersion.pkl"
mergedFile = BASE_NAME+"_merged.csv"

if not os.path.isfile(accelFile) or not os.path.isfile(magFile) or not os.path.isfile(pressFile):
    print("Couldn't find accel, mag, or press file from passed base name")
    print("Ensure dat file was parsed using -pkl argument")
    exit(1)

accelDF = pd.read_pickle(accelFile)
magDF = pd.read_pickle(magFile)
pressDF = pd.read_pickle(pressFile)

print("Found accel, mag, and pressure files with base name:")
print(BASE_NAME)
print("Merging...")

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

accelDF.to_csv(mergedFile,index=False)

print("Complete, generated merged file:")
print(mergedFile)
