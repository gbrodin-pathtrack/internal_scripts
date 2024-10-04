import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.cm as cm
import matplotlib.colors as col
import matplotlib.ticker as ticker
import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns

TB = 288.15
R = 8.3144598
LB = -0.0065
G0 = 9.80665
M = 0.0289644
POW = (R*LB)/(G0*M)
POW_L = R/(G0*M)
PB = 1013.25
MULT = R/(G0*M)

def inverseBarometricFormula(pressure, refTemp):
    height = (refTemp/LB) * (1-pow(pressure/PB,POW))
    return height

def inverseBarometricFormulaLapse(pressure, lapseRate):
    height = (TB/lapseRate) * (1-pow(pressure/PB,POW_L*lapseRate))
    return height

def hypsometricFormula(pressure, refTemp, currTemp):
    height = MULT*np.mean([refTemp,currTemp])*np.log(PB/pressure)
    return height

def absDiffFromBarometric(pressure, y, height):
    barHeight = inverseBarometricFormula(pressure,TB)
    return height - barHeight

def percentDiffFromBarometric(pressure, y, height):
    barHeight = inverseBarometricFormula(pressure,TB)
    return 100*(height - barHeight)/barHeight

def map_colors(p3dc, func, cmap='jet', norm=col.Normalize()):
    """
    Color a tri-mesh according to a function evaluated in each barycentre.

    p3dc: a Poly3DCollection, as returned e.g. by ax.plot_trisurf
    func: a single-valued function of 3 arrays: x, y, z
    cmap: a colormap NAME, as a string

    Returns a ScalarMappable that can be used to instantiate a colorbar.
    """

    # reconstruct the triangles from internal data
    x, y, z, _ = p3dc._vec
    slices = p3dc._segslices
    triangles = np.array([np.array((x[s],y[s],z[s])).T for s in slices])

    # compute the barycentres for each triangle
    xb, yb, zb = triangles.mean(axis=1).T
    
    # compute the function in the barycentres
    values = func(xb, yb, zb)

    # usual stuff
    colors = mpl.colormaps[cmap](norm(values))

    # set the face colors of the Poly3DCollection
    p3dc.set_fc(colors)

    # if the caller wants a colorbar, they need this
    return cm.ScalarMappable(cmap=cmap, norm=norm)

def showPlot3dBarErrRefTemp():
    tempArr = np.linspace(TB-20,TB+20,99)
    pressArr = np.linspace(PB-500,PB,501)

    data = pd.DataFrame(np.array(np.meshgrid(tempArr, pressArr)).T.reshape(-1,2), columns=['temp','press'])

    data['height'] = data.apply(lambda x: inverseBarometricFormula(x.press,x.temp), axis=1)

    ax = plt.figure().add_subplot(projection='3d')

    p3dc = ax.plot_trisurf(data.press, data.temp, data.height, linewidth=0, antialiased = False)

    #mappable = map_colors(p3dc, absDiffFromBarometric, norm = col.SymLogNorm(10))
    mappable = map_colors(p3dc, percentDiffFromBarometric)

    minTick = mappable.get_clim()[0]
    maxTick = mappable.get_clim()[1]

    plt.colorbar(mappable, shrink=0.5, format="%3d", label="Absolute Error (m)", ax=ax) #, ticks=np.linspace(minTick,maxTick,5)

    ax.set_xlabel("Measured Pressure (mbar)")
    ax.set_ylabel("Reference Temp (K)")
    ax.set_zlabel("Calculated Height (m)")
 
    ax.view_init(20,40)

    plt.show()

def showPlot3dBarVHypTempDiff():
    tempDiffArr = np.linspace(TB-10,TB+10,99)
    pressArr = np.linspace(PB-500,PB,501)

    df = pd.DataFrame(np.array(np.meshgrid(tempDiffArr, pressArr)).T.reshape(-1,2), columns=['tempDiff','pressure'])

    df["height_b"] = df.apply(lambda x: inverseBarometricFormula(x.pressure, TB), axis=1)
    df["lapse_temp"] = df.apply(lambda x: TB+(x.height_b*LB), axis=1)
    df["height_h"] = df.apply(lambda x: hypsometricFormula(x.pressure, TB, x.lapse_temp+x.tempDiff), axis=1)

    ax = plt.figure().add_subplot(projection='3d')

    p3dc = ax.plot_trisurf(df.pressure, df.tempDiff, df.height_h, linewidth=0, antialiased = False)

    mappable = map_colors(p3dc, absDiffFromBarometric)

    minTick = mappable.get_clim()[0]
    maxTick = mappable.get_clim()[1]

    plt.colorbar(mappable, shrink=0.5, format="%3d", ticks=np.linspace(minTick,maxTick,7), label="Percent Difference (%)", ax=ax)

    ax.set_xlabel("Measured Pressure (mbar)")
    ax.set_ylabel("Difference from Lapse Temp (K)")
    ax.set_zlabel("Calculated Hypsometric Height (m)")
 
    ax.view_init(20,40)

    plt.show()

