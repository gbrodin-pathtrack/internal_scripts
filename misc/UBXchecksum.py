UBX_MESSAGE = """
            0x06, 0x8A,				/* UBX-CFG-VALSET */
            0x51, 0x00,				/* length 80 */
            0x00,					/* msg version 0 */
            0x01,					/* update in RAM */
            0x00, 0x00,				/* reserved */
 
            0x01, 0x00, 0x74, 0x10,	/* CFG-UART1OUTPROT-UBX */
            0x01,					/* On */
 
            0x02, 0x00, 0x74, 0x10,	/* CFG-UART1OUTPROT-NMEA */
            0x00,					/* Off */
 
            0x07, 0x00, 0x91, 0x20, /* UBX-NAV-PVT */
            0x01,					/* 1 message per measurement */
 
            0x02, 0x00, 0x21, 0x30, /* CFG-RATE-NAV */
            0x01, 0x00,					/* 1 solution per measurement */
 
            0x01, 0x00, 0x21, 0x30,	/* CFG-RATE-MEAS */
            0xD0, 0x07,				/* 2000ms (0.5Hz) */
 
            0x1f, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-GPS_ENA - GPS enable */
            0x01,					/* On */
 
            0x01, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-GPS_L1CA_ENA - GPS L1C/A */
            0x01,					/* On */
 
            0x20, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-SBAS_ENA - SBAS enable */
            0x01,					/* On */
 
            0x05, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-SBAS_L1CA_ENA - SBAS L1C/A */
            0x01,					/* On */
 
            0x21, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-GAL_ENA - Galileo enable */
            0x00,					/* Off */
 
            0x22, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-BDS_ENA - BeiDou enable */
            0x00,					/* Off */
 
            0x24, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-QZSS_ENA - QZSS enable */
            0x01,					/* On */
 
            0x12, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-QZSS_L1CA_ENA - QZSS L1C/A */
            0x01,					/* On */
 
            0x14, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-QZSS_L1S_ENA - QZSS L1S */
            0x00,					/* Off */
 
            0x25, 0x00, 0x31, 0x10,	/* CFG-SIGNAL-GLO_ENA - GLONASS enable */
            0x00,					/* Off */
"""

import re
import sys
PATTERN = r'//.*?$|/\*.*?\*/'

if len(sys.argv) > 1:
    text = sys.argv[1]
else:
    text = UBX_MESSAGE

text = text.split("\n")
bytes = []
for line in text:
    line = re.sub(PATTERN, '', line, flags=re.DOTALL)
    nums = line.strip().split(',')
    nums = [x for x in nums if x]
    for num in nums:
        bytes.append(int(num,16))

checkA = 0
checkB = 0

for byte in bytes:
    checkA += byte
    checkA &= 0xFF
    checkB += checkA
    checkB &= 0xFF

print("check sum:","0x{:02x}".format(checkA).upper().replace('X','x')+",","0x{:02x}".format(checkB).upper().replace('X','x'))
payloadLen = len(bytes)-4
payloadLenL = payloadLen & 0xFF
payloadLenH = (payloadLen>>8) & 0xFF
print("Payload length:","0x{:02x}".format(payloadLenL).upper().replace('X','x')+",","0x{:02x}".format(payloadLenH).upper().replace('X','x')+",")
print(".length = ",len(bytes)+4)
