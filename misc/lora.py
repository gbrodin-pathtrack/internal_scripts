import numpy as np
import pandas as pd

SF = [5,6,7,8,9,10,11,12]
SNR = {5:-2.5,6:-5,7:-7,8:-9.5,9:-12,10:-14.5,11:-17,12:-19}
BW = [7.81,10.42,15.63,20.83,31.25,41.67,62.5,125,250,500]
CR = 1
PR = 12
CRC = 1
PL = 136 #128 data + 8 byte header
NF = 6
HEADER = False

def NbSymbolPayloadFrac(header : bool, pl, crc, sf, cr):
    return ((pl*8 + crc*16 - 4*(sf-(7 if header else 2))) * (4+cr)) / (4*sf)

def NbSymbolPayload(header : bool, pl, crc, sf, cr):
    return np.ceil(NbSymbolPayloadFrac(header, pl, crc, sf, cr) * (4+cr))

def TotalTimeOnAir(header : bool, pr, pl, crc, sf, cr, bw):
    return (pr + NbSymbolPayload(header,pl,crc,sf,cr) + 4.25 + 8) * ((2**sf) / bw)

def RawBitRate(sf, bw, cr):
    return ((sf*bw) / (2**sf)) * (4 / (4+cr))

def RealBitRate(header : bool, pr, pl, crc, sf, cr, bw):
    return (pl*8) / TotalTimeOnAir(header, pr, pl, crc, sf, cr, bw)

def sens(sf, bw, nf):
    return -174 + 10 * np.log10(bw*1000) + nf + SNR[sf]

combos = np.array(np.meshgrid(SF,BW)).T.reshape(-1,2)

df = pd.DataFrame(combos, columns=["SF","BW"])

df["rawBitRate"] = df.apply(lambda x: RawBitRate(x.SF, x.BW, CR)*1000, axis=1)
df["realBitRate"] = df.apply(lambda x: RealBitRate(HEADER, PR, PL, CRC, x.SF, CR, x.BW)*1000, axis=1)
df["sensitivity"] = df.apply(lambda x: sens(x.SF, x.BW, NF), axis=1)
df["timeToSend"] = df.apply(lambda x: (512*8)/x.realBitRate, axis=1)

df.to_csv("lora.csv",index=False)