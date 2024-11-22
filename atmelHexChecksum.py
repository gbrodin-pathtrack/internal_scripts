#script to calculate checksum for line in hex file for atmel (intel hex format)
#paste line into string without preceding ':' and without the final byte which is the checksum

line = "10000000FFFFFFFFFFFFFFFFFF29FFFFFFFFFFFF"

pairs = [line[i:i+2] for i in range(0, len(line), 2)]
pairs = [int(pair,16) for pair in pairs]

checksum = (~(sum(pairs) & 0xFF) + 1) & 0xFF

print(hex(checksum))
