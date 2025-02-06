time = "25 10 5 20 14 39 8"
time = time.split()
time = [int(unit) for unit in time]

packedTime = [0,0,0,0,0]

packedTime[0] = (time[0] & 0x7F) + ((time[1] & 0x1) << 7)
packedTime[1] = ((time[1] & 0xE) >> 1) + ((time[2] & 0x1F) << 3)
packedTime[2] = (time[3] & 0x1F) + ((time[4] & 0x7) << 5)
packedTime[3] = ((time[4] & 0x38) >> 3) + ((time[5] & 0x1F) << 3)
packedTime[4] = ((time[6] & 0x7F) << 1) + ((time[5] & 0x20) >> 5)

print(packedTime[0],packedTime[1],packedTime[2],packedTime[3],packedTime[4])