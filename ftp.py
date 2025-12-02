import ftplib
import gzip
from datetime import datetime, timedelta, timezone, time
import traceback
from pathlib import Path

pathtrackUser = "TEST01@pathtrack.co.uk"
pathtrackPass = "DxJkvat6H3"
pathtrackHost = "ftp.pathtrack.co.uk"

nasaUser = "anonymous"
nasaPass = "g.brodin@pathtrack.co.uk"
nasaHost = "gdc.cddis.eosdis.nasa.gov"
#for lambda change this to "/tmp/"
localRootAddress = "./RINEX/"

#function to read RINEX V2 file <filename> and parse it to check for any formatting errors
#returns bool: error, list: header, list: ephems
#error is True if there is an error in parsing, if there is header is a string with an error message and ephems is 0, noramlly will be False
#header is a list of lines that make up the RINEX V2 header
#ephems is a list of dicts that each represent an ephemeris, the dict contains: 
#'sat': the satalite number 1-32, 'time': a time tag of when the ephemeris is valid from, 'text': all the lines that represent that ephemeris (sat + timetag + data)
def parseRINEX(fileName):
    lines = []
    try:
        print("Opening local file for reading: "+fileName+" ...")
        with gzip.open(localRootAddress+fileName, 'rt') as f:
            print("Successful\n"+"Reading all lines from file ...")
            lines = f.readlines()
    except FileNotFoundError:
        return True,traceback.format_exc()+"\n"+"FileNotFound error when opening file to read: "+fileName,0
    except OSError:
        return True,traceback.format_exc()+"OS error when opening file to read: "+fileName,0
    except EOFError:
        return True,traceback.format_exc()+"EOF error when opening file to read: "+fileName,0
    
    print("Successful\n"+"Parsing lines for header and ephemerides ...")
    if len(lines) == 0:
        return True,"No content in RINEX file "+fileName,0

    if "2              NAVIGATION DATA                         RINEX VERSION / TYPE" not in lines[0]:
        return True,"Invalid RINEX header in file "+fileName+", file doesn't start with 2 NAVIGATION DATA RINEX VERSION / TYPE",0
    
    requirements = [[False,"END OF HEADER"],[False,"ION ALPHA"],[False,"ION BETA"],[False,"LEAP SECONDS"]]
    header = []
    ephemStart = 0
    for index, line in enumerate(lines):
        header.append(line)
        for requirement in requirements:
            if(requirement[1] in line):
                requirement[0] = True
        if("END OF HEADER" in line):
            ephemStart = index + 1
            break
    
    for requirement in requirements:
        if not requirement[0]:
            return True,"Invalid RINEX header in file "+fileName+", no "+requirement[1]+" line found",0

    lines = lines[ephemStart:]
    if len(lines)%8 != 0:
        return True,"Wrong number of lines in data section of file "+fileName+" should be multiple of 8",0

    ephems = []
    for index, line in enumerate(lines[::8]):
        index*=8
        if len(line) != 80:
            return True, "Incorrect number of characters in file "+fileName+" line "+str(ephemStart+index+1)+"\n"+line,0

        try:
            timetag = datetime.strptime(line[3:20], "%y %m %d %H %M %S")
        except ValueError:
            return True,traceback.format_exc()+"\n"+"Invalid timetag in file "+fileName+" line "+str(ephemStart+index+1)+"\n"+line+" "*3+"^"*19,0

        ephem = {'sat':line[0:2],'time':timetag, 'text':"".join(lines[index:index+8])}

        if not ephem['sat'].strip().isnumeric() or int(ephem['sat'].strip()) > 32 or int(ephem['sat'].strip()) < 1:
            return True,"Invalid sat code in file "+fileName+" line "+str(ephemStart+index+1)+"\n"+line+"^"*2,0
        ephem['sat'] = int(ephem['sat'].strip())
        
        if len(ephem['text']) != 640:
            return True, "Incorrect number of characters in file "+fileName+" block starting on line "+str(ephemStart+index+1)+"\n"+ephem['text'],0

        if ephem['text'][505:507] == '00':
            ephem['healthy'] = True
        else:
            ephem['healthy'] = False
        
        ephems.append(ephem)
    print("Successful")
    return False, header, ephems


