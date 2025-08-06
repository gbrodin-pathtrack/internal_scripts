import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

FIXED_STEPS = True

LABLE_NUMBERS = False

#VEDBA_FILE = "./z kml vedba/Obs040825_112743_Tag22074_VeDBA.pkl"
VEDBA_FILE = "./z kml vedba/Obs230625_083832_BS50400_Tag50385_VeDBA.pkl"
#KML_FILE = "./z kml vedba/Obs040825_112743_Tag22074.kml"
KML_FILE = "./z kml vedba/Obs230625_083832_Tag50385.kml"

NUM_STEPS = 10
RGB_LOW = {"r":255,"g":255,"b":0}
RGB_HIGH = {"r":255,"g":0,"b":0}

STEPS = [{"r":0,"g":255,"b":0,"min":0},
		{"r":255,"g":255,"b":0,"min":0.5},
		{"r":255,"g":128,"b":0,"min":1},
		{"r":255,"g":0,"b":0,"min":1.5}]


vedbaDF = pd.read_pickle(VEDBA_FILE)
maxVedba = vedbaDF["avgVeDBA"].max()*0.90

vedbaSteps = maxVedba/NUM_STEPS

ET.register_namespace("","http://earth.google.com/kml/2.1)")
tree = ET.parse(KML_FILE)
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

if FIXED_STEPS:
	for i in range(len(STEPS)):
		colHex = "ff{b:02x}{g:02x}{r:02x}".format(b=STEPS[i]["b"],g=STEPS[i]["g"],r=STEPS[i]["r"])
		root[0].insert(1,ET.fromstring(styleHighlightedXMLTemplate.format(colStr=str(i),colCode = colHex)))
		root[0].insert(1,ET.fromstring(styleNormalXMLTemplate.format(colStr=str(i),colCode = colHex)))
		root[0].insert(1,ET.fromstring(styleMapXMLTemplate.format(colStr=str(i))))
else:
	for i in range(NUM_STEPS+1):
		red = int((i/NUM_STEPS) * RGB_HIGH["r"] + ((NUM_STEPS-i)/NUM_STEPS) * RGB_LOW["r"])
		green = int((i/NUM_STEPS) * RGB_HIGH["g"] + ((NUM_STEPS-i)/NUM_STEPS) * RGB_LOW["g"])
		blue = int((i/NUM_STEPS) * RGB_HIGH["b"] + ((NUM_STEPS-i)/NUM_STEPS) * RGB_LOW["b"])
		colHex = "ff{b:02x}{g:02x}{r:02x}".format(b=blue,g=green,r=red)
		root[0].insert(1,ET.fromstring(styleHighlightedXMLTemplate.format(colStr=str(i),colCode = colHex)))
		root[0].insert(1,ET.fromstring(styleNormalXMLTemplate.format(colStr=str(i),colCode = colHex)))
		root[0].insert(1,ET.fromstring(styleMapXMLTemplate.format(colStr=str(i))))

for child in root[0]:
	if "Placemark" in child.tag and "TimeStamp" in child[0].tag:
		prevTimestamp = np.datetime64(child[0][0].text[:-1])
		break

midpoints = [prevTimestamp]
skip = True
for child in root[0]:
	if "Placemark" in child.tag and "TimeStamp" in child[0].tag:
		if skip:
			skip = False
			continue
		currTimestamp = np.datetime64(child[0][0].text[:-1])
		midpoints.append(prevTimestamp + ((currTimestamp-prevTimestamp)/2))
		prevTimestamp = currTimestamp

midpoints.append(prevTimestamp)

times = []

count = 1
for child in root[0]:
	if "Placemark" in child.tag and "TimeStamp" in child[0].tag:
		timestamp = np.datetime64(child[0][0].text[:-1])
		localMaxVedba = vedbaDF[(vedbaDF["datetime"] > midpoints[count-1]) & (vedbaDF["datetime"] <= midpoints[count])]["avgVeDBA"].max()
		if FIXED_STEPS:
			step = 0
			for i in range(1,len(STEPS)):
				if localMaxVedba<STEPS[i]["min"]:
					break
				step += 1
		else:
			step = round(localMaxVedba/vedbaSteps)
			if step > NUM_STEPS:
				step = NUM_STEPS

		child[1].text = styleURLTemplate.format(colStr=str(step))
		elem = ET.Element("name")
		elem.text = str(count)
		count += 1
		if LABLE_NUMBERS:
			child.append(elem)
		times.append(timestamp)

with open(KML_FILE[:-4]+"_vedba_coloured"+("_nums"if LABLE_NUMBERS else "")+".kml","wb") as f:
	tree.write(f, xml_declaration=True, encoding="UTF-8")

# plt.xlabel("Date Time")
# plt.ylabel("VeDBA (g)")
# plt.plot(vedbaDF.datetime, vedbaDF.avgVeDBA)

# plt.vlines(times, ymax=0.8, ymin=0.2, colors="red",linestyles="dashed")
# for i in range(len(times)):
#     plt.text(times[i],0.8,str(i+1),{'weight':'bold', 'size':14}).set_clip_on(True)

# plt.show()