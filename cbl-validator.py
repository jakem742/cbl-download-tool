#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Installation:
1) Download & install this package (required for searching the comicvine api):
   https://github.com/Buried-In-Code/Simyan
2) Create a folder called 'ReadingLists' in the same directory as the script and add any CBL files you want to process into this folder
3) Replace [MYLAR API KEY] with your Mylar3 api key
4) Replace [MYLAR SERVER ADDRESS] with your server in the format: http://servername:port/  (make sure to include the slash at the end)
5) Replace [CV API KEY] with your comicvine api key
6) Optional - Modify the following options:
    - PUBLISHER_BLACKLIST : List of publishers to ignore during CV searching
    - PUBLISHER_PREFERRED : List of publishers to prioritise when multiple CV matches are found
    - ADD_NEW_SERIES_TO_MYLAR : Automatically add CV search results to Mylar as new series
    - CV_SEARCH_LIMIT : Set a limit on the number of CV API calls made during this processing.
                        This is useful for large collections if you want to break the process into smaller chunks.

Usage:
    python3 cbl-validator.py

Results are output to "data.csv" in the same directory as the script

Notes:
    - Series are found based on series name and year match.
    - If multiple results are found, any matches of the preferred publisher will be prioritised.
    - For multiple matches, this script will output the result with the most issues (should help avoid TPB results).
    - CV api calls are limited to once every 2 seconds, so this script can take a while for large collections.
        It is not recommended to reduce this, however you can modify the rate using the CV_API_RATE var.
    - If you mess anything up, you can simply delete the data.csv or force a re-run using the Mylar & CV FORCE_RECHECK vars.

