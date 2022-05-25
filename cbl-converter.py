import json
import re
import os
from xml.sax.saxutils import escape

def extractJSON(fileName):

    file = open(fileName)
    data = json.load(file)

    countInvalidDate = 0
    countInvalidTitle = 0
    countInvalidNum = 0
    countInvalidTotal = 0

    bookList = []

    for issue in data:
        validTitle = True
        validDate = True
        validListNum = True

        invalidData = {}

        seriesPattern = "^(.*)\((\d{4})\) #(\d+)*"
        title = re.findall(seriesPattern,issue['title'])

        if len(title) == 1 and len(title[0]) == 3:
            seriesName = title[0][0].strip()
            seriesYear = title[0][1]
            issueNum = title[0][2]
        else:
            countInvalidTitle += 1
            validTitle = False
            print("Invalid title for %s : %s" % (issue['title'],title))

        datePattern = "(\d{2})/(\d{4})*"
        issueDate = re.findall(datePattern,issue['pubdate'])

        if len(issueDate) == 1 and len(issueDate[0]) == 2:
            issueYear = issueDate[0][1]
            issueMonth = issueDate[0][0]
        else:
            countInvalidDate += 1
            validDate = True
            print("Invalid date for %s : %s" % (issue['title'],issueDate))

        listNumber = issue['num']

        if not type(listNumber) == int:
            countInvalidNum += 1
            validListNum = False
            print("Invalid list number for %s : %s" % (issue['title'],listNumber))

        if not validListNum or not validDate or not validTitle:
            countInvalidTotal += 1

        issueID = seriesID = ""

        bookList.append({'listNumber':listNumber,'seriesName':seriesName,'seriesYear':seriesYear,'issueNum':issueNum,'issueYear':issueYear,'issueMonth':issueMonth, 'issueID':issueID, 'seriesID':seriesID})

    print("Total Issues: %s" % (len(data)))
    print("Total Invalid: %s" % (countInvalidTotal))
    print("%sInvalid Title: %s" % ('\t'*1,countInvalidTitle))
    print("%sInvalid Date: %s" % ('\t'*1,countInvalidDate))
    print("%sInvalid List Number: %s" % ('\t'*1,countInvalidNum))

    return bookList

def outputCBL(listName,bookList, dirPath):

    filePath = os.path.join(dirPath,"ReadingLists",listName.replace(" ","-") + ".cbl")

    with open(filePath, 'w') as file:
        line1 = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        line2 = "<ReadingList xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
        line3 = "<Name>%s</Name>" % (listName)
        line4 = "<Books>"

        fileHeader = [line1, line2, line3, line4]

        file.writelines(fileHeader)

        #For each issue in arc
        for book in bookList:

            #Set default values to blank string
            seriesName = issueNumber = seriesYear = issueYear = ""

            if book['seriesName'] is not None:
                seriesName = escape(str(book['seriesName']))
            if book['seriesYear'] is not None:
                seriesYear = str(book['seriesYear'])
            if book['issueNum'] is not None:
                issueNumber = str(book['issueNum'])
            if book['issueYear'] is not None:
                issueYear = str(book['issueYear'])
            if book['issueID'] is not None:
                issueCVID = str(book['issueID'])
            if book['seriesID'] is not None:
                seriesCVID = str(book['seriesID'])

            if seriesCVID or issueCVID:
                file.write("<Book Series=\"%s\" Number=\"%s\" Volume=\"%s\" Year=\"%s\">" % (seriesName,issueNumber,seriesYear,issueYear))
                file.write("<seriesCVID>%s</seriesCVID>" % (seriesCVID))
                file.write("<issueCVID>%s</issueCVID>" % (issueCVID))
                file.write("</Book>")
            else:
                file.write("<Book Series=\"%s\" Number=\"%s\" Volume=\"%s\" Year=\"%s\"></Book>" % (seriesName,issueNumber,seriesYear,issueYear))

        line1 = "</Books>"
        line2 = "<Matchers />"
        line3 = "</ReadingList>"

        footer = [line1, line2, line3]

        file.writelines(footer)

    file.close()

def main():
    issueList = extractJSON("cmro.json")

    listName = "Master Reading List"
    dirPath = os.getcwd()
    outputCBL(listName,issueList,dirPath)

main()
