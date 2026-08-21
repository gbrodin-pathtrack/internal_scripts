import pandas as pd
import numpy as np
from os import listdir
from os.path import isfile, join
import sys

ROOT = "./"

def processPosFile(fileName):
    posDF = pd.read_csv(fileName, skiprows=5, sep=',',names=["day","month","year","hour","min","sec","secOfDay","numSV","lat","lon","height","val1","val2","vBatt"])
    rawDF = pd.read_csv(fileName[:-4]+".raw", skiprows=5, sep=' ', usecols=[0,1,2,3,4,5], names=["year","dayOfYear","secOfDay","vBatt","TTF","numSV"])
    posDF.reset_index(inplace=True, drop=True)

    numProcessed = len(posDF.loc[posDF["lat"] != 0])
    num5PlusFails = len(posDF.loc[(posDF["lat"] == 0) & (rawDF["numSV"] >= 5)])
    num5DropTo4 = len(posDF[(posDF["numSV"] == 4) & (rawDF["numSV"] == 5)])

    print("*"*50)
    print(fileName)
    print(f"Processed: {numProcessed}")
    print(f"5+ SV failed: {num5PlusFails}")
    print(f"5 drop to 4: {num5DropTo4}")
    print()

#class to output printed values to terminal and output file
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.file = open(ROOT+"pos_summary.txt", "w")
    def __del__(self):
        self.file.close()
    def write(self, message):
        self.terminal.write(message)
        self.file.write(message)  
    def flush(self):
        self.terminal.flush()
        self.file.flush()

#get every file in root directory that ends with "_GPS"
wantedFiles = [ROOT + f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith(".pos")]

#duplicate print messages into an output file, only if there are files to process
if len(wantedFiles) > 0:
    sys.stdout = Logger()

for file in wantedFiles:
    processPosFile(file)