def showPlot3dBarErrLapseRateHeight():
    lapseArr = np.linspace(LB*1.5,LB*0.5,45)
    pressArr = np.linspace(PB-500,PB,251)

    df = pd.DataFrame(np.array(np.meshgrid(lapseArr, pressArr)).T.reshape(-1,2), columns=['lapse','pressure'])

    df["height"] = df.apply(lambda x: inverseBarometricFormulaLapse(x.pressure, x.lapse), axis=1)

    ax = plt.figure().add_subplot(projection='3d')

    p3dc = ax.plot_trisurf(df.pressure, df.lapse-LB, df.height, linewidth=0, antialiased = False)

    mappable = map_colors(p3dc, percentDiffFromBarometric, cmap="seismic")#, norm=col.SymLogNorm(0.25)

    minTick = mappable.get_clim()[0]
    maxTick = mappable.get_clim()[1]

    plt.colorbar(mappable, shrink=0.5, format="%3d", ticks=np.linspace(minTick,maxTick,7), label="Percent Difference (%)", ax=ax)#, ticks=np.linspace(minTick,maxTick,7)

    ax.set_xlabel("Measured Pressure (mbar)")
    ax.set_ylabel("Lapse Rate Difference (K/m)")
    ax.set_zlabel("Calculated Height (m)")
 
    ax.view_init(20,40)

    plt.show()

def showPlot3dBarErrLapseRatePercentage():
    if smallScale == 1:
        scale = 100
    else:
        scale = 500
    lapseArr = np.linspace(LB*1.5,LB*0.5,45)
    pressArr = np.linspace(PB-scale,PB,251)

    df = pd.DataFrame(np.array(np.meshgrid(lapseArr, pressArr)).T.reshape(-1,2), columns=['lapse','pressure'])

    df["height"] = df.apply(lambda x: inverseBarometricFormulaLapse(x.pressure, x.lapse), axis=1)

    ax = plt.figure().add_subplot(projection='3d')

    ax.plot_trisurf(df.pressure, 100*(df.lapse-LB)/LB, percentDiffFromBarometric(df.pressure, 0, df.height), cmap="jet", linewidth=0, antialiased = False)

    ax.invert_yaxis()

    ax.set_xlabel("Measured Pressure (mbar)")
    ax.set_ylabel("Difference in Lapse Rate (%)")
    ax.set_zlabel("Difference in Calculated Height (%)")
 
    ax.view_init(20,60)

    plt.show()

def showPlotBarRefTemp():
    tempArr = np.linspace(TB-20,TB+20,99)
    pressArr = np.linspace(PB-500,PB,501)

    data = pd.DataFrame(np.array(np.meshgrid(tempArr, pressArr)).T.reshape(-1,2), columns=['temp','press'])

    data['height'] = data.apply(lambda x: inverseBarometricFormula(x.press,x.temp), axis=1)

    numLines = 3
    
    temps = tempArr[np.round(np.linspace(0,len(tempArr)-1,numLines)).astype(int)]
    for line in range(numLines):
        temp = temps[line]
        dataSlice = data.loc[data['temp']==temp]
        plt.plot(dataSlice.press,dataSlice.height, label = "Ref Temp: "+str(temp)+"K")
    
    plt.legend(loc = "upper left")
    plt.xlabel("Measured Pressure (mbar)")
    plt.ylabel("Calculated Height (m)")
    plt.grid()
    plt.gca().invert_xaxis()

    plt.show()

def showPlotBarErrRefTemp():
    tempArr = np.linspace(TB-20,TB+20,11)

    standardHeight = inverseBarometricFormula(900, TB)
    err = 100*(inverseBarometricFormula(900, tempArr) - standardHeight)/standardHeight
    plt.plot(100*(tempArr-TB)/(TB-273.15), err)
    
    plt.xlabel("Difference in Reference Temperature in °C (%)")
    plt.ylabel("Difference in Calculated Height (%)")
    #plt.gca().set_xticks(tempArr)
    plt.axhline(y=0, color="black", lw=0.5)
    #plt.axvline(x=TB, color="black", lw=0.5)
    plt.grid()

    plt.show()

