import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
from datetime import datetime

accelDataFile = open("Obs030124_104345_Tag48888Accel.txt")
accelDataFile2 = open("Obs030124_104938_Tag58877Accel.txt")

text = accelDataFile.read()
text2 = accelDataFile2.read()

lines = [line.split(" ") for line in text.split("\n")[5:-1]]
lines2 = [line.split(" ") for line in text2.split("\n")[5:-1]]

#[datetime.strptime(' '.join(line[0:6]),"%Y %m %d %H %M %S.%f")]
# for line in lines:
#     line[0:6] = [float(''.join(line[0:6]))]

# for line in lines2:
#     line[0:6] = [float(''.join(line[0:6]))]

length = len(lines)
length2 = len(lines2)
width = 1000

fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.25)

t = [i for i in range(0,length)]
s = [float(line[6]) for line in lines]
t2 = [i for i in range(0,length2)]
s2 = [float(line[6]) for line in lines2]
plt.plot(t,s, label="tag48888")
plt.plot(t2,s2, label="tag58877")
plt.axis([0, width, -1.1, 1.1])

axcolor = 'lightgoldenrodyellow'
axpos = plt.axes([0.2, 0.1, 0.65, 0.03], facecolor=axcolor)
axposB = plt.axes([0.05, 0.1, 0.05, 0.03])
axposF = plt.axes([0.93, 0.1, 0.05, 0.03])

spos = Slider(axpos, 'Pos', 0, max(length,length2)-width)

forwardButton = Button(axposF, ">", color='w', hovercolor='b')
backwardButton = Button(axposB, "<", color='w', hovercolor='b')

def update(val):
    pos = spos.val
    ax.axis([pos,pos+width,-1.1,1.1])
    fig.canvas.draw_idle()

def forward(vl):
    pos = spos.val
    spos.set_val(pos+100)
def backward(vl):
    pos = spos.val
    spos.set_val(pos-100)

spos.on_changed(update)
forwardButton.on_clicked(forward)
backwardButton.on_clicked(backward)



plt.show()