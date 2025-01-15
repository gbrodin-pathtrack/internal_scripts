import numpy as np
import matplotlib.pyplot as plt
import scipy.signal

def highpass(data: np.ndarray, cutoff: float, sample_rate: float, poles: int = 5):
    #sos = scipy.signal.butter(poles, cutoff, 'highpass', fs=sample_rate, output='sos')
    sos = scipy.signal.cheby2(poles,60, cutoff, 'highpass', fs=sample_rate, output='sos')
    filtered_data = scipy.signal.sosfiltfilt(sos, data)
    return filtered_data

def lowpass(data: np.ndarray, cutoff: float, sample_rate: float, poles: int = 5):
    sos = scipy.signal.butter(poles, cutoff, 'lowpass', fs=sample_rate, output='sos')
    filtered_data = scipy.signal.sosfiltfilt(sos, data)
    return filtered_data

def bandpass(data: np.ndarray, edges: list[float], sample_rate: float, poles: int = 5):
    sos = scipy.signal.butter(poles, edges, 'bandpass', fs=sample_rate, output='sos')
    filtered_data = scipy.signal.sosfiltfilt(sos, data)
    return filtered_data

driftData = np.loadtxt("pressure tests/processing tests/indoor_moved_shelves.txt") #indoor_static #outdoor_static_noisy #indoor_moved_shelves

frequency = 0.001
datapoints = len(driftData)
length = np.pi * 2 * datapoints * frequency

magnitude = 0
artificialData = np.sin(np.arange(0, length, length/datapoints))*0.1

numSteps = 200
stepOffset = 9000
stepWidth = datapoints/4
zeros = np.zeros(stepOffset)
zeroToOne = np.arange(0,1,1/numSteps)
ones = np.repeat(1, stepWidth)
oneToZero = np.flip(zeroToOne)
stepUp = np.concatenate([zeros,zeroToOne,ones,oneToZero])
stepUp.resize(datapoints)

maskSize = 2000
maskZeros = np.zeros(maskSize)
maskOnes = np.ones(datapoints-maskSize*2)
mask = np.concatenate([maskZeros,maskOnes,maskZeros])

#artificialData -= stepUp

artificialData *= magnitude
artificialData *= mask

modifiedData = driftData + artificialData

# calibrationPoints = [[0,0],[3000,0],[6000,0],[7650,0],[datapoints,0]] #,[2400,0],[5000,0],[8000,0],[18000,0],[23000,0]

# calibrationPoints[0][1] = np.average(modifiedData[:500])
# for point in calibrationPoints[1:-1]:
#     point[1]= np.average(modifiedData[point[0]-100:point[0]+100])
# calibrationPoints[-1][1] = np.average(modifiedData[-500:])

# lowFreq = np.array([])
# for start, end in zip(calibrationPoints, calibrationPoints[1:]):
#     lowFreq = np.concatenate([lowFreq, np.linspace(start[1],end[1],end[0]-start[0])])

#lowFreq = lowpass(lowFreq, 0.0005, 1)

startPressure = np.average(modifiedData[:100])
endPressure = np.average(modifiedData[-100:])
lowFreq = np.linspace(startPressure,endPressure,datapoints)

# w = int(datapoints/4)
# lowFreq = scipy.signal.savgol_filter(modifiedData,w,1)

#lowFreq = lowpass(modifiedData, 0.001, 1)

filtered = modifiedData - lowFreq

#filtered = highpass(modifiedData, 0.01, 1)


#filtered = np.cumsum(lowpass(np.diff(modifiedData),0.2,1))
# filtered = np.convolve(modifiedData, np.ones(3), 'valid')/3
# diffed = np.diff(modifiedData)
# diffed[abs(diffed) < 0.005] = 0
# filtered = np.cumsum(diffed)

#np.savetxt("filtered.txt", data)

fig, axs = plt.subplot_mosaic("BC;AA")

axs["B"].plot(driftData, label="Real Static Data")
axs["B"].plot(lowFreq, label="Aproximation from Combined")
axs["B"].legend(loc='upper right')

axs["C"].plot(modifiedData, label="Combined Artificial and Real")
axs["C"].legend(loc='upper right')

axs["A"].plot(filtered, label="Filtered Data")
axs["A"].plot(artificialData, label="Artificial Data")
axs["A"].legend(loc='upper right')
plt.show()