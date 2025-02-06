time = "25 45 212 57 17"
time = time.split()
time = [int(unit) for unit in time]

print("Year:", time[0] & 0x7F)
print("Month:", ((time[0] & 0x80) >> 7) + ((time[1] & 0x07) << 1))
print("Day:", (time[1] & 0xF8) >> 3)
print("Hour:", time[2] & 0x1F)
print("Minute:", ((time[2] & 0xE0) >> 5) + ((time[3] & 0x07) << 3))
print("Second:", ((time[3] & 0xF8) >> 3) + ((time[4] & 0x01) << 5))
print("Sub:", (time[4] & 0xFE) >> 1)