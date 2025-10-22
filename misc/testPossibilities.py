import itertools

VARS = {
#"MCU":["ATX 32E5","ATX 128A4U"],
#"Flash":["128Mbit","4Gbit"],
#"Accel Rate":["1Hz","12.5Hz","25Hz","50Hz"],
#"Accel Mode":["Scalar","Vector","VeDBA"],
#"Pressure Sensor":["Mini Alt","Mini Com","Mini Depth","Large Com"],
#"Pressure Storage":["Yes","No"],
#"Pressure Interval":["1s","2s","4s","8s"],
#"Immersion Interval":["1s","10s","1 min","4 min"],
#"Immersion Shorted":["Yes","No"],
"Battery Size (mAh)":["12","40","90"],
#"GPS Conditions":["1-2s fixes", "5-8s fixes", "20s timeouts"],
"UHF Pages":["1", "10", "100"],
"UHF Mode":["Slow","Fast"]
}

print(",".join(VARS.keys()))
for row in itertools.product(*(VARS.values())):
    print(",".join(row))