#function to download a file over FTP from <host> as user <user> with password <password>
#function goes to directory <serverFilePath> and downloads <serverFileName> into local file <localFileName>
#returns bool: error, string: localFileName
#error is True if there is any error in the FTP connection or file writing, if there is an error localFileName is an error string, normally will be False
#localFileName is the file name the downloaded file was written to
def getFTPFile(localFileName, serverFilePath, serverFileName, host, user, password, retries=0):
    ftp = None
    try:
        print("Opening FTP connection to: "+host+" as user: "+user+" with pass: "+password+" ...")
        ftp = ftplib.FTP_TLS(host, user, password)
        print("Successful\n"+"Setting up secure data connection ...")
        ftp.prot_p()
        print("Successful\n"+"Changing directory to: "+serverFilePath+" ...")
        ftp.cwd(serverFilePath)
        print("Successful\n"+"Opening local file to write: "+localFileName+" ...")
        with open(localRootAddress+localFileName,'wb') as fp:
            print("Successful\n"+"Retriving server file: "+serverFileName+" ...")
            ftp.retrbinary('RETR '+serverFileName,fp.write)
        print("Successful\n"+"Closing FTP connection")
        ftp.quit()
    except ftplib.all_errors as e:
        print("FTP failed\n"+"Closing FTP connection")
        if ftp is not None: 
            ftp.quit()
        if isinstance(e, ftplib.error_temp) and retries < 2:
            print("Retrying ...")
            return getFTPFile(localFileName, serverFilePath, serverFileName, host, user, password, retries=retries+1)
        return True, traceback.format_exc()+"\n"+str(e)+"\n"+"Attempted to connect to: "+host+" as user: "+user+" with pass: "+password\
                           +"\n"+"Attempted to get: "+serverFilePath+"/"+serverFileName
    except FileNotFoundError:
        return True,traceback.format_exc()+"\n"+"FileNotFound error when opening file to write: "+localFileName
    except OSError:
        return True,traceback.format_exc()+"\n"+"OS error when opening file to write: "+localFileName
    return False, localFileName    


#function to upload a file over FTP to <host> as user <user> with password <password>
#function goes to directory <serverFilePath> and uploads local file <localFileName> into <serverFileName>
#returns bool: error, string: localFileName
#error is True if there is any error in the FTP connection or file reading, if there is an error localFileName is an error string, normally will be False
#localFileName is the file name that was uploaded
def writeFTPFile(localFileName, serverFilePath, serverFileName, host, user, password, retries=0):
    ftp = None
    try:
        print("Opening FTP connection to: "+host+" as user: "+user+" with pass: "+password+" ...")
        ftp = ftplib.FTP_TLS(host, user, password)
        print("Successful\n"+"Setting up secure data connection ...")
        ftp.prot_p()
        print("Successful\n"+"Changing directory to: "+serverFilePath+" ...")
        ftp.cwd(serverFilePath)
        print("Successful\n"+"Opening local file to read: "+localFileName+" ...")
        with open(localRootAddress+localFileName,'rb') as fp:
            print("Successful\n"+"Writing to server file: "+serverFileName+" ...")
            ftp.storbinary('STOR '+serverFileName,fp)
        print("Successful\n"+"Closing FTP connection")
        ftp.quit()
    except ftplib.all_errors as e:
        print("FTP failed\n"+"Closing FTP connection")
        if ftp is not None: 
            ftp.quit()
        if isinstance(e, ftplib.error_temp) and retries < 2:
            print("Retrying ...")
            return getFTPFile(localFileName, serverFilePath, serverFileName, host, user, password, retries=retries+1)
        return True, traceback.format_exc()+"\n"+str(e)+"\n"+"Attempted to connect to: "+host+" as user: "+user+" with pass: "+password\
                           +"\n"+"Attempted to get: "+serverFilePath+"/"+serverFileName
    except FileNotFoundError:
        return True,traceback.format_exc()+"\n"+"FileNotFound error when opening file to write: "+localFileName
    except OSError:
        return True,traceback.format_exc()+"\n"+"OS error when opening file to write: "+localFileName
    return False, localFileName   


