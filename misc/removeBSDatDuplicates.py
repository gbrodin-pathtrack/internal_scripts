from os import listdir
from os.path import isfile, join
import sys

ROOT = "./"

def checkLinesIdentical(line1 : list, line2 : list):
    for i in range(20):
        if i == 2:
            if (line1[2]&0x0F) != (line2[2]&0x0F):
                return False
            continue
        if line1[i] != line2[i]:
            return False

    return True

def removeDuplicates(fileName):
    with open(fileName, "r") as f:
        lines = f.readlines()
        byteLines = [
            [int(byte) for byte in line.split()]
            for line in lines
            if line[:1].isdigit()
        ]

    uniqueLines = []

    for line in byteLines:
        exists = False
        for existingLine in uniqueLines:
            if checkLinesIdentical(line, existingLine):
                exists = True
                break

        if not exists:
            uniqueLines.append(line)

    #print(uniqueLines)

    with open(fileName[:-4]+"_unique.dat","w") as f:
        f.writelines(lines[:5])
        f.write("\n".join([" ".join([str(byte) for byte in line]) for line in uniqueLines]))

    print("Removed",len(lines)-len(uniqueLines),"lines from",fileName)



#if CLI given take arguments as list of files
if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.startswith("Obs") and f.endswith(".dat") and "BS" in f and "unique" not in f]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    removeDuplicates(ROOT+fileName)