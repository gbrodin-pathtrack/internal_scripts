import pandas as pd
import numpy as np
from parsers.parseInt import parseUInt16, parseUInt32
from parsers.parsePackedTime import parsePackedTime
from os import listdir
from os.path import isfile, join, splitext
import sys

LINE_OFFSET = 6

USE_PICKLE = False

ROOT = "./"

def parseBSDat(fileName):
    if fileName.endswith(".dat"):
        #read every line from file, ignoring header lines and produce a list of np arrays of bytes
        with open(fileName, "r") as f:
            allLines = f.readlines()
            byteLines = [
                np.array([int(byte) for byte in line.split()])
                for line in allLines
                if line[:1].isdigit()
            ]
    else:
        with open(fileName, 'rb') as f:
            fileHeader = f.read(12 if 'ptdw' in fileName else 11)
            lineLength = int.from_bytes(fileHeader[-6:-4], byteorder="little", signed=False)
            numBytesToData = int.from_bytes(fileHeader[-4:-2], byteorder="little", signed=False)
            checkA = 0
            checkB = 0
            for byte in fileHeader[:-2]:
                checkA += byte
                checkA &= 0xFF
                checkB += checkA
                checkB &= 0xFF
            if checkA != fileHeader[-2] or checkB != fileHeader[-1]:
                print("Invalid checksum on file header of:",fileName)
                return
            f.read(numBytesToData)
            data = f.read()
            byteLines = [np.frombuffer(data[i:i+lineLength],dtype=np.uint8) for i in range(0, len(data), lineLength)]

    contactArr = []
    for lineNum, line in enumerate(byteLines):
        #only process contact lines
        if line[0] != 0xFD:
            continue

        length = line[1] + (line[2] << 8)
        index = 3
        while index < length:
            battTimeType = line[index+7]
            secondsOfYear = 0
            datetime = 0
            if (battTimeType & 0xC0) == 0x40:
                datetime = parsePackedTime(line[index+8:])
            elif (battTimeType & 0xC0) == 0x80:
                secondsOfYear = (parseUInt32(line[index+8:]) & 0x7FFFFFFF) >> 6

            contactArr.append(
                {"lineNum":lineNum + LINE_OFFSET,
                 "tagID":parseUInt32(line[index:]),
                 "numPages":parseUInt16(line[index+4:]),
                 "vbatt":line[index+6],
                 "datetime":datetime,
                 "secondsOfYear":secondsOfYear,
                 "RSSI":(line[index+13] & 0x7F) - (line[index+13] & 0x80) - line[index+14]}
            )
            index += 15

    df = pd.DataFrame(contactArr)

    if USE_PICKLE:
        df.to_pickle(splitext(fileName)[0]+"_contacts.pkl")
    else:
        df.to_csv(splitext(fileName)[0]+"_contacts.csv",index=False)



#if CLI given take arguments as list of files
if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [ROOT + f for f in listdir(ROOT) if isfile(join(ROOT, f)) and (f.endswith(".dat") or f.endswith(".ptdb"))]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    parseBSDat(fileName)