#function to get the daily file from NASA FTP server from date <date>
#calls getFTPFile and returns the result
def getNASADailyFile(date: datetime):
    dailyFileName, dayOfYear, year = getDailyFileName(date)
    dailyFilePath = "./gnss/data/daily/"+year+"/brdc"
    #dailyFileName = "brdc0080."+year[-2:]+"n.gz"

    print("Getting NASA file: "+dailyFileName+" ...")
    return getFTPFile("nasa/"+dailyFileName, dailyFilePath, dailyFileName, nasaHost, nasaUser, nasaPass)


#function to get the hourly file from NASA FTP server from date <date>
#calls getFTPFile and returns the result
def getNASAHourlyFile(date: datetime):
    hourlyFileName, dayOfYear, year = getHourlyFileName(date)
    dailyFileName, dayOfYear, year = getDailyFileName(date)
    hourlyFilePath = "./gnss/data/hourly/"+year+"/"+dayOfYear

    print("Getting NASA file: "+hourlyFileName+" ...")
    return getFTPFile("nasa/"+dailyFileName, hourlyFilePath, hourlyFileName, nasaHost, nasaUser, nasaPass)


#function to get create a directory on pathtrack FTP server, goes to directory <folderPath> and creates a directory <folderName>
#returns bool:error, string:folderName
#error is True if there is an FTP error, if there is an error folderName is an error string, normally will be False
#folderName is the name of the folder created on the Pathtrack FTP server
def createPathtrackDirectory(folderPath, folderName):
    ftp = None
    try:
        print("Opening FTP connection to: "+pathtrackHost+" as user: "+pathtrackUser+" with pass: "+pathtrackPass+" ...")
        ftp = ftplib.FTP_TLS(pathtrackHost, pathtrackUser, pathtrackPass)
        print("Successful\n"+"Setting up secure data connection ...")
        ftp.prot_p()
        print("Successful\n"+"Changing directory to: "+folderPath+" ...")
        ftp.cwd(folderPath)
        print("Successful\n"+"Creating new directory: "+folderName+" ...")
        ftp.mkd(folderName)
        print("Successful\n"+"Closing FTP connection")
        ftp.quit()
    except ftplib.all_errors as e:
        print("FTP failed\n"+"Closing FTP connection")
        if ftp is not None:
            ftp.quit()
        return True, traceback.format_exc()+"\n"+str(e)+"\n"+"Attempted to connect to: "+pathtrackHost+" as user: "+pathtrackUser+" with pass: "+pathtrackPass\
                           +"\n"+"Attempted to create folder: "+folderName+" in folder: "+folderPath
    return False, folderName


#function to get the daily file from Pathtrack FTP server from date <date>
#calls getFTPFile and returns the result, if there is an error caused by directory not existing, directory is created before return
def getPathtrackDailyFile(date: datetime):
    dailyFileName, dayOfYear, year = getDailyFileName(date)
    dailyFilePath = "./"+year
    #dailyFileName = "brdc0080."+year[-2:]+"n.gz"

    print("Getting pathtrack file: "+dailyFileName+" ...")
    ftpError, fileName = getFTPFile("ptrack/"+dailyFileName, dailyFilePath, dailyFileName, pathtrackHost, pathtrackUser, pathtrackPass)
    if ftpError and "550 Can't change directory to" in fileName:
        print("Creating new pathtrack folder: ./"+year+" ...")
        ftpError, folderName = createPathtrackDirectory("./",year)
        if ftpError:
            return True, fileName+"\n"+folderName
        return True, fileName+"550 Can't open No such file" #directory fixed, added error code to act as if only file doesn't exist
    return ftpError, fileName


