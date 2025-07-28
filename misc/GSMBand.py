bands = "185079967"
bands = int(bands)
allowedStr = ""

for i in range(0,32):
    if bands % 2 == 1:
        allowedStr += "B"+str(i+1)+", "
    bands >>= 1

print(allowedStr)

bands = [1, 3, 5, 8, 20, 28, 2, 4, 12, 13, 25, 26]
allowed = 0

for band in bands:
    allowed += 2**(band-1)

print(allowed)

print("****")

bands = "2"
bands = int(bands)
allowedStr = ""

for i in range(0,32):
    if bands % 2 == 1:
        allowedStr += "B"+str(i+65)+", "
    bands >>= 1

print(allowedStr)

bands = [66]
allowed = 0

for band in bands:
    allowed += 2**(band-65)

print(allowed)


