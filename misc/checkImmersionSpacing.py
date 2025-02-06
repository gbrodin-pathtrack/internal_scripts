import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join

USE_PICKLE = True

if USE_PICKLE:
    wantedExtension = ".pkl"
else:
    wantedExtension = ".csv"
#get every file in root directory that ends with "_GPS"
wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith("_ImmersionAccel"+wantedExtension)]

for fileName in wantedFiles:
    if USE_PICKLE:
        df = pd.read_pickle(fileName)
    else:
        df = pd.read_csv(fileName)

    df["timeDiff"] = df["time"].diff().dt.total_seconds()

    print("*"*100)
    print(fileName)
    print("Avg time diff: %.2fs" % (np.mean(df["timeDiff"])))
    print("Max time diff: %.2fs" % df["timeDiff"].max())
    print("Min time diff: %.2fs" % df["timeDiff"].min())
    print()
    print(df[df["timeDiff"]>10.1])
    # print(df.iloc[df["timeDiff"].idxmax()-4 : df["timeDiff"].idxmax()+3])
    # print()
    # print(df.iloc[df["timeDiff"].idxmin()-4 : df["timeDiff"].idxmin()+3])
    # print()
