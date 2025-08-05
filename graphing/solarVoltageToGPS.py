import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta

solarDF = pd.read_pickle("./z Mark Ketner/solar_pkl/Obs030625_182414_Tag32364_EHSolar.pkl")

obsDF = pd.read_pickle("./z Mark Ketner/solar_pkl/Obs030625_182414_Tag32364_GPS_Obs.pkl")

TIME_SPAN = timedelta(minutes=2.5)

obsDF["avgVOC"] = obsDF.apply(lambda x: np.mean(solarDF.loc[(solarDF["datetime"] < x.datetime + TIME_SPAN) & (solarDF["datetime"] > x.datetime - TIME_SPAN)]["VOC"]), axis = 1)

x = obsDF.avgVOC
y = obsDF.TTF

plt.scatter(x, y, marker='o', linewidth=0, alpha=0.5)
plt.plot(np.unique(x), np.poly1d(np.polyfit(x, y, 1))(np.unique(x)),color="black",linestyle=(0,(5,7)),linewidth=1)
plt.show()