# Reading List Tools
Various tools for validating/creating CBL reading lists and importing them into Mylar as series

**Requirements**

This tool relies on the following software:
- mylar/mylar3
- Buried-In-Code/Simyan 
- Comicvine (personal API key required)

**Features**:
- Read, optimise & maintain a list of series found in one or more CBL files
- Search for comicvine series matches. Ability to blacklist & prefer specific publishers when finding matches.
- Check series status in Mylar. Option to add series to Mylar.
- Generate CBL from JSON file (specific JSON formatting required)

**Installation**:
1) Download & install this package (required for searching the comicvine api):
   https://github.com/Buried-In-Code/Simyan
2) Create folders called 'ReadingLists','Data','Results' in the same directory as the script and add any CBL files you want to process into the 'ReadingLists' folder
3) Replace [MYLAR API KEY] with your Mylar3 api key
4) Replace [MYLAR SERVER ADDRESS] with your server in the format: http://servername:port/  (make sure to include the slash at the end)
5) Replace [CV API KEY] with your comicvine api key
6) Optional - Modify the following options:
    - PUBLISHER_BLACKLIST : List of publishers to ignore during CV searching
    - PUBLISHER_PREFERRED : List of publishers to prioritise when multiple CV matches are found
    - ADD_NEW_SERIES_TO_MYLAR : Automatically add CV search results to Mylar as new series
    - CV_SEARCH_LIMIT : Set a limit on the number of CV API calls made during this processing.
                        This is useful for large collections if you want to break the process into smaller chunks.
**Usage**:
    python3 cbl-validator.py
    
Results are output to "data.csv" in the Data directory

**Notes**:
- Series are found based on series name and year match.
- If multiple results are found, any matches of the preferred publisher will be prioritised.
- For multiple matches, this script will output the result with the largest number of issues (less like to be tpb/omnis).
- CV api calls are limited to once every 2 seconds, so this script can take a while for large collections.
   It is not recommended to reduce this, however you can modify the rate using the CV_API_RATE var.
- If you mess anything up, you can simply delete the output.csv or force a re-run using the Mylar & CV FORCE_RECHECK vars.