#function to upload local file <localFileName> to Pathtrack FTP server in <year> directory with server file name <serverFileName>
#calls writeFTPFile and returns the result, if there is an error caused by directory not existing, directory is created and writeFTPFile is retried
def uploadPathtrackFIle(localFileName, year, serverFileName):
    serverFilePath = './'+year

    print("Uploading local file: "+localFileName+" to pathtrack as: "+serverFileName+" ...")
    ftpError, fileName = writeFTPFile(localFileName, serverFilePath, serverFileName, pathtrackHost, pathtrackUser, pathtrackPass)
    if ftpError and "550 Can't change directory to" in fileName:
        print("Creating new pathtrack folder: ./"+year+" ...")
        ftpError, folderName = createPathtrackDirectory("./",year)
        if ftpError:
            return True, fileName+"\n"+folderName
        print("Uploading local file: "+localFileName+" to pathtrack as: "+serverFileName+" ...")
        ftpError, fileName = writeFTPFile(localFileName, serverFilePath, serverFileName, pathtrackHost, pathtrackUser, pathtrackPass)
    return ftpError, fileName


#function to write a parsed header <header> and list of ephemerides <ephems> to a local file <localFileName>
#returns bool: error, string: localFileName
#error is True if there is an error in file writing, if there is an error localFileName is an error string, normally will be false
def writeRINEXtoFile(header, ephems, localFileName):
    print("Writing header and ephemerides to local file: "+localFileName+" ...")
    try:
        print("Opening local file to write: "+localFileName+" ...")
        with gzip.open(localRootAddress+localFileName,"wt",newline="\n") as f:
            print("Successful\n"+"Writing header and ephemerides ...")
            for line in header:
                f.write(line)
            for ephem in ephems:
                f.write(ephem['text'])
        print("Successful")
    except FileNotFoundError:
        return True,traceback.format_exc()+"\n"+"FileNotFound error when opening file to write: "+localFileName
    except OSError:
        return True,traceback.format_exc()+"\n"+"OS error when opening file to write: "+localFileName
    return False,localFileName


#function to compare 2 lists of ephemerides, if more than 5 old ephemerides are non existant in the new list a warning is printed as this is unexpected
def compareEphems(newEphems: list, oldEphems: list):
    numMissing = 0
    print("Merging old list of ephemerides into new list ...")
    for oldEphem in oldEphems:
        existing = False
        for newEphem in newEphems:
            if newEphem['sat'] == oldEphem['sat'] and abs((newEphem['time'] - oldEphem['time']).total_seconds()) < 300: 
                existing = True
                break
        if existing == False:
            numMissing += 1

    print(str(numMissing)+" old ephemerides non existant in new file")
    if numMissing > 5:
        print("WARNING all old ephemerides should be existant in new file")
    return


#function to validate if a list of ephemerides <ephems> is complete
#function counts number of ephemerides for each sat ID, if there are 24 or more satalites with 12 or more ephemerides, list is complete
#returns bool: complete
def validateEphems(ephems: list):
    print("Validating if list of ephemerides is complete ...")
    counts = [0]*32
    unhealthy = [0]*32
    # times = [ [] for _ in range(32) ]
    for ephem in ephems:
        counts[ephem['sat']-1] += 1
        if ephem['healthy'] == False:
            unhealthy[ephem['sat']-1] += 1
            counts[ephem['sat']-1] -= 1
    #     times[ephem['sat']-1].append(ephem['time'].strftime("%H:%M"))
    # for index, sat in enumerate(times):
    #     print("SVID:",index+1,", Num Ephemerides:",counts[index],", Ephemeris Times:",sat)
    # print("Diffs")
    # svid = 1
    # numBad = 0
    # badSVs = []
    # for satTimes in times:
    #     svid += 1
    #     lastTime = 0
    #     for time in satTimes:
    #         hourMin = time.split(":")
    #         newTime = int(hourMin[0])*60 + int(hourMin[1])
    #         diff = newTime - lastTime
    #         if diff > 240:
    #             if svid not in badSVs:
    #                 badSVs.append(svid)
    #             print("SVID:",svid)
    #             print(time)
    #             print(satTimes)
    #             numBad += 1
    #         lastTime = newTime
    # print()
    # print("Num gaps of over 4 hours:",numBad)
    # print(badSVs)
    # print()
    
    print("File contains",sum(counts),"healthy ephemerides")
    if(sum(counts) < 350):
        print("WARNING less healthy ephemerides in file than usual, typically over 350")
    print("File contains",sum(unhealthy),"unhealthy ephemerides")
    if(sum(unhealthy) > 15):
        print("WARNING over 15 unhealthy ephemerides in file")
    if sum(1 for count in counts if count >= 11) >= 24:
        print("List is complete")
        return True
    else:
        print("List is incomplete")
        return False
    


