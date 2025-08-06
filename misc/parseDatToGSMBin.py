from os import listdir
from os.path import isfile, join
import sys
import numpy as np

def convertBinToDat(fileName):
    with open(fileName,'r') as dat, open(fileName[:-4]+".bin",'wb') as bin:
        byteLines = [
            [int(byte) for byte in line.split()]
            for line in dat
            if line[:1].isdigit()
        ]
        for byteLine in byteLines:
            bin.write(bytes(byteLine))
            bin.write(bytes([0]*(528-len(byteLine))))
        

if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
else:
    wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".dat") and "BS" in f]

for file in wantedFiles:
    convertBinToDat(file)