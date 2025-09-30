import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

GPS_FILE = "./Obs_combined_Tag10178_GPS_Obs.pkl"

obsDF = pd.read_pickle(GPS_FILE)
obsDF.sort_values("datetime",inplace=True)

plt.plot(obsDF.datetime, obsDF.vbatt)
plt.show()