#function to add Pathtrack mark to header, used by host software to recognise if a file is complete
def markHeaderValid(header: list):
    print("Marking header as complete ...")
    for index, line in enumerate(header):
        if "ION ALPHA" in line:
            header.insert(index,"PATHTRACK MODIFIED EPHEMERIS FILE       %s     COMMENT\n" % datetime.now(timezone.utc).strftime("%d-%b-%y %H:%M").upper())
            break


#function to look for Pathtrack mark on header
def checkHeaderValid(header: list):
    print("Checking if header is marked complete ...")
    for line in header:
        if "PATHTRACK MODIFIED EPHEMERIS FILE" in line:
            print("Header marked complete")
            return True
    print("No mark on header")
    return False


#function to get the filename for the daily RINEX file for date <date>
#returns string: fileName, string: dayOfYear "DDD", string: year "YYYY"
def getDailyFileName(date: datetime):
    dayOfYear = date.strftime("%j")
    year = date.strftime("%Y")
    return "brdc"+dayOfYear+"0."+year[-2:]+"n.gz", dayOfYear, year


#function to get the filename for the hourly RINEX file for date <date>
#returns string: fileName, string: dayOfYear "DDD", string: year "YYYY"
def getHourlyFileName(date: datetime):
    dayOfYear = date.strftime("%j")
    year = date.strftime("%Y")
    return "hour"+dayOfYear+"0."+year[-2:]+"n.gz", dayOfYear, year


#function to update the file from date <date> on the Pathtrack server with the file from the NASA server
#if validate is True the file will be checked for completeness and marked
#if useHourly is True the hourly NASA file will be downloaded, otherwise the daily one will be used
#function prints out any errors generated by above functions that it calls
#returns bool: error, bool: valid
#error is True if any of the called functions return an error, if error is true valid is false
#valid is True if validate is True and the file downloaded from Pathtrack has previously been marked as valid, valid will not be true if a valid file was created and uploaded 
def updateFile(date: datetime, validate: bool, useHourly: bool):
    fileName, dayOfYear, year = getDailyFileName(date)
    if useHourly:
        ftpError, nasaFileName = getNASAHourlyFile(date)
    else:
        ftpError, nasaFileName = getNASADailyFile(date)
    if ftpError:
        print("FTP ERROR\n"+nasaFileName)
        return True, False
    
    timetag = datetime.now(timezone.utc).strftime("%j_%H_%M_")
    ftpError, ptrackFileName = uploadPathtrackFIle(nasaFileName, year, timetag+fileName)
    if ftpError:
        print("FTP ERROR\n"+ptrackFileName)
        return True, False

    parseError, nasaHeader, nasaEphems = parseRINEX(nasaFileName)
    if parseError:
        print("RINEX PARSE ERROR\n"+nasaHeader)
        return True, False
    
    ftpError, ptrackFileName = getPathtrackDailyFile(date)
    if not ftpError:
        parseError, ptrackHeader, ptrackEphems = parseRINEX(ptrackFileName)
    if ftpError or parseError:
        if ftpError and ("550 Can't open" not in ptrackFileName or "No such file" not in ptrackFileName):
            print("FTP ERROR\n"+ptrackFileName)
            return True, False
        if parseError:
            print("WARNING Pathtrack file faulty, replacing with nasa file")
        else:
            print("Pathtrack file non existant, uploading nasa file")
        if validate and validateEphems(nasaEphems):
            markHeaderValid(nasaHeader)
        writeError, localFileName = writeRINEXtoFile(nasaHeader, nasaEphems, "combined/"+fileName)
        if writeError:
            print("LOCAL WRITE ERROR\n"+localFileName)
            return True, False
        ftpError, ptrackFileName = uploadPathtrackFIle(localFileName, year, fileName)
        if ftpError:
            print("FTP ERROR\n"+ptrackFileName)
            return True, False
        return False, False

    if validate and checkHeaderValid(ptrackHeader):
        print("File marked as complete, file shouldn't be modified")
        return False, True

    compareEphems(nasaEphems, ptrackEphems)

    if validate and validateEphems(nasaEphems):
        markHeaderValid(nasaHeader)

    writeError, localFileName = writeRINEXtoFile(nasaHeader, nasaEphems, "combined/"+fileName)
    if writeError:
        print("LOCAL WRITE ERROR\n"+localFileName)
        return True, False

    ftpError, ptrackFileName = uploadPathtrackFIle(localFileName, year, fileName)
    if ftpError:
        print("FTP ERROR\n"+ptrackFileName)
        return True, False

    return False, False

