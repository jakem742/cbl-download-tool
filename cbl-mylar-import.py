#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Installation:
1) Download & install this package (required for searching the comicvine api):
   https://github.com/jessebraham/comicvine-search
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
    python3 cbl-mylar-import.py

Results are output to "output.csv" in the same directory as the script

Notes:
    - Series are found based on series name and year match.
    - If multiple results are found, any matches of the preferred publisher will be prioritised.
    - For multiple matches, this script will output the last result found.
    - CV api calls are limited to once every 2 seconds, so this script can take a while for large collections.
        It is not recommended to reduce this, however you can modify the rate using the CV_API_RATE var.
    - If you mess anything up, you can simply delete the output.csv or force a re-run using the Mylar & CV FORCE_RECHECK vars.

'''

import requests
import json
import time
import os
from enum import IntEnum
import comicvine_search
from comicvine_search import ComicVineClient
import xml.etree.ElementTree as ET
from glob import glob
from sys import argv

### DEV OPTIONS
#Enable verbose output
VERBOSE = False
#Prevent overwriting of main CSV data file
TEST_MODE = False

#File prefs
SCRIPT_DIR = os.getcwd()
READINGLIST_DIR = os.path.join(SCRIPT_DIR, "ReadingLists")
DATA_FILE = os.path.join(SCRIPT_DIR, "output.csv")

if TEST_MODE:
    #Create new file instead of overwriting data file
    OUTPUT_FILE = os.path.join(SCRIPT_DIR, "output_new.csv")
else:
    OUTPUT_FILE = DATA_FILE

CSV_HEADERS = ["Series","Year","Publisher", "ComicID","InMylar"]
class Column(IntEnum):
    SERIES = 0
    YEAR = 1
    PUBLISHER = 2
    COMICID = 3
    INMYLAR = 4

#CV prefs
CV_SEARCH_LIMIT = 10000 #Maximum allowed number of CV API calls
CV_API_KEY = '[CV API KEY]'
CV_API_RATE = 2 #Seconds between CV API calls
FORCE_RECHECK_CV = False
PUBLISHER_BLACKLIST = ["Panini Comics","Editorial Televisa"]
PUBLISHER_PREFERRED = ["Marvel","DC Comics"] #If multiple matches found, prefer this result
CV = None

#Mylar prefs
mylarAPI = '[MYLAR API KEY]'
mylarBaseURL = '[MYLAR SERVER ADDRESS]'   #format= http://servername:port/
FORCE_RECHECK_MYLAR_MATCHES = False
ADD_NEW_SERIES_TO_MYLAR = True

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

def parseCBLfiles():
    series_list = []

    print("Checking CBL files in %s" % (READINGLIST_DIR))
    for root, dirs, files in os.walk(READINGLIST_DIR):
        for file in files:
            if file.endswith(".cbl"):
                try:
                    filename = os.path.join(root, file)
                    #print("Parsing %s" % (filename))
                    tree = ET.parse(filename)
                    fileroot = tree.getroot()

                    cblinput = fileroot.findall("./Books/Book")
                    for series in cblinput:
                        line = series.attrib['Series'].replace(",",""),series.attrib['Volume']
                        series_list.append(list(line))
                except:
                    print("Unable to process file at %s" % ( os.path.join(str(root), str(file)) ))

    return series_list

def isSeriesInMylar(comicID):
    found = False
    global mylarExisting
    global mylarMissing

    if comicID.isnumeric():
        comicCheckURL = "%s%s" % (mylarCheckURL, str(comicID))
        mylarData = requests.get(comicCheckURL).text
        jsonData = json.loads(mylarData)
        mylarComicData = jsonData['data']['comic']

        if not len(mylarComicData) == 0:
            found = True

    if found:
        if VERBOSE: print("Match found for %s in Mylar" % (comicID))
        mylarExisting += 1
        return True
    else:
        if VERBOSE: print("No match found for %s in Mylar" % (comicID))
        mylarMissing += 1
        return False

def addSeriesToMylar(comicID):
    if comicID.isnumeric():
        if VERBOSE: print("Adding %s to Mylar" % (comicID))
        comicAddURL = "%s%s" % (mylarAddURL, str(comicID))
        mylarData = requests.get(comicAddURL).text
        ## TODO: Check result of API call
        return True
    else:
        return False

def findVolumeDetails(series,year):
    found = False
    comicID = "Unknown"
    publisher = "Unknown"
    global searchCount
    global CVNotFound
    global CVFound
    global CV

    if isinstance(series,str):
        searchCount += 1

        result_matches = 0
        result_publishers = []
        result_matches_blacklist = 0

        series_matches = []
        publisher_blacklist_results = set()

        try:
            if VERBOSE: print("Searching for %s (%s) on CV" % (series,year))
            #response = CV.Volume.search(series)
            response = CV.search(series , resources=['volume'])

            if response.results is None:
                print("     No results found for %s (%s)" % (series,year))
            else: #Results were found
                    for result in response.results: #Iterate through CV results
                        #If exact series name and year match
                        if result['name'] == series and result['start_year'] == year:

                            publisher_temp = result['publisher']['name']
                            result_publishers.append(publisher_temp)

                            series_matches.append(result)

                            if publisher_temp in PUBLISHER_BLACKLIST:
                                result_matches_blacklist += 1
                                publisher_blacklist_results.add(publisher)
                            else:
                                found = True
                                result_matches += 1
                                publisher = publisher_temp
                                comicID = result['id']
                                print("     Found on comicvine: %s - %s (%s) : %s" % (publisher, series, year, comicID))

                    #Handle multiple publisher matches
                    if result_matches > 1:
                        print("         Warning: Multiple valid matches found! Publishers: %s" % (", ".join(result_publishers)))

                        #set result to preferred publisher
                        for item in series_matches:
                            if item['publisher']['name'] in PUBLISHER_PREFERRED:
                                publisher = item['publisher']['name']
                                comicID = item['id']
                                print("         Selected preferred publisher from multiple results: %s" % (publisher))

                    if result_matches_blacklist > 0 and result_matches == 0: #Only invalid results found
                        print("     No Valid results found for %s (%s). %s blacklisted results found with the following publishers: %s" % (series,year,result_matches_blacklist, ",".join(publisher_blacklist_results)))
        except Exception as e:
            print("There was an error processing %s (%s)" % (series,year))
            print(repr(e))

    #Update counters
    if not found:
        CVNotFound += 1
    else:
        CVFound += 1

    return [publisher,comicID]

def readExistingData():
    print("Reading data from %s" % (DATA_FILE))

    dataList = []

    if os.path.exists(DATA_FILE):
        #Import raw csv data as lines
        with open(DATA_FILE, mode='r') as csv_file:
            data = csv_file.readlines()

            #Parse csv data and strip whitespace
            for i in range(len(data)):
                if not i == 0: #Skip header row
                    fields = [x.strip() for x in data[i].split(",")]
                    dataList.append(fields)

    return dataList

def outputData(data):
    print("Exporting data to %s" % (OUTPUT_FILE))
    with open(OUTPUT_FILE, mode='w') as output_file:
        output_file.write("%s\n" % (",".join(CSV_HEADERS)))
        #Check if list contains multiple columns
        if len(data[0]) == 1:
            output_file.writelines(data)
        else:
            for row in data:
                output_file.write("%s\n" % (",".join(map(str,row))))

def index_2d(myList, v):
    for i, x in enumerate(myList):
        if v[0] == x[0] and v[1] == x[1]:
            return (i)

def mergeDataLists(list1, list2):
    # list1 = Main list with rows of 4 items
    # list2 = Import list with rows of 2 items
    print("Merging data lists")

    mainDataList = list1
    dataToMerge = list2
    global numExistingSeries
    global numCBLSeries
    global numNewSeries

    mainDataTitles = []
    mergedTitleSet = ()
    finalMergedList = []

    #Extract first 2 row elements to modified list
    for row in mainDataList:
        mainDataTitles.append([row[Column.SERIES], row[Column.YEAR]])

    mergedTitleList = mainDataTitles + dataToMerge
    mergedTitleList.sort()

    numExistingSeries = len(mainDataList)
    numCBLSeries = len(mergedTitleList)

    mergedTitleSet = set(tuple(map(tuple,mergedTitleList)))

    for row in mergedTitleSet:
        if list(row) in mainDataTitles:
          #Find index of exact match in mainDataSet
          match_row = index_2d(mainDataList,row)
          if VERBOSE: print("Merged row: %s found in main data at row %s" % (list(row),match_row))

          finalMergedList.append(mainDataList[match_row])
          #Removing
          if VERBOSE: print("Removing %s from mainDataList" % (list(row)))
          mainDataList.pop(match_row)

        else:
          if VERBOSE: print("Merged row: %s NOT found in main data" % (list(row)))
          #Use the list with only
          newData = [row[Column.SERIES],row[Column.YEAR],"Unknown","Unknown",False]
          finalMergedList.append(newData)

    numNewSeries = len(finalMergedList) - numExistingSeries

    return finalMergedList


def main():
    #Initialise CV API tool
    global CV
    CV = ComicVineClient(CV_API_KEY)

    global numExistingSeries
    global numCBLSeries
    global numNewSeries

    #Extract list from existing csv
    importData = readExistingData()

    #Process CBL files
    cblSeriesList = parseCBLfiles()

    #Merge csv data with cbl data
    mergedData = mergeDataLists(importData, cblSeriesList)
    mergedData.sort()

    print("Found %s series in CSV, %s new series in CBL" % (numExistingSeries,numNewSeries))

    #Run all data checks in CV & Mylar
    for rowIndex in range(len(mergedData)):
        series = mergedData[rowIndex][Column.SERIES]
        year = mergedData[rowIndex][Column.YEAR]
        publisher = mergedData[rowIndex][Column.PUBLISHER]
        comicID = mergedData[rowIndex][Column.COMICID]
        inMylar = mergedData[rowIndex][Column.INMYLAR]
        checkMylar = False
        comicIDExists = comicID.isnumeric()

        #Check for new comicIDs
        if not comicIDExists or FORCE_RECHECK_CV:
            #Self-imposed search limit to prevent hitting limits
            if searchCount < CV_SEARCH_LIMIT:
                #sleeping at least 1 second is what comicvine reccomends. If you are more than 450 requests in 15 minutes (900 seconds) you will be rate limited. So if you are going to be importing for a straight 15 minutes (wow), then you would want to changet this to 2.
                if searchCount > 0: time.sleep(CV_API_RATE)

                #Update field in data list
                cv_data = findVolumeDetails(series,year)
                mergedData[rowIndex][Column.PUBLISHER] = cv_data[0]
                mergedData[rowIndex][Column.COMICID] = cv_data[1]

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

        if checkMylar:
            #Update field in data list
            mergedData[rowIndex][Column.INMYLAR] = isSeriesInMylar(comicID)

        #Add new series to Mylar
        if not inMylar and ADD_NEW_SERIES_TO_MYLAR:
            mergedData[rowIndex][Column.INMYLAR] = addSeriesToMylar(comicID)


    #Write modified data to file
    outputData(mergedData)

    #Print summary to terminal
    print("Total Number of Series: %s, New Series Added From CBL: %s,  Existing Series (Mylar): %s,  Missing Series (Mylar): %s,  New Matches (CV): %s, Unfound Series (CV): %s" % (numExistingSeries,numNewSeries,mylarExisting,mylarMissing,CVFound,CVNotFound))

    ## TODO: Summarise list of publishers in results

main()
