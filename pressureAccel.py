import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.signal
import pandas as pd
import time

def highpass(data: np.ndarray, cutoff: float, sample_rate: float, poles: int = 5):
    sos = scipy.signal.butter(poles, cutoff, 'highpass', fs=sample_rate, output='sos')
    filtered_data = scipy.signal.sosfiltfilt(sos, data)
    return filtered_data

def lowpass(data: np.ndarray, cutoff: float, sample_rate: float, poles: int = 5):
    sos = scipy.signal.butter(poles, cutoff, 'lowpass', fs=sample_rate, output='sos')
    filtered_data = scipy.signal.sosfiltfilt(sos, data)
    return filtered_data

TB = 288.15
R = 8.3144598
LB = -0.0065
G0 = 9.80665
M = 0.0289644
POW = (R*LB)/(G0*M)

def heightFromPressure(pressure, sealevelpressure):
    if pressure < sealevelpressure:
        height = (TB/LB) * (1-pow(pressure/sealevelpressure,POW))
    else:
        height = pressure*-0.010197
    return height

def check_and_gen_cal(x):
    #static so is a calibration point
    if 0.98< x.smoothed_mag < 1.05:
        #sat at sea level, smoothed press can be calibration value
        if x.smoothed_press > 990:
            return x.smoothed_press
        #sat in burrow, calibrate offset for 230m
        return x.smoothed_press + 29.158
    
    #not static so not a calibration point
    return np.NaN

start = time.time()

file = "pressure tests/real/mousa/Tag14179/Obs160824_145018_Tag14179"
#"pressure tests/real/mousa/Tag14179/Obs160824_145018_Tag14179"
#"pressure tests/real/mousa/Tag14179/Obs070824_093824_Tag14179"
#"pressure tests/real/mousa/Tag14179/Obs020824_092751_Tag14179"
#"pressure tests/real/mousa/Tag14174/Obs170824_123700_Tag14174"
#"pressure tests/real/mousa/Tag14178/Obs160824_152218_Tag14178"

#"pressure tests/real/Tag14172/Obs210724_161035_Tag14172"
#pressure tests/real/Tag14172/Obs210724_161035_Tag14172PressTemp.txt

pressTemp = pd.read_csv(file+"PressTemp.txt", 
                        header=None, 
                        names=["year","month","day","hour","minute","second","temp","press","height_file"],
                        skiprows=5)
pressTemp["timetag"] = pd.to_datetime(pressTemp[['year', 'month', 'day','hour','minute','second']])
pressTemp = pressTemp.drop(columns=['year', 'month', 'day','hour','minute','second'])
#print(pressTemp.head())
pressTemp.info()

#pressure tests/real/Tag14172/Obs210724_161035_Tag14172Accel.txt

accel = pd.read_csv(file+"Accel.txt",
                    delimiter=' ',
                    header=None,
                    names=["year","month","day","hour","minute","second","x","y","z","mag"],
                    skiprows=5)
accel["timetag"] = pd.to_datetime(accel[['year', 'month', 'day','hour','minute','second']])
accel = accel.drop(columns=['year', 'month', 'day','hour','minute','second'])
accel["smoothed_mag"] = lowpass(accel["mag"],0.1,12.5)
#print(accel.head())
accel.info()

# weather = pd.read_csv("pressure tests/real/EGPL_15_to_18.csv")
# weather["timetag"] = pd.to_datetime(weather["datetime"])
# weather = weather.drop(weather.columns.difference(["timetag","sealevelpressure"]),axis=1)
# weather.info()

# weather2 = pd.read_csv("pressure tests/real/st_kilda_15_to_18.csv")
# weather2["timetag"] = pd.to_datetime(weather2["datetime"])
# weather2 = weather2.drop(weather2.columns.difference(["timetag","sealevelpressure"]),axis=1)
# weather2.rename(columns={"sealevelpressure":"sealevelpressure2"}, inplace=True)
# weather2.info()

