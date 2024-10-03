text = """
            0x06, 0x01, //UBX-CFG-MSG
            0x08, 0x00, //length 8
            0xF0, 0x00, //GAA class/ID
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, //disable on all ports
            0x16, 0x03 //check sum
"""

text = text.split("\n")
lines = []
for line in text:
    print(line.split("//")[0].strip())
