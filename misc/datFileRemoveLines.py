INTPUT_FILE_NAME = "Obs_consensus_Tag49240.dat"

OUTPUT_FILE_NAME = "Obs_fixed_Tag49240.dat"

REMOVE_LINES = [17, 49, 51, 56, 70, 73, 81, 82, 116, 124, 126, 134, 141, 150, 157, 162, 165, 169, 188, 203, 246, 254, 264, 265, 297, 316, 324, 330, 375, 405, 423, 441, 462, 507, 512, 545, 553, 554, 564, 565, 571, 583, 593, 594, 598, 608, 646, 672, 684, 698, 727]

with open(INTPUT_FILE_NAME, 'r') as f:
    lines = f.readlines()

newLines = []

for i in range(len(lines)):
    if (i+1) in REMOVE_LINES:
        continue
    newLines.append(lines[i])

with open(OUTPUT_FILE_NAME, 'w') as f:
    f.writelines(newLines)