#pressTemp["smoothed_press"] = lowpass(pressTemp["press"],0.01,1)
#pressTemp["smoothed_press"] = scipy.signal.savgol_filter(pressTemp["press"],200,3)
#pressTemp["smoothed_press"] = pressTemp["press"].rolling(window=200, min_periods=0, center=True).mean()
#peakIndecies, peakProperties = scipy.signal.find_peaks(pressTemp["smoothed_press"],wlen=2000,prominence=0.5) #.where(pressTemp["smoothed_press"].between(990,1020)),wlen=2000
#print(peakProperties)
# peakLRs = []
# for a,b in zip(peakProperties["left_bases"],peakProperties["right_bases"]):
#     peakLRs += list(range(a,b))
# peakLRs = list(set(peakLRs))
#peakLRs = list(range(peakProperties["left_bases"][0],peakProperties["right_bases"][0]))
# pressTemp["peak_tops"] = pressTemp.iloc[peakIndecies].smoothed_press #smoothed_
# pressTemp["peak_left_edges"] = pressTemp.iloc[list(set(peakProperties["left_bases"]))].smoothed_press #smoothed_
# pressTemp["peaks"] = pressTemp.iloc[peakLRs].smoothed_press #smoothed_
#pressTemp["peaks_p"] = pressTemp.iloc[peakIndecies].smoothed_press
# pressTemp["peak_tops"].where(pressTemp["peak_tops"].between(990,1020), inplace=True)
# pressTemp["peak_tops"] = pressTemp["peak_tops"].interpolate()
# pressTemp["peak_left_edges"].where(pressTemp["peak_left_edges"].between(990,1020), inplace=True)
# pressTemp["peak_left_edges"] = pressTemp["peak_left_edges"].interpolate()
#pressTemp = pd.merge(pressTemp, accel, how="outer", on="timetag")
# pressTemp = pd.merge(pressTemp, weather, how="outer", on="timetag")
# pressTemp = pd.merge(pressTemp, weather2, how="outer", on="timetag")
#pressTemp = pressTemp.drop(pressTemp.columns.difference(["press","height","timetag","smoothed_press","smoothed_mag","sealevelpressure","sealevelpressure2","peaks"]),axis=1)
pressTemp = pressTemp.sort_values(by=['timetag'])
pressTemp = pressTemp.set_index('timetag',drop=False)
# pressTemp['sealevelpressure'] = pressTemp['sealevelpressure'].interpolate("index")
# pressTemp['sealevelpressure2'] = pressTemp['sealevelpressure2'].interpolate("index")
# pressTemp['smoothed_mag'] = pressTemp['smoothed_mag'].interpolate("index")
#pressTemp = pressTemp.dropna(subset=["press","smoothed_press","smoothed_mag"])
#pressTemp["cal_point"] = pressTemp.apply(check_and_gen_cal, axis=1)
#pressTemp["cal_point"] = pressTemp["cal_point"].combine_first(pressTemp["peaks"])
#pressTemp['cal'] = pressTemp['cal_point'].interpolate("index")
#pressTemp["combined_cal"] = pressTemp.apply(lambda x: (x.cal + x.sealevelpressure)/2, axis=1)
#pressTemp["delta_cal"] = pressTemp["press"] - pressTemp["cal"]
#pressTemp["delta"] = pressTemp["press"] - 1013.25
#pressTemp["delta_weather"] = pressTemp["press"] - pressTemp["sealevelpressure"]
#pressTemp["delta_weather2"] = pressTemp["press"] - pressTemp["sealevelpressure2"]
#pressTemp["delta_peaks"] = pressTemp["press"] - pressTemp["peaks"]
#pressTemp["height_cal"] = pressTemp.apply(lambda x: x.delta_cal*-7.8880172892718 if x.delta_cal <= 0 else x.delta_cal*-0.010197, axis=1)
#pressTemp["height_weather"] = pressTemp.apply(lambda x: x.delta_weather*-7.8880172892718 if x.delta_weather <= 0 else x.delta_weather*-0.010197, axis=1)
#pressTemp["height_peaks"] = pressTemp.apply(lambda x: x.delta_peaks*-7.8880172892718 if x.delta_peaks <= 0 else x.delta_peaks*-0.010197, axis=1)
pressTemp["height_uncal"] = pressTemp.apply(lambda x: heightFromPressure(x.press, 1013.25), axis=1) #lambda x: x.delta*-7.8880172892718 if x.delta <= 0 else x.delta*-0.010197

pressTemp.info()
print(pressTemp.head())

print("Load time: ",round(time.time() - start,2),"s")

plotAccel = 1
labelSeconds = 1
plotPressure = 1

if plotAccel:
    ax1 = plt.subplot(211)
else:
    ax1 = plt.subplot(111)

if labelSeconds:
    dateFmtString = "%H:%M:%S"
    xLabelString = "Time (hh:mm:ss)"
