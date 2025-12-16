from os import listdir
from os.path import isfile, join
import sys

ROOT = "./"

def unscramble(fileName):
    with open(fileName, "r") as scrambled, open(fileName[:-4]+"_unscrambled.dat","w") as unscrambled:
        line = scrambled.readline()
        while len(line) != 0:
            if not line[:1].isdigit():
                unscrambled.write(line)
            else:
                words = line.split()
                unscrambled.write(" ".join([words[(i*505) % 512] for i in range(512)])+"\n")
            line = scrambled.readline()

#if CLI given take arguments as list of files
if len(sys.argv) > 1:
    wantedFiles= sys.argv[1:]
#no command line args given, auto select all dat files in current directory
else:
    #Every file name in current directory that starts with "Obs" and ends with ".dat"
    wantedFiles = [f for f in listdir(ROOT) if isfile(join(ROOT, f)) and f.startswith("Obs") and f.endswith(".dat") and "unscrambled" not in f]

for fileName in wantedFiles:
    #only produce a combined file if there are more than 1 dat files
    unscramble(ROOT+fileName)