#temp code to examine files
# err, header, ephems = parseRINEX("brdc1150.24n.gz")
# validateEphems(ephems)

# err, header, ephems = parseRINEX("temp/manual_brdc2570.24n.gz")
# err2, header2, ephems2 = parseRINEX("temp/nasa_brdc2570.24n.gz")
# if err or err2:
#     print(header)
#     print(header2)
# else:
#     combineEphems(ephems2, ephems)

# exit(0)


#for lambda this code is moved out of global scope and into a function called "lambda_handler(event, context)", with the exit(0) statements replaced with returns

#ensure subdirectories for intermediate files exist
Path(localRootAddress+"nasa").mkdir(exist_ok=True)
Path(localRootAddress+"ptrack").mkdir(exist_ok=True)
Path(localRootAddress+"combined").mkdir(exist_ok=True)

print("*******UPDATING TODAYS FILE***********\n")
today = datetime.now(timezone.utc)
#today = datetime(2024,8,15,3,0,0,tzinfo=timezone.utc)
oneAMtoday = datetime.combine(today.date(),time(1,0,0,tzinfo=timezone.utc))
twoAMtoday = datetime.combine(today.date(),time(2,0,0,tzinfo=timezone.utc))
error = False
if(today > oneAMtoday):
    error, valid = updateFile(today, False, True)
else:
    print("Skipping update of todays file as it is not yet 1AM and file will not be uploaded yet")
# error, valid = updateFile(today, False, True)
if error:
    print("Ending execution due to error")
    exit(0)
#update up to 1 week back of files, after this raise an error
previousDayValid = False
for delta in range(1,7):
    #validate files that are over a day old
    validate = delta > 1
    print("\n*******"+("VALIDATING AND " if validate else "")+"UPDATING TODAY -"+str(delta)+" DAYS FILE***********\n")
    if(delta == 1 and oneAMtoday < today < twoAMtoday):
        print("Skipping update of yesterdays file between 1AM and 2AM due to persistant issues with ephemerides being removed then readded")
        continue
    day = today - timedelta(delta)
    error, valid = updateFile(day, validate, False)
    if error:
        print("Ending execution due to error")
        exit(0)
    if valid and previousDayValid:
        print("Ending execution as consecutive complete files found")
        exit(0)
    if previousDayValid and not valid:
        print("ERROR file for day "+day.strftime("%j")+" is incomplete but file for day after is complete")
        print("Ending execution due to error")
        exit(0)
    previousDayValid = valid

print("ERROR 1 week backwards and no consecutive complete files found")
print("Ending execution due to error")

