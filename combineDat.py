from os import listdir
from os.path import isfile, join
import sys

#if CLI given take arguments as list of files
if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
#no command line args given, auto select all dat files in current directory
else:
    wantedFiles = [f for f in listdir("./") if isfile(join("./", f)) and f.endswith(".dat") and "combined" not in f]

skipLines = 0
with open("combined.dat","w") as combinedFile:
    for file in wantedFiles:
        with open(file,'r') as datFile:
            combinedFile.writelines(datFile.readlines()[skipLines:])
            skipLines = 5

