import os
import requests
import shutil
from pathlib import Path
import gzip
import time
from datetime import datetime, timezone, timedelta
if "LOCAL_TEST" not in os.environ:
    import boto3
    from botocore.exceptions import ClientError

session = None

# overriding requests.Session.rebuild_auth to mantain headers when redirected
class SessionWithHeaderRedirection(requests.Session):

    AUTH_HOST = 'urs.earthdata.nasa.gov'

    def __init__(self, username, password):
        super().__init__()
        self.auth = (username, password)

   # Overrides from the library to keep headers when redirected to or from
   # the NASA auth host.
    def rebuild_auth(self, prepared_request, response):
        headers = prepared_request.headers
        url = prepared_request.url

        if 'Authorization' in headers:
            original_parsed = requests.utils.urlparse(response.request.url)
            redirect_parsed = requests.utils.urlparse(url)

            if (original_parsed.hostname != redirect_parsed.hostname) and redirect_parsed.hostname != self.AUTH_HOST and original_parsed.hostname != self.AUTH_HOST:
                del headers['Authorization']


def parse_RINEX_V3(rinexV3FileName):
    ret = {
        "error" : None,
        "complete" : False,
        "ephemerides" : {}
    }
    with gzip.open(rinexV3FileName, "rt") as file:
        line = file.readline()
        while not "END OF HEADER" in line:
            if "PATHTRACK COMPLETE" in line:
                ret["complete"] = True

            line = file.readline()
            if line == "":
                ret["error"] = f"ERROR End of header not found in {rinexV3FileName}"
                return ret
        
        ret["ephemerides"]["G"] = {}

        line = file.readline()
        while line != "":
            if line.startswith("G"):
                prn = int(line[1:3])
                timestamp = datetime.strptime(line[4:23],"%Y %m %d %H %M %S")
                for _ in range (6):
                    line = file.readline()
                healthy = line[26:28] == "00"
                ephemeride = {"time": timestamp,
                              "healthy": healthy}
                if prn in ret["ephemerides"]["G"]:
                    ret["ephemerides"]["G"][prn].append(ephemeride)
                else:
                    ret["ephemerides"]["G"][prn] = [ephemeride]
            line = file.readline()

        return ret


def upload_to_s3(localFileName : str, s3fileName : str):
    print(f"Uploading {localFileName} to {s3fileName}")

    #if running locally copy file to local folder instead of uploading
    if "LOCAL_TEST" in os.environ:
        uploadFileName = os.environ["LOCAL_TEST"]+s3fileName
        Path(uploadFileName).parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(localFileName, uploadFileName)

    else:
        s3 = boto3.resource("s3")
        with open(localFileName, "rb") as f:
            fileBytes = f.read()
            s3.Bucket(os.environ["S3_BUCKET"]).put_object(Key=s3fileName, Body=fileBytes)


def download_from_s3(s3fileName : str, localFileName : str) -> bool:
    print(f"Attempting download of {s3fileName} to {localFileName}")

    Path(localFileName).parent.mkdir(exist_ok=True, parents=True)

    #if running locally copy file from local folder instead of downloading
    if "LOCAL_TEST" in os.environ:
        downloadFileName = os.environ["LOCAL_TEST"]+s3fileName

        if not os.path.isfile(downloadFileName):
            print("File not found")
            return False
        
        shutil.copyfile(downloadFileName, localFileName)
        print("Download successful")
        return True
    
    else:
        s3 = boto3.client("s3")

        try:
            s3.download_file(os.environ["S3_BUCKET"], s3fileName, localFileName)
            print("Download successful")
            return True
        
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                print("File not found")
                return False
            else:
                raise


def download_nasa_file(fileName : str, addr : str, dir : str, numRetries : int) -> str:
    print(f"Attempting to download nasa file {fileName} from {addr}")

    Path(dir).mkdir(exist_ok=True, parents=True)

    if download_nasa_file.session == None:
        download_nasa_file.session = SessionWithHeaderRedirection(os.environ["EARTHDATA_USERNAME"],os.environ["EARTHDATA_PASSWORD"])

    r = download_nasa_file.session.get(addr+fileName)

    if r.status_code == 200:
        print("Download successful")
        with open(dir+fileName, "wb") as f:
            for byte in r.iter_content():
                f.write(byte)
        return fileName
    else:
        if numRetries == 0:
            print(f"Download failed ({r.status_code}: {r.reason}) no more retries")
            return None
        else:
            print(f"Download failed ({r.status_code}: {r.reason}) retrying in 5 seconds")
            time.sleep(5)
            return download_nasa_file(fileName, addr, dir, numRetries-1)