def showPlotBarVHyp():
    if smallScale == 1:
        scale = 100
    else:
        scale = 500
    pressArr = np.linspace(PB-scale,PB,5010)

    df = pd.DataFrame(pressArr, columns=["pressure"])
    df["height_b"] = df.apply(lambda x: inverseBarometricFormula(x.pressure, TB), axis=1)
    df["lapse_temp"] = df.apply(lambda x: TB+(x.height_b*LB), axis=1)
    df["height_h_lapse"] = df.apply(lambda x: hypsometricFormula(x.pressure, TB, x.lapse_temp), axis=1)
    df["height_h_lapse_p10"] = df.apply(lambda x: hypsometricFormula(x.pressure, TB, x.lapse_temp+10), axis=1)
    df["height_h_lapse_m10"] = df.apply(lambda x: hypsometricFormula(x.pressure, TB, x.lapse_temp-10), axis=1)
    df["height__nolapse"] = df.apply(lambda x: hypsometricFormula(x.pressure, TB, TB), axis=1)

    plt.plot(df.pressure, df.height_b, label="Barometric Height")
    plt.plot(df.pressure, df.height_h_lapse, label="Hypsometric Height (At lapse temp)")
    #plt.plot(df.pressure, df.height_h_lapse_p10, label="Hypsometric Height (At lapse temp + 10C)")
    #plt.plot(df.pressure, df.height_h_lapse_m10, label="Hypsometric Height (At lapse temp - 10C)")
    #plt.plot(df.pressure, df.height_h_nolapse, label="Hypsometric Height (Without lapse)")
    #plt.plot(df.pressure, df.lapse_temp)

    plt.legend(loc = "upper left")
    plt.xlabel("Measured Pressure (mbar)")
    plt.ylabel("Calculated Height (m)")
    plt.grid()
    plt.gca().invert_xaxis()

    plt.show()

def showPlotBarLapseRate():
    pressArr = np.linspace(PB-500,PB,5010)

    df = pd.DataFrame(pressArr, columns=["pressure"])
    df["height_b"] = df.apply(lambda x: inverseBarometricFormula(x.pressure, TB), axis=1)
    df["lapse_temp"] = df.apply(lambda x: TB+(x.height_b*LB), axis=1)
    df["height_h_lapse"] = df.apply(lambda x: hypsometricFormula(x.pressure, TB, x.lapse_temp), axis=1)

    numLines = 3
    lapseArr = np.linspace(LB*1.5,LB*0.5, numLines)
    for line in range(numLines):
        lapse = lapseArr[line]
        plt.plot(df.pressure, df.apply(lambda x: inverseBarometricFormulaLapse(x.pressure, lapse), axis=1), label = "Lapse Rate: "+str(lapse)+" K/m")
    
    #plt.plot(df.pressure, df.height_h_lapse, label="Hypsometric Height (using standard lapse temp)")

    plt.legend(loc = "upper left")
    plt.xlabel("Measured Pressure (mbar)")
    plt.ylabel("Calculated Height (m)")
    plt.grid()
    plt.gca().invert_xaxis()

    plt.show()

def showPlotBarErrLapseRatePercentage():
    if smallScale == 1:
        scale = 100
    else:
        scale = 500
    pressArr = np.linspace(PB-scale,PB,5010)

    df = pd.DataFrame(pressArr, columns=["pressure"])
    df["height_b"] = df.apply(lambda x: inverseBarometricFormulaLapse(x.pressure, LB), axis=1)

    numLines = 5
    lapseArr = np.linspace(LB*1.5,LB*0.5, numLines)
    for line in range(numLines):
        lapse = lapseArr[line]
        plt.plot(df.pressure, 100*(df.apply(lambda x: inverseBarometricFormulaLapse(x.pressure, lapse), axis=1)-df.height_b)/df.height_b, label = "Difference in Lapse Rate: {:.0f}%".format(100*(lapse-LB)/LB))
    

    plt.legend(loc = "upper left")
    plt.xlabel("Measured Pressure (mbar)")
    plt.ylabel("Difference in Calculated Height (%)")
    plt.grid()
    plt.gca().invert_xaxis()

    plt.show()

plot3dBarErrRefTemp = 0
plotBarErrRefTemp = 0
plotBarRefTemp = 0
plotBarVHyp = 0
plot3dBarVHypTempDiff = 0
plotBarLapseRate = 0
plot3dBarErrLapseRateHeight = 0
plot3dBarErrLapseRatePercentage = 1
plotBarErrLapseRatePercentage = 0

smallScale = 1

if plot3dBarErrRefTemp == 1:
    showPlot3dBarErrRefTemp()
elif plotBarErrRefTemp == 1:
    showPlotBarErrRefTemp()
elif plotBarVHyp == 1:
    showPlotBarVHyp()
elif plotBarRefTemp == 1:
    showPlotBarRefTemp()
elif plot3dBarVHypTempDiff == 1:
    showPlot3dBarVHypTempDiff()
elif plotBarLapseRate == 1:
    showPlotBarLapseRate()
elif plot3dBarErrLapseRateHeight == 1:
    showPlot3dBarErrLapseRateHeight()
elif plot3dBarErrLapseRatePercentage == 1:
    showPlot3dBarErrLapseRatePercentage()
elif plotBarErrLapseRatePercentage == 1:
    showPlotBarErrLapseRatePercentage()
