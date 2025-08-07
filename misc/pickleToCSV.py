import pandas as pd
from os import listdir
from os.path import isfile, join

pickleFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith(".pkl")]

for file in pickleFiles:
    df = pd.read_pickle(file)
    df.to_csv(file[:-4]+".csv",index=False)