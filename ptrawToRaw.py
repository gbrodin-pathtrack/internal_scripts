import sys
import struct
from os import listdir, fstat
from os.path import isfile, join, splitext
from parsers.parseNetDateTime import parse64toDateTime

ROOT = "./"

HEADER_VAL = 0x50545257

def convert(filename : str):
    if not filename.endswith(".ptraw"):
        print(f"{filename} not a .ptraw file")
        return
    with open(filename, 'rb') as ptraw, open(splitext(filename)[0]+".raw", 'w') as raw:
        fileSize = fstat(ptraw.fileno()).st_size
        headerVal = struct.unpack('<I',ptraw.read(4))[0]
        if headerVal != HEADER_VAL:
            print(f"Invalid header val in {filename}")
            return
        version = struct.unpack('B', ptraw.read(1))[0]
        if version != 1:
            print(f"Unrecognised ptraw version in {filename}")
            return
        sourceFileNameLen = struct.unpack('B', ptraw.read(1))[0] #discard source file name
        ptraw.read(sourceFileNameLen)

        raw.writelines([
            "*************************************************************************************\n",
            "PathTrack Archival Tracking System Raw Data File for Base Station 51180 (NanoFix UHF Format)\n",
            "Created 28.05.26 07:19\t\t**9646,11305**\t\t (F/W Ver. 120625-UHBnF-915D)\n",
            "DO NOT MODIFY THIS HEADER\n",
            "*************************************************************************************\n"
        ])

        while ptraw.tell() < fileSize:
            satTime = parse64toDateTime(struct.unpack('<Q', ptraw.read(8))[0])
            vbatt = struct.unpack('<d', ptraw.read(8))[0]
            ttf = struct.unpack('<f', ptraw.read(4))[0]
            numSV = struct.unpack('B', ptraw.read(1))[0]

            secOfDay = (satTime - satTime.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()

            raw.write(f"{satTime.year} {satTime.timetuple().tm_yday} {secOfDay:.1f} {vbatt:.2f} {ttf*10:.0f} {numSV}")

            for i in range(numSV):
                prn = struct.unpack('B', ptraw.read(1))[0]
                cnr = struct.unpack('B', ptraw.read(1))[0]
                ran = struct.unpack('<d', ptraw.read(8))[0]
                raw.write(f" {prn} {ran:.10f} 0 {cnr}")

            raw.write(" 32 32.0 32\n")


passedFiles = sys.argv[1:]

#if CLI given take arguments as list of files
if len(passedFiles) > 0:
    wantedFiles = passedFiles
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [ROOT + f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.endswith(".ptraw")]

for file in wantedFiles:
    convert(file)