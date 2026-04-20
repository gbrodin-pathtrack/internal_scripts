import os

os.environ["LOCAL_TEST"] = "./RINEX/V3_TESTING/S3/"
os.environ["EARTHDATA_USERNAME"] = "PTrack2020"
os.environ["EARTHDATA_PASSWORD"] = "Nano21Fix"
os.environ["S3_BUCKET"] = "ephemeris-414556474136-eu-north-1-an"
os.environ["TEMP_DIR"] = "./RINEX/V3_TESTING/"

import lambda_function

lambda_function.lambda_handler(None, None)