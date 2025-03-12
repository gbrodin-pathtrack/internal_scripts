from os import listdir
from os.path import isfile, join
import sys

header = \
"""*************************************************************************************
PathTrack Archival Tracking System Raw Data File for Tag XXXXX (NanoFix UHF Format)
Blah blah blah
DO NOT MODIFY THIS HEADER
*************************************************************************************
"""

def convertBinToDat(fileName):
    with open(fileName,'rb') as bin, open(fileName[:-4]+".dat",'w') as dat:
        dat.write(header)
        while chunk := bin.read(528):  # Read 528 bytes at a time
            decimal_representation = " ".join(str(byte) for byte in chunk)  # Convert to decimal
            dat.write(decimal_representation + "\n")  # Write to file with newline

if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
else:
    wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".bin")]

for file in wantedFiles:
    convertBinToDat(file)