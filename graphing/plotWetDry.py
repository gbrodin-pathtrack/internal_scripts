import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def convertDatetime(x):
    dt = datetime(year=int(x.year), month=1, day=1)
    offset = timedelta(days=(int(x.day) - 1),seconds=int(x.second))
    dt += offset
    return pd.to_datetime(dt)

#accelImmersionDF = pd.read_csv("./z leg rings/Tag60816/Obs190625_181807_Tag60816MERGEDAccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag60818/Obs300525_112508_Tag60818AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag60830/Obs190625_190938_Tag60830MERGEDAccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag60838/Obs170625_201211_Tag60838MERGEDAccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag60940/Obs100225_084510_Tag60940AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag60954/Obs280625_210215_Tag60954AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag60960/Obs030725_180627_Tag60960AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag60985/Obs130625_180250_Tag60985AccWetDry_noreset.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag61029/Obs070625_212952_Tag61029AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag61032/Obs300625_135223_Tag61032_combinedAccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag61033/Obs050625_200759_Tag61033AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag61035/Obs210625_200606_Tag61035_combinedAccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag61049/Obs170625_165524_Tag61049_combinedAccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag61061/Obs170625_210619_Tag61061AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag61063/Obs170625_203140_Tag61063_combinedAccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag61068/Obs130825_230454_Tag61068AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
accelImmersionDF = pd.read_csv("./z leg rings/Tag61086/Obs130825_224531_Tag61086AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)
#accelImmersionDF = pd.read_csv("./z leg rings/Tag61090/Obs030725_184037_Tag61090AccWetDry.txt",sep=' ',names=["year","month","day","hour","minute","second","X","Y","Z","mag","immersed"],header=None,skiprows=5)

accelImmersionDF["datetime"] = pd.to_datetime(accelImmersionDF[["year","month","day","hour","minute","second"]])

#gpsDF = pd.read_csv("./z leg rings/Tag60816/Obs190625_181807_Tag60816MERGED.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag60818/Obs300525_112508_Tag60818.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag60830/Obs190625_190938_Tag60830MERGED.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag60838/Obs170625_201211_Tag60838MERGED.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag60940/Obs100225_084510_Tag60940.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag60954/Obs280625_210215_Tag60954.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag60960/Obs030725_180627_Tag60960.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag60985/Obs130625_180250_Tag60985_noreset.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag61029/Obs070625_212952_Tag61029.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag61032/Obs300625_135223_Tag61032_combined.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag61033/Obs050625_200759_Tag61033.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag61035/Obs210625_200606_Tag61035_combined.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag61049/Obs170625_165524_Tag61049_combined.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag61061/Obs170625_210619_Tag61061.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag61063/Obs170625_203140_Tag61063_combined.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag61068/Obs130825_230454_Tag61068.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
gpsDF = pd.read_csv("./z leg rings/Tag61086/Obs130825_224531_Tag61086.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)
#gpsDF = pd.read_csv("./z leg rings/Tag61090/Obs030725_184037_Tag61090.raw",sep=' ', names=["year","day","second","vbatt","TTF","numSVs"], usecols=[0,1,2,3,4,5], header=None, skiprows=5)

gpsDF["datetime"] = gpsDF.apply(lambda x: convertDatetime(x), axis=1)

fig, ax1 = plt.subplots()

#plt.title("1 min accel and immersion samples with GPS times marked")

col = "tab:blue"
ax1.set_xlabel("Datetime")
ax1.set_ylabel("Immersed (boolean)", color=col)
ax1.plot(accelImmersionDF["datetime"], accelImmersionDF["immersed"], color=col)
ax1.tick_params(axis="y", labelcolor=col)

plt.vlines(gpsDF.datetime, ymin=0.2, ymax=0.8, colors='green')

ax2 = ax1.twinx()

col = "tab:red"
ax2.set_ylabel("Acceleration magnitude (g)", color=col)
# ax2.plot(accelImmersionDF["datetime"],accelImmersionDF["X"], color="red")
# ax2.plot(accelImmersionDF["datetime"],accelImmersionDF["Y"], color="green")
# ax2.plot(accelImmersionDF["datetime"],accelImmersionDF["Z"], color="blue")
ax2.plot(accelImmersionDF["datetime"],accelImmersionDF["mag"], color=col)

ax2.tick_params(axis="y", labelcolor=col)

plt.tight_layout()
plt.show()
