import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta

POS_FILE = "./z Mark Ketner/solar_pos/Obs030625_182414_Tag32364.pos"

posDF = pd.read_csv(POS_FILE, sep=',',skiprows=5,names=["day","month","year","hour","minute","second","secondOfDay","numSV","lat","long","height","clkOffset","acc","vbatt"])

#need to map pos datetime to obs datetime to get TTF, filter <4SV then plot TTF vs accuracy

x = posDF.numSV
y = posDF.acc

plt.scatter(x, y, marker='o', linewidth=0, alpha=0.5)
plt.plot(np.unique(x), np.poly1d(np.polyfit(x, y, 1))(np.unique(x)),color="black",linestyle=(0,(5,7)),linewidth=1)
plt.show()