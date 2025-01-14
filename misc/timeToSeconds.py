time = "9 36 11.12"

time = time.split(" ")
time[2] = time[2].split(".")[0]

seconds = int(time[0])*3600 + int(time[1])*60 + int(time[2])

print(str(seconds))