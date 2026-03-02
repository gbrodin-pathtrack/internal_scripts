INTPUT_FILE_NAME = "Obs230226_174555_BS51144.dat"

REMOVE_LINES = [400, 404, 406, 410, 414, 418, 440, 442, 446, 474, 500, 625, 641, 651, 653, 655, 659, 661, 932, 1382, 1384]

# with open(INTPUT_FILE_NAME, 'r') as f:
#     lines = f.readlines()

# newLines = []

# for i in range(len(lines)):
#     if (i+1) in REMOVE_LINES:
#         continue
#     newLines.append(lines[i])

# with open(OUTPUT_FILE_NAME, 'w') as f:
#     f.writelines(newLines)

with open(INTPUT_FILE_NAME, 'r') as original, open(INTPUT_FILE_NAME[:-4]+"_clean.dat", 'w') as clean, open(INTPUT_FILE_NAME[:-4]+"_removed.dat", 'w') as removed:
    i = 1
    line = original.readline()
    while line != "":
        if i in REMOVE_LINES:
            removed.writelines(line)
        else:
            clean.writelines(line)
        line = original.readline()
        i += 1