download_nasa_file.session = None


def download_daily_V3(year : int, day : int, dir : str, numRetries : int) -> str:
    return download_nasa_file(f"BRDC00IGS_R_{year}{day:03d}0000_01D_MN.rnx.gz",f"https://cddis.nasa.gov/archive/gnss/data/daily/{year}/brdc/", dir, numRetries) 


def download_hourly_V2(year : int, day : int, dir : str, numRetries : int) -> str:
    return download_nasa_file(f"hour{day:03d}0.{(year % 100):02d}n.gz",f"https://cddis.nasa.gov/archive/gnss/data/hourly/{year}/{day:03d}/", dir, numRetries)


def compare_ephemerides(old : dict[str, dict[int, list[dict]]], new : dict[str, dict[int, list[dict]]]):
    print("Comparing old and new ephemeris")
    missing = 0

    for oldGPSPRN, oldGPSEphems in old["G"].items():

        if oldGPSPRN not in new["G"]:
            missing += len(oldGPSEphems)
            continue

        for oldGPSEphem in oldGPSEphems:
            existing = False
            for newGPSEphem in new["G"][oldGPSPRN]:
                if abs((oldGPSEphem["time"] - newGPSEphem["time"]).total_seconds()) < 300:
                    existing = True
                    break
            if not existing:
                missing += 1

    print(f"{missing} old ephemerides non existant in new file")
    if missing > 15:
        print("WARNING more missing ephemerides than expected in new file")


def validate_ephemeris(ephemerides : dict[str, dict[int, list[dict]]]) -> bool:
    print("Validating list for completeness")
    prnCount = [0]*32
    prnUnhealthy = [0]*32
    for gpsPRN, ephems in ephemerides["G"].items():
        unhealthy = 0
        for ephem in ephems:
            if not ephem["healthy"]:
                unhealthy += 1
        prnUnhealthy[gpsPRN - 1] = unhealthy
        prnCount[gpsPRN - 1] = len(ephems) - unhealthy
    
    print(f"File contains {sum(prnCount)} healthy ephemerides")
    if(sum(prnCount) < 400):
        print("WARNING less healthy ephemerides in file than usual, typically over 400")

    print(f"File contains {sum(prnUnhealthy)} unhealthy ephemerides")
    if(sum(prnUnhealthy) > 20):
        print("WARNING over 20 unhealthy ephemerides in file")

    if sum(1 for count in prnCount if count >= 11) >= 24:
        print("List is complete")
        return True
    
    print("List is incomplete")
    return False


def mark_file_complete(fileName : str):
    print(f"Marking file {fileName} as complete")
    tempFileName = fileName+"_temp"
    os.rename(fileName, tempFileName)
    with gzip.open(tempFileName, "rt") as original, gzip.open(fileName, "wb") as new:
        line = original.readline()
        while line != "":
            if "END OF HEADER" in line:
                new.write((f"PATHTRACK COMPLETE {datetime.now(timezone.utc):%Y/%m/%d-%H:%M:%S}".ljust(60)+"COMMENT\n").encode("utf-8"))
            new.write(line.encode("utf-8"))
            line = original.readline()

    os.remove(tempFileName)


