import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

NUM_STEPS = 10

RGB_LOW = {"r":255,"g":255,"b":0}
RGB_HIGH = {"r":255,"g":0,"b":0}

TIME_WINDOW = np.timedelta64(1,"m")

vedbaDF = pd.read_pickle("./z kml vedba/Obs230625_083832_BS50400_Tag50385_VeDBA.pkl")
maxVedba = vedbaDF["avgVeDBA"].max()

vedbaSteps = maxVedba/NUM_STEPS

ET.register_namespace("","http://earth.google.com/kml/2.1)")
tree = ET.parse("./z kml vedba/Obs230625_083832_Tag50385.kml")
root = tree.getroot()

styleMapXMLTemplate = """<StyleMap id="msn_{colStr}-pushpin">
		<Pair>
			<key>normal</key>
			<styleUrl>#sn_{colStr}-pushpin</styleUrl>
		</Pair>
		<Pair>
			<key>highlight</key>
			<styleUrl>#sh_{colStr}-pushpin</styleUrl>
		</Pair>
	</StyleMap>"""

styleNormalXMLTemplate="""<Style id="sn_{colStr}-pushpin">
		<IconStyle>
            <color>{colCode}</color>
			<scale>0.5</scale>
			<Icon>
				<href>https://maps.google.com/mapfiles/kml/pal2/icon18.png</href>
			</Icon>
			<hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>
		</IconStyle>
		<LineStyle>
			<color>ff0000ff</color>
		</LineStyle>
	</Style>"""

styleHighlightedXMLTemplate="""<Style id="sh_{colStr}-pushpin">
		<IconStyle>
            <color>{colCode}</color>
			<scale>0.7</scale>
			<Icon>
				<href>https://maps.google.com/mapfiles/kml/pal2/icon18.png</href>
			</Icon>
			<hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>
		</IconStyle>
		<LineStyle>
			<color>ff0000ff</color>
		</LineStyle>
	</Style>"""

styleURLTemplate = "#msn_{colStr}-pushpin"

for i in range(NUM_STEPS+1):
    red = int((i/NUM_STEPS) * RGB_HIGH["r"] + ((NUM_STEPS-i)/NUM_STEPS) * RGB_LOW["r"])
    green = int((i/NUM_STEPS) * RGB_HIGH["g"] + ((NUM_STEPS-i)/NUM_STEPS) * RGB_LOW["g"])
    blue = int((i/NUM_STEPS) * RGB_HIGH["b"] + ((NUM_STEPS-i)/NUM_STEPS) * RGB_LOW["b"])
    colHex = "ff{b:02x}{g:02x}{r:02x}".format(b=blue,g=green,r=red)
    root[0].insert(1,ET.fromstring(styleHighlightedXMLTemplate.format(colStr=str(i),colCode = colHex)))
    root[0].insert(1,ET.fromstring(styleNormalXMLTemplate.format(colStr=str(i),colCode = colHex)))
    root[0].insert(1,ET.fromstring(styleMapXMLTemplate.format(colStr=str(i))))

times = []

prevTimestamp = np.datetime64(0,"Y")

count = 1
for child in root[0]:
    if "Placemark" in child.tag and "TimeStamp" in child[0].tag:
        timestamp = np.datetime64(child[0][0].text[:-1])
        #timeMin = timestamp - TIME_WINDOW
        #timeMax = timestamp + TIME_WINDOW
        #localMaxVedba = vedbaDF[(vedbaDF["datetime"] >= timeMin) & (vedbaDF["datetime"] < timeMax)]["avgVeDBA"].max()
        localMaxVedba = vedbaDF[(vedbaDF["datetime"] > prevTimestamp) & (vedbaDF["datetime"] <= timestamp)]["avgVeDBA"].max()
        prevTimestamp = timestamp
        step = round(localMaxVedba/vedbaSteps)
        child[1].text = styleURLTemplate.format(colStr=str(step))
        elem = ET.Element("name")
        elem.text = str(count)
        count += 1
        child.append(elem)
        times.append(timestamp)

with open("./z kml vedba/vedba_colour_coded.kml","wb") as f:
    tree.write(f, xml_declaration=True, encoding="UTF-8")

# plt.xlabel("Date Time")
# plt.ylabel("VeDBA (g)")
# plt.plot(vedbaDF.datetime, vedbaDF.avgVeDBA)

# plt.vlines(times, ymax=0.8, ymin=0.2, colors="red",linestyles="dashed")
# for i in range(len(times)):
#     plt.text(times[i],0.8,str(i+1)).set_clip_on(True)

# plt.show()