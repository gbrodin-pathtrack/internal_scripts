from os import listdir
from os.path import isfile, join
import pandas as pd

USE_PICKLE = True

ROOT = "./"

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
immersionAccelFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith("_ImmersionAccel"+wantedExtension) and "combined" not in f]
immersionFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith("_Immersion"+wantedExtension) and "combined" not in f]

#loop over wanted files and generate a combined version
if len(immersionAccelFiles) > 1:
    dfArr = []
    for file in immersionAccelFiles:
        if USE_PICKLE:
            df = pd.read_pickle(ROOT+file)
        else:
            df = pd.read_csv(ROOT+file)
        dfArr.append(df)
    df_combined = pd.concat(dfArr)
    if USE_PICKLE:
        df_combined.to_pickle(ROOT+"combined_ImmersionAccel.pkl")
    else:
        df_combined.to_csv(ROOT+"combined_ImmersionAccel.csv",index=False)

#loop over wanted files and generate a combined version
if len(immersionFiles) > 1:
    dfArr = []
    for file in immersionFiles:
        if USE_PICKLE:
            df = pd.read_pickle(ROOT+file)
        else:
            df = pd.read_csv(ROOT+file)
        dfArr.append(df)
    df_combined = pd.concat(dfArr)
    if USE_PICKLE:
        df_combined.to_pickle(ROOT+"combined_Immersion.pkl")
    else:
        df_combined.to_csv(ROOT+"combined_Immersion.csv",index=False)