def update(date : datetime, validate : bool):
    ret = {"error": None,
           "complete": False}
    
    dateTuple = date.timetuple()
    year = dateTuple.tm_year
    day = dateTuple.tm_yday

    #download the nasa V3 file for the day
    fileName = download_daily_V3(year, day, os.environ["TEMP_DIR"]+"nasa/", 3)

    #if download failed return
    if fileName == None:
        ret["error"] = f"ERROR Failed to download daily V3 file for {year}/{day}"
        return ret

    #upload copy of nasa file for our records
    upload_to_s3(os.environ["TEMP_DIR"]+"nasa/"+fileName, f"{year}/{day:03d}/{datetime.now(timezone.utc):%j_%H_%M}_{fileName}")

    #parse nasa file
    nasaRINEX = parse_RINEX_V3(os.environ["TEMP_DIR"]+"nasa/"+fileName)

    #return early if error in parsing nasa file
    if nasaRINEX["error"] != None:
        ret["error"] = nasaRINEX["error"]
        return ret

    #download our copy of the file for the day
    exists = download_from_s3(f"{year}/{fileName}", os.environ["TEMP_DIR"]+"ptrack/"+fileName)

    if exists:
        #parse our file if it exists
        ptrackRINEX = parse_RINEX_V3(os.environ["TEMP_DIR"]+"ptrack/"+fileName)

        #return error if error in parsing our file
        if ptrackRINEX["error"] != None:
            ret["error"] = ptrackRINEX["error"]
            return ret
        
        #if validating and our file is complete return early
        if validate and ptrackRINEX["complete"]:
            ret["complete"] = True
            print("File marked as complete")
            return ret
        
        #compare our file (old) and the nasa file (new)
        compare_ephemerides(ptrackRINEX["ephemerides"], nasaRINEX["ephemerides"])

    #if validating check if nasa file is complete and mark before uploading
    if validate and validate_ephemeris(nasaRINEX["ephemerides"]):
        mark_file_complete(os.environ["TEMP_DIR"]+"nasa/"+fileName)

    #upload nasa file as our newest
    upload_to_s3(os.environ["TEMP_DIR"]+"nasa/"+fileName, f"{year}/{fileName}")

    return ret


def mirror(date : datetime):
    ret = {"error" : None}

    dateTuple = date.timetuple()
    year = dateTuple.tm_year
    day = dateTuple.tm_yday

    #download hourly V2 file
    fileName = download_hourly_V2(year, day, os.environ["TEMP_DIR"]+"nasa/", 3)

    #if download failed return
    if fileName == None:
        ret["error"] = f"ERROR Failed to download hourly V2 file for {year}/{day}"
        return ret
    
    #upload hourly file with daily naming
    upload_to_s3(os.environ["TEMP_DIR"]+"nasa/"+fileName, f"{year}/brdc{day:03d}0.{(year % 100):02d}n.gz")

    return ret

def clear_logs_before(date : datetime):
    s3 = boto3.client("s3")
    found = True
    while found:
        dateTuple = date.timetuple()
        folder = f"{dateTuple.tm_year}/{dateTuple.tm_yday:03d}/"
        resp = s3.list_objects_v2(Bucket=os.environ["S3_BUCKET"], Prefix=folder)
        found = 'Contents' in resp
        if found:
            print(f"Deleting logs {folder}")
            files = []
            for f in resp['Contents']:
                files.append({"Key": f["Key"]})
            s3.delete_objects(Bucket=os.environ["S3_BUCKET"], Delete={"Objects": files})
            date -= timedelta(days=1)
    return


def lambda_handler(event, context):
    today = datetime.now(timezone.utc)
    
    print("*"*150)
    print("Mirroring todays hourly file")
    print("*"*150)

    if today.hour == 0:
        print("Skipping mirror of todays hourly file as it is not yet 1AM and file will not be uploaded yet")
    else:
        ret = mirror(today)

        if ret["error"] != None:
            print(ret["error"])
            print("Ending execution due to error")
            return

    prevDayComplete = False
    for delta in range(1,7):
        if delta == 1 and (today.hour == 0 or today.hour == 1):
            print("Skipping download of yesterdays file as it won't be uploaded yet")
            continue

        day = today - timedelta(days=delta)

        #validate files that are over a day old
        validate = delta > 1
        print("*"*150)
        print(f"Updating{' and validating' if validate else ''} for today -{delta} days ({day:%Y/%j})")
        print("*"*150)

        ret = update(day, validate)

        if ret["error"] != None:
            print(ret["error"])
            print("Ending execution due to error")
            return
        
        if ret["complete"] and prevDayComplete:
            print("Ready to end execution as consecutive complete files found")
            clear_logs_before(today - timedelta(days=30))
            print("Ending execution now old logs have been cleared")
            return

        if not ret["complete"] and prevDayComplete:
            print(f"ERROR file for {day:%Y/%j} is incomplete but file for day after is complete")
            print("Ending execution due to error")
            return
        prevDayComplete = ret["complete"]

    print(f"ERROR searched backwards to maximum and no consecutive complete files found")
    print("Ending execution due to error")
    return
