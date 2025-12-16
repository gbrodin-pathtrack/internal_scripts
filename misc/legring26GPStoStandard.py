from os import listdir
from os.path import isfile, join
import sys

ROOT = "./"

def convertLine(byteLine : list):
    if(byteLine[0] != 0x9C):
        return byteLine
    
    length = byteLine[1] + ((byteLine[2] & 0x0F) << 8)

    newByteLine = [None]*512
    newByteLine[0] = 0x90
    newIndex = 3
    index = 3
    while index < length:
        #copy ptTimePacked
        for _ in range(5):
            newByteLine[newIndex] = byteLine[index]
            newIndex += 1
            index += 1
        #skip immersion data
        index += 4
        
        #get end of obs from num SVs
        end = index + ((byteLine[index] * 5) + 4)

        #copy numSV, Vbatt, TTF
        for _ in range(3):
            newByteLine[newIndex] = byteLine[index]
            newIndex += 1
            index += 1

        #skip time first sat
        index += 1
        while index < end:
            #copy SV
            for _ in range(5):
                newByteLine[newIndex] = byteLine[index]
                newIndex += 1
                index += 1

    newByteLine[1] = newIndex & 0xFF
    newByteLine[2] = (newIndex >> 8) & 0xFF

    return newByteLine

        
        

def convertFile(fileName):
    with open(fileName, "r") as legring, open(fileName[:-4]+"_converted.dat","w") as standard:
        line = legring.readline()
        while len(line) != 0:
            if not line[:1].isdigit():
                standard.write(line)
            else:
                try:
                    byteLine = convertLine([int(byte) for byte in line.split()])
                    standard.write(" ".join([str(byte) for byte in byteLine])+"\n")
                except:
                    print("skipping line due to error")
                
            line = legring.readline()

#if CLI given take arguments as list of files
if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.startswith("Obs") and f.endswith(".dat") and "unscrambled" in f and "converted" not in f]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    convertFile(ROOT+fileName)