else:
    dateFmtString = "%m/%d - %H:%M"
    xLabelString = "Datetime (MM/DD - hh:mm)"

dateFmt = mdates.DateFormatter(dateFmtString)#%m/%d - %H:%M #%H:%M:%S
ax1.set_xlabel(xLabelString)#Datetime (MM/DD - hh:mm:ss) #Time (hh:mm:ss)
ax1.xaxis.set_major_formatter(dateFmt)

if plotPressure:
    ax1.set_ylabel("Pressure (mBar)")

    ax1.plot(pressTemp.timetag, pressTemp.press, color="tab:blue", label="Measured Pressure")
    #ax1.plot(pressTemp.timetag, pressTemp.smoothed_press, color="tab:orange",label="Smoothed Measured Pressure")

    #ax1.plot(pressTemp.timetag, pressTemp.sealevelpressure, color="xkcd:hot pink", label="Sea Level Pressure: EGPL")
    #ax1.plot(pressTemp.timetag, pressTemp.sealevelpressure2, color="xkcd:lavender", label="Sea Level Pressure: St Kilda")

    #ax1.plot(pressTemp.timetag, pressTemp.peaks, color="xkcd:forest green",label="Peaks")
    #ax1.plot(pressTemp.timetag, pressTemp.peak_tops, color="xkcd:green",label="Peak Tops")
    #ax1.plot(pressTemp.timetag, pressTemp.peak_left_edges, color="xkcd:neon green",label="Peak Left Edges")

    #ax1.plot(pressTemp.timetag, pressTemp.cal, color="xkcd:red", label="Calculated Calibration Curve")
    #ax1.plot(pressTemp.timetag, pressTemp.cal_point, color="xkcd:golden yellow", label="Calibration Points")
else:
    ax1.set_ylabel("Height (m)")
    ax1.axhline(y=0,color="black")

    #ax1.plot(pressTemp.timetag, pressTemp.height_file, color="tab:blue", label= "File Height")
    #ax1.plot(pressTemp.timetag, pressTemp.delta, color="tab:blue", label="Delta Pressure: 1013.25")
    #ax1.plot(pressTemp.timetag, pressTemp.delta_weather, color="tab:orange", label="Delta Pressure: EGPL")
    #ax1.plot(pressTemp.timetag, pressTemp.delta_cal, color="tab:red", label="Delta Pressure: Calibration Curve")
    #ax1.plot(pressTemp.timetag, pressTemp.delta_weather2, color="tab:red", label="Delta Pressure: St Kilda")
    #ax1.plot(pressTemp.timetag, pressTemp.delta_peaks, color="tab:green")
    #ax1.plot(pressTemp.timetag, pressTemp.height_cal, color=col)
    #ax1.plot(pressTemp.timetag, lowpass(pressTemp.height_weather,0.01,1), color="tab:blue",label="Smoothed Calibrated Height")
    #ax1.plot(pressTemp.timetag, pressTemp.height_weather, color="tab:blue",label="Calibrated Height")
    #ax1.plot(pressTemp.timetag, pressTemp.height_peaks, color="tab:orange")
    ax1.plot(pressTemp.timetag, pressTemp.height_uncal, color="tab:orange", label="Uncalibrated Height")

ax1.legend(loc="upper left")

if plotAccel:
    ax2 = plt.subplot(212, sharex=ax1)
    ax2.set_ylabel("Acceleration (g)")
    
    col = "tab:red"
    #ax2.set_ylim(0.8,1.3)
    ax2.axhline(y=1,color="black")
    #ax2.axhline(y=0,color="black")
    #ax2.plot(accel.timetag, accel.mag, color=col, label="Acceleration (Magnitude)")
    #ax2.plot(accel.timetag, highpass(accel.mag,5,12.5), color=col)
    ax2.plot(accel.timetag, accel.smoothed_mag, color=col, label="Smoothed Acceleration (Magnitude)")
    # ax2.plot(accel.timetag, lowpass(accel.x,0.05,12.5), color="tab:red", label="x")
    # ax2.plot(accel.timetag, lowpass(accel.y,0.05,12.5), color="tab:green", label="y")
    # ax2.plot(accel.timetag, lowpass(accel.z,0.05,12.5), color="tab:blue", label="z")
    ax2.legend(loc="upper left")
    

# ax3 = plt.subplot(313, sharex=ax1)

# col="tab:green"
# ax3.set_ylabel("temp")
# ax3.plot(pressTemp.timetag, pressTemp.temp, color=col)

plt.show()