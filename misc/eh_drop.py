import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_csv("eh_drop_250312_dark.csv")

df["normalDrop"] = (df["drop"] * df["battery"])/12

print("Average SirfRF:",np.mean(df[df["type"] == "SirfRF"]["normalDrop"]))
print("Average MiniRF:",np.mean(df[df["type"] == "MiniRF"]["normalDrop"]))
print()

print("Average 12mAh:",np.mean(df[df["battery"] == 12]["normalDrop"]))
print("Average 25mAh:",np.mean(df[df["battery"] == 25]["normalDrop"]))
print()

print("Average old solar:",np.mean(df[df["solar"] == "Old"]["normalDrop"]))
print("Average new solar:",np.mean(df[df["solar"] == "New"]["normalDrop"]))
print()

print("Average no mitigation:",np.mean(df[df["mitigation"] == False]["normalDrop"]))
print("Average w/ mitigation:",np.mean(df[df["mitigation"] == True]["normalDrop"]))
# print("Std Dev no mitigation:",np.std(df[df["mitigation"] == False]["normalDrop"]))
# print("Std Dev w/ mitigation:",np.std(df[df["mitigation"] == True]["normalDrop"]))
print()

print("Average old solar no mitigation:",np.mean(df[(df["mitigation"] == False) & (df["solar"] == "Old")]["normalDrop"]))
print("Average old solar w/ mitigation:",np.mean(df[(df["mitigation"] == True) & (df["solar"] == "Old")]["normalDrop"]))
print("Average new solar no mitigation:",np.mean(df[(df["mitigation"] == False) & (df["solar"] == "New")]["normalDrop"]))
print("Average new solar w/ mitigation:",np.mean(df[(df["mitigation"] == True) & (df["solar"] == "New")]["normalDrop"]))
print()

# plt.boxplot([df[df["mitigation"] == False]["normalDrop"], df[df["mitigation"] == True]["normalDrop"]])
# plt.xticks(ticks=[1,2],labels=["No","Yes"])
# plt.xlabel("FW mitigation")
# plt.ylabel("Normalised Battery Drop")
# plt.show()