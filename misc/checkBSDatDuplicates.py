from os import listdir
from os.path import isfile, join
import sys

def checkLinesIdentical(line1 : list, line2 : list):
    for i in range(20):
        if i == 2:
            if (line1[2]&0x0F) != (line2[2]&0x0F):
                return False
            continue
        if line1[i] != line2[i]:
            return False
    
    return True

def checkDatFile(fileName):
    with open(fileName, "r") as f:
        lines = [
            [int(byte) for byte in line.split()]
            for line in f
            if line[:1].isdigit()
        ]

    tags = {}

    for line in lines:
        tagID = line[3] + (line[4] << 8)
        if tagID not in tags.keys():
            tags[tagID] = {"lines":[],"duplicateLines":[]}

        exists = False
        for existingLine in tags[tagID]["lines"]:
            if checkLinesIdentical(line, existingLine):
                exists = True
                break

        tags[tagID]["lines"].append(line)

        if exists:
            tags[tagID]["duplicateLines"].append(line)

    for tagID, tagLines in tags.items():
        print("Tag"+str(tagID)+":")
        print("Total Lines: "+str(len(tagLines["lines"])))
        print("Duplicates: "+str(len(tagLines["duplicateLines"])))
        print()
        if len(tagLines["duplicateLines"]) == 0:
            continue
        with open("./Tag"+str(tagID)+"_duplicates.txt","w") as f:
            f.write("\n".join([" ".join([str(byte) for byte in line]) for line in tagLines["duplicateLines"]]))
                



#if CLI given take arguments as list of files
if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.startswith("Obs") and f.endswith(".dat") and "BS" in f]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    checkDatFile(fileName)