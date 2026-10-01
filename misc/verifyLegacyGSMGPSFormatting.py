import numpy as np
from os import listdir
from os.path import isfile, join, splitext
import sys
from datetime import datetime

ROOT = "./"

LINE_OFFSET = 6

def parseDatFile(fileName : str):
    printedFile = False

    #read every line from file, ignoring header lines and produce a list of np arrays of bytes
    with open(fileName, "r") as f:
        allLines = f.readlines()
        byteLines = [
            np.array([int(byte) for byte in line.split()])
            for line in allLines
            if line[:1].isdigit()
        ]

    lineNum = LINE_OFFSET
    for byteLine in byteLines:
        if byteLine[0] > 2:
            continue
        lineLen = byteLine[0] * 256 + byteLine[1]

        index = 2
        while index < lineLen:
            year = byteLine[index]
            month = byteLine[index+1]
            day = byteLine[index+2]
            hour = byteLine[index+3]
            minute = byteLine[index+4]
            second = byteLine[index+5]
            if month == 0 or month > 12 or day == 0 or day > 31 or hour > 23 or minute > 59 or second > 59:
                if not printedFile:
                    print(f"Problem with file {fileName}")
                    printedFile = True
                print(f"{year} {month} {day} {hour} {minute} {second}")
                print(f"Invalid time at index {index} on line {lineNum}")
                break

            index += 6

            numSV = byteLine[index]

            index += 11 + (4*numSV)

            if index > lineLen + 1:
                if not printedFile:
                    print(f"Problem with file {fileName}")
                    printedFile = True
                print(f"Index overran length on line {lineNum}")
                break

        lineNum += 1

        if printedFile:
            break


passedFiles = sys.argv[1:]

#if CLI given take arguments as list of files
if len(passedFiles) > 0:
    wantedFiles = passedFiles
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [ROOT + f for f in listdir(ROOT) if isfile(join(ROOT, f)) and (f.endswith(".dat") or ".ptd" in f)]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseDatFile(fileName)
