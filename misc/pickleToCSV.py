import pandas as pd

FILE_NAME = "shag_ImmersionAccel.pkl"

df = pd.read_pickle(FILE_NAME)

df.to_csv(FILE_NAME[:-4]+".csv",index=False)