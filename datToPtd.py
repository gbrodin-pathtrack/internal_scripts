from os import listdir
from os.path import isfile, join, splitext
import sys
import re

ROOT = "./"

def convertDatFile(fileName : str, uhf : bool):
    if uhf:
        extension = ".ptdb"
    else:
        extension = ".ptdl"

    tagID = -1

    with open(fileName, 'r') as dat, open(splitext(fileName)[0]+extension, 'wb') as ptd:
        matchTag = re.search(r"Tag(\d+)", fileName)
        matchBS = re.search(r"BS(\d+)", fileName)
        fileTagID = 65535
        if not matchTag and not matchBS:
            print("Couldn't get tag ID from file name, using tag ID 65535")
        elif matchTag:
            fileTagID = int(matchTag.group(1))
        else:
            fileTagID = int(matchBS.group(1))
        headerBytes = bytes([0x44, 0x58, 0x49, 0x46, #FIXD
                             0x01, #Version 1
                             0x00, #padding
                             0x00, 0x02, #512 byte lines
                             fileTagID & 0xFF, #Device ID
                             (fileTagID >> 8) & 0xFF,
                             (fileTagID >> 16) & 0xFF,
                             (fileTagID >> 24) & 0xFF,
                             0x00, 0x00, #num padding bytes
                             ])

        ptd.write(headerBytes)

        checkA = 0
        checkB = 0

        for byte in headerBytes:
            checkA += byte
            checkA &= 0xFF
            checkB += checkA
            checkB &= 0xFF

        ptd.write(bytes([checkA, checkB]))
        while (line := dat.readline()) != "":
            if not line[:1].isdigit():
                continue
            intLine = [int(byte) for byte in line.split()]

            if uhf and len(intLine) != 516:
                print("line not 516 bytes long")
                exit(1)
            elif not uhf and len(intLine) != 512:
                print("line not 512 bytes long")
                exit(1)

            if uhf:
                intLine = intLine[:512]
                lineTagID = intLine[3] + (intLine[4] << 8)
                if lineTagID != tagID:
                    contactInts = [0 for _ in range(512)]
                    contactInts[0] = 0xFD
                    contactInts[1] = 18
                    contactInts[3] = lineTagID & 0xFF
                    contactInts[4] = (lineTagID >> 8) & 0xFF
                    contactInts[5] = (lineTagID >> 16) & 0xFF
                    contactInts[6] = (lineTagID >> 24) & 0xFF
                    contactBytes = bytes(contactInts)
                    ptd.write(contactBytes)
                    tagID = lineTagID

            byteLine = bytes(intLine)
            ptd.write(byteLine)


args = sys.argv[1:]

#if CLI given take arguments as list of files
if len(args) > 0:
    wantedFiles = args
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that ends with ".dat"
    wantedFiles = [ROOT + f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith(".dat")]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    convertDatFile(fileName, fileName.find("BS") != -1)