'''

import requests
import json
import time
import os
import re
from enum import IntEnum
from operator import itemgetter
import xml.etree.ElementTree as ET
from glob import glob
from sys import argv
import time
import csv
##TESTING NEW API
from simyan.session import Session

### DEV OPTIONS
#Enable verbose output
VERBOSE = False
#Prevent overwriting of main CSV data file
TEST_MODE = False

timeString = time.strftime("%y%m%d%H%M%S")

#File prefs
SCRIPT_DIR = os.getcwd()
RESULTS_DIR = os.path.join(SCRIPT_DIR, "Results")
DATA_DIR = os.path.join(SCRIPT_DIR, "Data")
READINGLIST_DIR = os.path.join(SCRIPT_DIR, "ReadingLists")
DATA_FILE = os.path.join(DATA_DIR, "data.csv")
RESULTS_FILE = os.path.join(RESULTS_DIR, "results-%s.txt" % (timeString))

if TEST_MODE:
    #Create new file instead of overwriting data file
    OUTPUT_FILE = os.path.join(DATA_DIR, "data-%s.csv" % (timeString))
else:
    OUTPUT_FILE = DATA_FILE

CSV_HEADERS = ["Series","Year","IssueList","Publisher","ComicID","NumIssues","InMylar"]
class Column(IntEnum):
    SERIES = 0
    YEAR = 1
    ISSUELIST = 2
    PUBLISHER = 3
    COMICID = 4
    NUMISSUES = 5
    INMYLAR = 6

#CV prefs
CV_SEARCH_LIMIT = 10000 #Maximum allowed number of CV API calls
CV_API_KEY = '18e89ce50b8f89c04c86627b93d45894f54921ce'
CV_API_RATE = 2 #Seconds between CV API calls
FORCE_RECHECK_CV = False #Recheck all valid CV IDs
ENABLE_CV = False #Allow CV checks
VALIDATE_ISSUES = True
PUBLISHER_BLACKLIST = ["Panini Comics","Editorial Televisa","Planeta DeAgostini","Unknown"]
PUBLISHER_PREFERRED = ["Marvel","DC Comics"] #If multiple matches found, prefer this result
session = Session(api_key=CV_API_KEY)

#Mylar prefs
mylarAPI = 'eadf6dfd1542b7f4984f2623c5941ec2'
mylarBaseURL = 'http://192.168.1.10:8090/'   #format= http://servername:port/
FORCE_RECHECK_MYLAR_MATCHES = False
ENABLE_MYLAR = False #Allow CV checks
ADD_NEW_SERIES_TO_MYLAR = False

mylarAddURL = mylarBaseURL + 'api?apikey=' + mylarAPI + '&cmd=addComic&id='
mylarCheckURL = mylarBaseURL + 'api?apikey=' + mylarAPI + '&cmd=getComic&id='

numNewSeries = 0
numExistingSeries = 0
numCBLSeries = 0

#Initialise counters
mylarExisting = 0
mylarMissing = 0
CVFound = 0
CVNotFound = 0
searchCount = 0

numVolumeResults = 0
numIssueResultsFound = 0
numIssuesTotal = 0
numVolumeMatches = 0

def readExistingData():
    printResults("Reading data from %s" % (DATA_FILE),2)

    dataList = []

    if os.path.exists(DATA_FILE):
        #Import raw csv data as lines
        with open(DATA_FILE, mode='r') as csv_file:
            #data = csv_file.readlines()
            i = 0
            #Parse csv data and strip whitespace
            for line in csv.reader(csv_file,quotechar='"',delimiter=',',quoting=csv.QUOTE_ALL, skipinitialspace=True):
                if i == 0:
                    i += 1
                    continue

                issuePattern = "([A-Z0-9]+) \[([0-9]+)\]"
                tupIssueList = re.findall(issuePattern,line[Column.ISSUELIST])
                dicIssueList = []
                for issue in tupIssueList:
                    curIssue = {'issueNumber':issue[0],'issueID':issue[1]}
                    dicIssueList.append(curIssue)

                line[Column.ISSUELIST] = dicIssueList

                dataList.append(line)


            #for i in range(len(data)):
            #    if not i == 0: #Skip header row
            #        fields = [x.strip().replace("\"","") for x in data[i].split(",")]
            #        issuePattern = "([A-Z0-9]+) \[([0-9]+)\]"
            #        tupIssueList = re.findall(issuePattern,fields[Column.ISSUELIST])
            #        dicIssueList = []
            #        for issue in tupIssueList:
            #            curIssue = {'issueNumber':issue[0],'issueID':issue[1]}
            #            dicIssueList.append(curIssue)
            #        fields[Column.ISSUELIST] = dicIssueList
            #        dataList.append(fields)

    return dataList

def parseCBLfiles():
    bookList = []

    printResults("Checking CBL files in %s" % (READINGLIST_DIR),2)
    for root, dirs, files in os.walk(READINGLIST_DIR):
        for file in files:
            if file.endswith(".cbl"):
                try:
                    filename = os.path.join(root, file)
                    #print("Parsing %s" % (filename))
                    tree = ET.parse(filename)
                    fileroot = tree.getroot()

                    cblinput = fileroot.findall("./Books/Book")
                    for entry in cblinput:
                        book = {'seriesName':entry.attrib['Series'],'seriesYear':entry.attrib['Volume'],'issueNumber':entry.attrib['Number']}#,'issueYear':entry.attrib['Year']}
                        bookList.append(book)
                except Exception as e:
                    printResults("Unable to process file at %s" % ( os.path.join(str(root), str(file)) ),3)
                    printResults(repr(e),3)

    bookSet = set()
    finalBookList = []

    for book in bookList:
        curSeriesName = book['seriesName']
        curSeriesYear = book['seriesYear']
        bookSet.add((curSeriesName,curSeriesYear))

    #Iterate through unique list of series
    if VERBOSE: printResults('Compiling set of issueNumbers from CBLs',2)
    for series in bookSet:
        curSeriesName = series[0]
        curSeriesYear = series[1]
        curSeriesIssues = []
        #Check every book for matches with series
        for book in bookList:
            if book['seriesName'] == curSeriesName and book['seriesYear'] == curSeriesYear:
                #Book matches current series! Add issueNumber to list
                curSeriesIssues.append({'issueNumber':book['issueNumber'],'issueID':"Unknown"})

        finalBookList.append({'seriesName':curSeriesName,'seriesYear':curSeriesYear,'issueNumberList':curSeriesIssues})

    return finalBookList

def index_2d(myList, v):
    for i, x in enumerate(myList):
        if v[0] == x[0] and v[1] == x[1]:
            return (i)

def mergeDataLists(csvData, cblData):
    # list1 = Main list from csv
    # list2 = Import list from cbl
    printResults("Merging data lists",2)

    mergedList = list(csvData)
    global numExistingSeries
    global numCBLSeries
    global numNewSeries

    if len(csvData) == 0:
        for cblSeries in cblData:
            newData = [cblSeries['seriesName'],cblSeries['seriesYear'],cblSeries['issueNumberList'],"Unknown","Unknown","Unknown",False]
            mergedList.append(newData)
    else:
        for cblSeries in cblData:
            #Lookup books in mergedList
            csvMatch = False
            for csvIndex in range(len(csvData)):

                seriesNameMatch = (cblSeries['seriesName'] == mergedList[csvIndex][Column.SERIES] or cblSeries['seriesName'].replace(",","") == mergedList[csvIndex][Column.SERIES])
                seriesYearMatch = cblSeries['seriesYear'] == mergedList[csvIndex][Column.YEAR]

                if seriesNameMatch and seriesYearMatch:
                    #Series already exists in mergedList. Update issueNumbers.
                    cblIssueList = cblSeries['issueNumberList']
                    csvIssueList = mergedList[csvIndex][Column.ISSUELIST]
                    csvIssueListNums = [issue['issueNumber'] for issue in csvIssueList]
                    finalIssueList = []

                    #iterate through cbl issue numbers
                    for issue in cblIssueList:
                        #check if issue num exists in csv already
                        if issue['issueNumber'] in csvIssueListNums:
                            #output existing csv data
                            index = csvIssueListNums.index(issue['issueNumber'])
                            finalIssueList.append(csvIssueList[index])
                        else:
                            #output new data from CBL
                            finalIssueList.append(issue)

                    mergedList[csvIndex][Column.ISSUELIST] = finalIssueList
                    csvMatch = True
                    continue

            if not csvMatch:
                #add new row to mergedList if not found
                newData = [cblSeries['seriesName'],cblSeries['seriesYear'],cblSeries['issueNumberList'],"Unknown","Unknown","Unknown",False]
                mergedList.append(newData)

    numExistingSeries = len(csvData)
    numCBLSeries = len(cblData)
    numNewSeries = len(mergedList) - numExistingSeries

    if VERBOSE: printResults("Merged List: %s" % (mergedList),3)

    return sorted(mergedList,key=itemgetter(0,1))

def isSeriesInMylar(comicID):
    found = False
    global mylarExisting
    global mylarMissing

    #print("Checking if comicID %s exists in Mylar" % (comicID))
    if ENABLE_MYLAR:
        if comicID.isnumeric():
            comicCheckURL = "%s%s" % (mylarCheckURL, str(comicID))
            mylarData = requests.get(comicCheckURL).text
            jsonData = json.loads(mylarData)
            mylarComicData = jsonData['data']['comic']

            if not len(mylarComicData) == 0:
                found = True

        elif comicID != "Unknown":
            printResults("Mylar series status unknown - invalid ComicID:%s" % (comicID),4)

        if found:
            if VERBOSE: printResults("Match found for %s in Mylar" % (comicID),4)
            mylarExisting += 1
            return True
        else:
            if VERBOSE: printResults("No match found for %s in Mylar" % (comicID),4)
            mylarMissing += 1
            return False

    #Fallback
    return False

def addSeriesToMylar(comicID):
    if comicID.isnumeric():
        if VERBOSE: printResults("Adding %s to Mylar" % (comicID),4)
        comicAddURL = "%s%s" % (mylarAddURL, str(comicID))
        mylarData = requests.get(comicAddURL).text

        ## Check result of API call
        jsonData = json.loads(mylarData)
        #jsonData = mylarData.json()
        #mylarComicData = jsonData['data']['comic']

        if jsonData['success'] == "true":
            return True
        else:
            return False
    else:
        return False

def findVolumeDetails(series,year, issueList):
    data = {'publisher':"Unknown",'comicID':"Unknown",'numIssues':"Unknown"}
    global searchCount
    global CVNotFound; global CVFound; global session
    global numVolumeResults; numVolumeResults = 0
    global numVolumeMatches; numVolumeMatches = 0
    global numCVMatchOne; global numCVMatchMultiple;
    global numCVNoMatchBlacklist; global numCVNoMatch;

    if ENABLE_CV:
        if isinstance(series,str):
            searchCount += 1
            numIssues = len(issueList)
            issueCounter = 0

            results = []
            series_matches = []
            blacklist_matches = []
            allowed_matches = []
            preferred_matches = []

            try:
                VERBOSE: printResults("Searching for Volume : %s (%s) on CV" % (series,year),4)
                response = session.volume_list(params={"filter": "name:%s" % (series) })

                numVolumeResults = len(response)

                if response is None or len(response) == 0:
                    #print("         0 CV results found for %s (%s)" % (series,year))
                    numCVNoMatch += 1
                else: #Results were found

                    for result in response: #Iterate through CV results
                        #If exact series name and year match
                        if result.name == series and str(result.start_year) == year:
                            #Add result to lists
                            series_matches.append(result)
                            curPublisher = result.publisher.name

                            if curPublisher in PUBLISHER_BLACKLIST:
                                blacklist_matches.append(result)
                            elif curPublisher in PUBLISHER_PREFERRED:
                                preferred_matches.append(result)
                            else:
                                allowed_matches.append(result)

                    numVolumeMatches = len(series_matches) - len(blacklist_matches)
                    if numVolumeMatches < 0: numVolumeMatches = 0

                    if len(series_matches) == 0:
                        numCVNoMatch += 1
                        printResults("No exact matches found for %s (%s)" % (series,year),4)
                    elif len(series_matches) == 1:
                        #One match
                        if len(blacklist_matches) > 0:
                            numCVNoMatchBlacklist += 1
                            printResults("No valid results found for %s (%s). %s blacklisted results found with the following publishers: %s" % (series,year,len(blacklist_matches), ",".join(blacklist_matches)),4)
                        else:
                            numCVMatchOne += 1
                            results = series_matches
                    else:
                        #Multiple matches
                        numCVMatchMultiple += 1
                        publishers = set([vol.publisher.name for vol in series_matches])
                        printResults("Warning: Multiple CV matches found! Publishers: %s" % (", ".join(publishers)),4)
                        if len(preferred_matches) > 0 :
                            results = preferred_matches
                        elif len(allowed_matches) > 0 :
                            results = allowed_matches
                        else:
                            printResults("No valid results found for %s (%s). %s blacklisted results found." % (series,year,len(blacklist_matches)),4)

                    data = processCVResults(results)
                    #data = findIssueDetails(data)

            except Exception as e:
                printResults("     There was an error processing Volume search for %s (%s)" % (series,year),4)
                printResults(repr(e),4)
    else:
        data = {'publisher':"Unknown",'comicID':"Unknown",'numIssues':"0"}

    return data

def findIssueDetails(comicID, issueList):
    global session
    checkedIssueList = []

    issuesFoundCounter = 0
    numIssueResultsFound = "N/A"
    numIssuesTotal = len(issueList)

    try:
        if comicID != "Unknown":
            resultIssueNums = []

            #print(issueList)

            if VALIDATE_ISSUES:
                if VERBOSE: printResults("Searching for issues on CV with ComicID %s " % (comicID),4)
                results = session.issue_list(params={"filter": "volume:%s" % (comicID)})

                for issue in results:
                    resultIssueNums.append(issue.number)

            for issue in issueList:
                issueID = "Unknown"
                issueNumber = issue['issueNumber']

                #If issueNum exists in list of results, grab id
                if VALIDATE_ISSUES and (issueNumber in resultIssueNums):
                    issueIndex = resultIssueNums.index(issueNumber)
                    issueID = results[issueIndex].id

                checkedIssueList.append({'issueNumber':issueNumber,'issueID':issueID})
        else:
            checkedIssueList = issueList

    except Exception as e:
        printResults("There was an error processing Issue search for %s" % (comicID),4)
        printResults(repr(e),4)

    return checkedIssueList

def processCVResults(results):
    issueCounter = 0
    publisher = "Unknown"
    comicID = "Unknown"

    if len(results) > 0:
        for item in results:
            numIssues = item.issue_count
            if numIssues > issueCounter:
                #Current series has more issues than any other preferred results!
                publisher = item.publisher.name
                comicID = item.id
                issueCounter = numIssues

        #print("             Selected series from results: %s - %s (%s issues)" % (publisher,comicID,numIssues))

    return {'publisher':publisher,'comicID':comicID,'numIssues':str(issueCounter)}

def outputData(data):
    printResults("\nExporting data to %s" % (OUTPUT_FILE),1)
    with open(OUTPUT_FILE, mode='w') as output_file:
        output_file.write("%s\n" % (",".join(CSV_HEADERS)))
        #Check if list contains multiple columns
        if len(data[0]) == 1:
            output_file.writelines(data)
        else:
            for row in data:
                rowTemplate = '{seriesName},{seriesYear},{issueList},{publisher},{comicID},{numIssues},{inMylar}\n'
                issueTemplate = '{issueNumber} [{issueID}]; '
                issueString = ""
                for issue in row[2]:
                    curIssueString = issueTemplate.format(issueNumber=issue['issueNumber'],issueID=issue['issueID'])
                    issueString += curIssueString

                rowString = rowTemplate.format(
                    seriesName="\"%s\"" % (row[0]),
                    seriesYear=row[1],
                    issueList=issueString,
                    publisher=row[3],
                    comicID=row[4],
                    numIssues=row[5],
                    inMylar=row[6]
                )

                output_file.write(rowString)

def printResults(string,indentation,lineBreak = False):


    with open(RESULTS_FILE, mode='a') as resultsFile:
        if lineBreak:
            print("")
            resultsFile.write("\n")
        print("%s%s" % ('\t'*indentation,string))

        resultsFile.write("\n%s%s" % ('\t'*indentation,string))
        resultsFile.flush()



def main():
    #Initialise CV API tool
    global CV
    global numVolumeResults; global numVolumeMatches;

    global numMylarFoundAdded; numMylarFoundAdded = 0; global numMylarFoundNotAdded; numMylarFoundNotAdded = 0;
    global numMylarFoundUnchecked; numMylarFoundUnchecked = 0; global numMylarMissingUnchecked; numMylarMissingUnchecked = 0;
    global numMylarMissingNotAdded; numMylarMissingNotAdded = 0; global numMylarMissingFailed; numMylarMissingFailed = 0;

    global numCVMatchOne; numCVMatchOne = 0; global numCVMatchMultiple; numCVMatchMultiple = 0;
    global numCVNoMatchBlacklist; numCVNoMatchBlacklist = 0; global numCVNoMatch; numCVNoMatch = 0;
    global numCVMatchExisting; numCVMatchExisting = 0;

    partialIssueMatchList = []; noIssueMatchList = [];

    printResults("Loading data",1)
    #Extract list from existing csv
    csvData = readExistingData()
    if VERBOSE: printResults("CSV Data Import: %s" % (csvData),2)

    #Process CBL files
    cblData = parseCBLfiles()
    if VERBOSE: printResults("CBL Data Import: %s" % (cblData),2)

    #Merge csv data with cbl data
    mergedData = mergeDataLists(csvData, cblData)

    numVolumes = len(mergedData)
    seriesNumCounter = 0

    printResults("Found %s series in CSV, %s new series in CBL" % (numExistingSeries,numNewSeries),2)
    printResults("\nChecking Series",1)

    #Run all data checks in CV & Mylar
    for rowIndex in range(len(mergedData)):
        try:
            seriesNumCounter += 1
            series = mergedData[rowIndex][Column.SERIES]
            year = mergedData[rowIndex][Column.YEAR]
            issueList = mergedData[rowIndex][Column.ISSUELIST]
            publisher = mergedData[rowIndex][Column.PUBLISHER]
            comicID = mergedData[rowIndex][Column.COMICID]
            inMylar = mergedData[rowIndex][Column.INMYLAR]
            inMylar = inMylar == "True"
            checkMylar = False
            cvSearched = False
            mylarChecked = False
            comicIDExists = comicID.isnumeric()

            issueID_missing = any(issue['issueID'] == "Unknown" for issue in issueList)

            if comicID.isnumeric() and not FORCE_RECHECK_CV: numCVMatchExisting += 1

            #Check for new comicIDs
            if not comicIDExists or FORCE_RECHECK_CV:
                #Self-imposed search limit to prevent hitting limits
                if searchCount < CV_SEARCH_LIMIT:
                    #sleeping at least 1 second is what comicvine reccomends. If you are more than 450 requests in 15 minutes (900 seconds) you will be rate limited. So if you are going to be importing for a straight 15 minutes (wow), then you would want to changet this to 2.
                    if searchCount > 0 and ENABLE_CV: time.sleep(CV_API_RATE)

                    cvSearched = True
                    #Update field in data list
                    cvResults = findVolumeDetails(series,year,issueList)
                    mergedData[rowIndex][Column.PUBLISHER] = cvResults['publisher']
                    mergedData[rowIndex][Column.COMICID] = cvResults['comicID']
                    mergedData[rowIndex][Column.NUMISSUES] = cvResults['numIssues']

                    #update comicID var for use elsewhere
                    comicID = str(cvResults['comicID'])


            if issueID_missing:
                if ENABLE_CV: time.sleep(CV_API_RATE)
                mergedData[rowIndex][Column.ISSUELIST] = findIssueDetails(comicID,issueList)

            #Check if series exists in mylar
            if inMylar:
                #Match exists in mylar
                if FORCE_RECHECK_MYLAR_MATCHES:
                    #Force recheck anyway
                    checkMylar = True
                else:
                    checkMylar = False
            else:
                #No mylar match found
                checkMylar = True

            mylarStatus = "Unknown"

            if checkMylar:
                #Update field in data list
                inMylar = isSeriesInMylar(comicID)
                mergedData[rowIndex][Column.INMYLAR] = inMylar
                if inMylar:
                    mylarStatus = "Found (Not Added)"
                    numMylarFoundNotAdded += 1
                else:
                    mylarStatus = "Missing (Not Added)"
                    numMylarMissingNotAdded += 1
            elif inMylar:
                mylarStatus = "Found (Unchecked)"
                numMylarFoundUnchecked += 1
            else:
                mylarStatus = "Missing (Unchecked)"
                numMylarMissingUnchecked += 1

            #Add new series to Mylar
            if not inMylar and ADD_NEW_SERIES_TO_MYLAR:
                mergedData[rowIndex][Column.INMYLAR] = addSeriesToMylar(comicID,issueList)
                if mergedData[rowIndex][Column.INMYLAR] == True:
                    mylarStatus = "Found (Added)"
                    numMylarFoundAdded += 1
                else:
                    mylarStatus = "Missing (Add Failed)"
                    numMylarMissingFailed += 1


            if comicID == "Unknown":
                numVolumeResults = 0

            issueList = list(mergedData[rowIndex][Column.ISSUELIST])
            issuesFound = 0; issuesTotal = len(issueList)

            for issue in issueList:
                if str(issue['issueID']).isnumeric(): issuesFound += 1

            if issuesFound == 0:
                noIssueMatchList.append({'seriesName':series,'seriesYear':year,'seriesID':comicID,'issuesFound':issuesFound,'issuesTotal':issuesTotal})
            elif issuesFound != issuesTotal:
                partialIssueMatchList.append({'seriesName':series,'seriesYear':year,'seriesID':comicID,'issuesFound':issuesFound,'issuesTotal':issuesTotal})

            printResults("[%s/%s] Series: %s (%s) [%s]" % (seriesNumCounter,numVolumes,series,year,comicID),2)
            if cvSearched: printResults("Volumes: CV Results = %s; Matches = %s" % (numVolumeResults,numVolumeMatches),3)
            printResults("Issues: %s / %s" % (issuesFound,issuesTotal),3)
            printResults("Mylar: %s" % (mylarStatus),3)

        except Exception as e:
            printResults("There was an error processing data entry for %s (%s)" % (series, year),4)
            printResults(repr(e),4)



    #Write modified data to file
    outputData(mergedData)

    #Print summary to terminal
    printResults("*** SUMMARY ***",1,True)

    printResults("Series: %s" % (numVolumes),2,True)
    printResults("ComicVine Results:",2)
    printResults("VOLUMES",3)
    printResults("Match (Existing) = %s" % (numCVMatchExisting),4) #One match
    printResults("Match (Single) = %s" % (numCVMatchOne),4) #One match
    printResults("Match (Multiple) = %s" % (numCVMatchMultiple),4) #Multiple series matches
    printResults("No Match (Blacklist) = %s" % (numCVNoMatchBlacklist),4) #Blacklist publisher matches only
    printResults("No Match (Unfound) = %s" % (numCVNoMatch),4) #No cv matches

    numPartialIssueMatch = len(partialIssueMatchList)
    numNoIssueMatch = len(noIssueMatchList)
    numFullIssueMatch = numVolumes - numPartialIssueMatch - numNoIssueMatch

    printResults("ISSUES",3,True)
    printResults("Full Match = %s" % (numFullIssueMatch),4)
    printResults("Partial Match = %s" % (numPartialIssueMatch),4)
    for match in partialIssueMatchList:
        printResults("%s (%s) [%s] : %s / %s" % (match['seriesName'],match['seriesYear'],match['seriesID'],match['issuesFound'],match['issuesTotal']),5)
    printResults("No Match = %s" % (numNoIssueMatch),4)
    for match in noIssueMatchList:
        printResults("%s (%s) [%s] : %s / %s" % (match['seriesName'],match['seriesYear'],match['seriesID'],match['issuesFound'],match['issuesTotal']),5)

    printResults("Mylar Status:",2,True)
    printResults("Found (Added) = %s" % (numMylarFoundAdded),3)
    printResults("Found (Not Added) = %s" % (numMylarFoundNotAdded),3)
    printResults("Found (Unchecked) = %s" % (numMylarFoundUnchecked),3)
    printResults("Missing (Not Added) = %s" % (numMylarMissingNotAdded),3)
    printResults("Missing (Failed) = %s" % (numMylarMissingFailed),3)
    printResults("Missing (Unchecked) = %s" % (numMylarMissingUnchecked),3)

main()
