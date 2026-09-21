from os import listdir
from os.path import isfile, join, splitext
import sys
import struct

ROOT = "./"

def convertPtdFile(fileName : str):

    with open(fileName, 'rb') as ptd, open(splitext(fileName)[0]+".dat", 'w') as dat:
        headerBytes = ptd.read(14)

        headerVal = struct.unpack("<I", headerBytes[0:4])[0]
        if headerVal != 0x46495844:
            print(f"Invalid header value in file {fileName}")
            return

        if headerBytes[4] != 1:
            print(f"Unrecognised file version in header of file {fileName}")
            return

        lineLength = struct.unpack("<H", headerBytes[6:8])[0]

        if lineLength != 512:
            print(f"Only 512 byte line length supported, cannot convert file {fileName}")
            return

        numBytesToData = struct.unpack("<H", headerBytes[12:14])[0]

        checkA = 0
        checkB = 0

        for byte in headerBytes:
            checkA += byte
            checkA &= 0xFF
            checkB += checkA
            checkB &= 0xFF

        fileCheck = ptd.read(2)

        if fileCheck[0] != checkA or fileCheck[1] != checkB:
            print(f"Invalid checksum in header of file {fileName}")
            return

        ptd.read(numBytesToData)

        byteLine = ptd.read(512)
        while len(byteLine) != 0:
            dat.write(" ".join([str(byte) for byte in byteLine]) + "\n")
            byteLine = ptd.read(512)


args = sys.argv[1:]

#if CLI given take arguments as list of files
if len(args) > 0:
    wantedFiles = args
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that ends with ".dat"
    wantedFiles = [ROOT + f for f in listdir(ROOT) if isfile(join(ROOT, f)) and ".ptd" in f]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    convertPtdFile(fileName)
