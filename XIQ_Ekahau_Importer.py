#!/usr/bin/env python3
import logging
import argparse
import time
import sys
import os
import inspect
import shutil
import getpass
import pandas as pd
import numpy as np
from app.Ekahau_importer import Ekahau
from app.ap_csv_importer import apSerialCSV
from mapImportLogger import logger
from app.xiq_exporter import XIQ
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
logger = logging.getLogger('MapImporter.Main')

parser = argparse.ArgumentParser()
parser.add_argument('--external',action="store_true", help="Optional - adds External Account selection, to create floorplans and APs on external VIQ")
parser.add_argument('--csv', type=str, help="Optional - Allows to import a CSV file that will match AP names to serial numbers") 
args = parser.parse_args()

PATH = current_dir
imageFilePath = PATH + "/app/images/"

# Git Shell Coloring - https://gist.github.com/vratiu/9780109
RED   = "\033[1;31m"  
BLUE  = "\033[1;34m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RESET = "\033[0;0m"

def yesNoLoop(question):
    validResponse = False
    while validResponse != True:
        response = input(f"{question} (y/n) ").lower()
        if response =='n' or response == 'no':
            response = 'n'
            validResponse = True
        elif response == 'y' or response == 'yes':
            response = 'y'
            validResponse = True
        elif response == 'q' or response == 'quit':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
    return response

def checkNameLength(name, type):
    while len(name) > 32:
        sys.stdout.write(YELLOW)
        sys.stdout.write(f"'{name}' is longer than 32 characters allowed for a name.\n")
        sys.stdout.write(RESET)
        name = input(f"Please enter a new name for the {type} that is less than 32 characters: ")
    return name


def getParentLocation(building="new"):
    # Get Parent location
    response = yesNoLoop(f"Would you like to create the {building} building under a sub location?")
    if response == 'y':
        filt = location_df['type'] == 'Location'
        sublocation_df = location_df.loc[filt]
        validResponse = False
        while validResponse != True:
            count = 0
            countmap = {}
            print("Which location would you like the building to be under?")
            for loc_id, location_info in sublocation_df.iterrows():
                countmap[count] = loc_id
                print(f"   {count}. {location_info['name']}")
                count+=1
            print(f"   {count}. Create a new location")
            selection = input(f"Please enter 0 - {count}: ")
            try:
                selection = int(selection)
            except:
                sys.stdout.write(YELLOW)
                sys.stdout.write("Please enter a valid response!!\n")
                sys.stdout.write(RESET)
                continue
            if 0 <= selection < count:
                validResponse = True
                location_id = (sublocation_df.loc[countmap[selection],'id'])
                parent_name = (sublocation_df.loc[countmap[selection],'name'])
            elif selection == count:
                validResponse = True
                filt = location_df['type'] == 'Global'
                parent_id = location_df.loc[filt, 'id'].values[0]
                location_id, parent_name = createLocation(parent_id)
    elif response == 'n':
        filt = location_df['type'] == 'Global'
        location_id = location_df.loc[filt, 'id'].values[0]
        parent_name = location_df.loc[filt, 'name'].values[0]
    return location_id, parent_name 

def createLocation(parent_id):
    validResponse = False
    while validResponse != True:
        location_name = input("What would you like the name of this location to be? ")
        if location_name in sublocation_df['name'].unique():
            sys.stdout.write(YELLOW)
            sys.stdout.write("\nThis location name exists already. Please enter a new location name.\n") 
            sys.stdout.write(RESET)
            continue
        elif location_name.lower() == 'quit':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
        elif not location_name.strip():
            print("\nPlease enter a new location name.\n") 
            continue
        location_name = checkNameLength(location_name, type='location')
        print(f"\nLocation '{location_name}' will be created.")
        response = yesNoLoop("Would you like to proceed?")
        if response == 'y':
            validResponse = True
            data = {"parent_id": parent_id, "name": location_name}
        elif response == 'n':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
    subLocationId = x.createLocation(location_name, data)
    if subLocationId != 0:
        sys.stdout.write(GREEN)
        sys.stdout.write(f"Location {location_name} was successfully created.\n\n")
        sys.stdout.write(RESET)
    return subLocationId, location_name

def createBuildingInfo(location_id, parent_name):
    validResponse = False
    while validResponse != True:
        building_name = input("What would you like the name of the building to be? ")
        building_address = input("What is the address for this building? ")
        if building_name in building_df['name'].unique():
            sys.stdout.write(YELLOW)
            sys.stdout.write("\nThis building name already exists. Please enter a new building name.\n\n") 
            sys.stdout.write(RESET)
            continue
        elif building_name.lower() == 'quit':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
        elif not building_name.strip():
            print("\nPlease enter a new building name.\n") 
            continue
        if not building_address.strip():
            building_address = 'Unknown Address'
        building_name = checkNameLength(building_name, type='building')
        print(f"\n\nBuilding '{building_name}' with address '{building_address}' will be created under location '{parent_name}'.")
        response = yesNoLoop("Would you like to proceed?")
        if response == 'y':
            validResponse = True
            data = {"parent_id": location_id, "name": building_name, "address": building_address}
            return data
        elif response == 'n':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit

def updateApWithId(ap):
    global ek_ap_df
    filt = ek_ap_df['sn'] == ap['serial_number']
    ek_ap_df.loc[filt,'xiq_id'] = ap['id']


## EKAHAU IMPORT
filename = str(input("Please enter the Ekahau File: ")).strip()
#filename = "Mayflower.esx"
filename = filename.replace("\ ", " ")
filename = filename.replace("'", "")

saveImages = False
print("Gathering Ekahau Data.... ", end='')
sys.stdout.flush()
x = Ekahau(filename)
try:
    rawData = x.exportFile()
except ValueError as e:
    print("Failed")
    sys.stdout.write(YELLOW)
    sys.stdout.write(str(e) +'\n')
    sys.stdout.write(RED)
    sys.stdout.write("script is exiting....\n")
    sys.stdout.write(RESET)
    raise SystemExit
except:
    log_msg = "Unknown Error opening and exporting Ekahau data"
    print("Failed")
    print(log_msg)
    logger.error(log_msg)
    raise SystemExit
#pprint(rawData)
#print("\n\n")
print("Complete\n")


## CSV AP MAPPER
if args.csv:
    print("Gathering Serial Numbers from CSV file.... ", end='')
    sys.stdout.flush()
    filename = args.csv
    x = apSerialCSV(filename, rawData['aps'])
    try:
        rawData['aps'], unmatched_ap_info_ap, unmatched_csv_ap = x.getSerialNumbers()
    except ValueError as e:
        print(e)
    except:
        log_msg = "Unknown Error opening and exporting CSV data"
        sys.stdout.write(RED)
        sys.stdout.write(log_msg+"\n")
        sys.stdout.write(RESET)
        logger.error(log_msg)
        raise SystemExit
    print("Complete\n")
    if unmatched_ap_info_ap:
        print("These APs were not found in CSV\n  ", end='')
        print(*unmatched_ap_info_ap, sep='\n  ')
        logger.warning("These APs were not found in the CSV file: " + ",".join(unmatched_ap_info_ap))
    if unmatched_csv_ap:
        print("These APs were in the CSV but did not match the name of any AP\n  ", end='')
        print(*unmatched_csv_ap, sep='\n  ')
        logger.warning("These APs were in the CSV file but did not match the name of any AP in Ekahau: " + ",".join(unmatched_csv_ap))
    #pprint(rawData)
    #print("\n\n")

## XIQ EXPORT

print("Enter your XIQ login credentials")
username = input("Email: ")
password = getpass.getpass("Password: ")


x = XIQ(username,password)
if args.external:
    accounts, viqName = x.selectManagedAccount()
    if accounts == 1:
        validResponse = False
        while validResponse != True:
            response = input("No External accounts found. Would you like to import data to your network? (y/n)")
            if response == 'y':
                validResponse = True
            elif response =='n':
                sys.stdout.write("Thanks. ")
                sys.stdout.write(RED)
                sys.stdout.write("Script is exiting....\n")
                sys.stdout.write(RESET)
                raise SystemExit
    elif accounts:
        validResponse = False
        while validResponse != True:
            print("\nWhich VIQ would you like to import the floor plan and APs too?")
            accounts_df = pd.DataFrame(accounts)
            count = 0
            for df_id, viq_info in accounts_df.iterrows():
                print(f"   {df_id}. {viq_info['name']}")
                count = df_id
            print(f"   {count+1}. {viqName} (This is Your main account)\n")
            selection = input(f"Please enter 0 - {count+1}: ")
            try:
                selection = int(selection)
            except:
                sys.stdout.write(YELLOW)
                sys.stdout.write("Please enter a valid response!!\n")
                sys.stdout.write(RESET)
                continue
            if 0 <= selection <= count+1:
                validResponse = True
                if selection != count+1:
                    newViqID = (accounts_df.loc[int(selection),'id'])
                    newViqName = (accounts_df.loc[int(selection),'name'])
                    x.switchAccount(newViqID, newViqName)
                    

xiq_building_exist = False
ekahau_building_exists = False

location_df = x.gatherLocations()
filt = location_df['type'] == 'BUILDING'
building_df = location_df.loc[filt]
filt = location_df['type'] == 'Location'
sublocation_df = location_df.loc[filt]

# Check Building
if rawData['building']:
    for building in rawData['building']:
        #if not (lambda x: x['associated_building_id'] == building['building_id'], rawData['floors']):
        if not any(d['associated_building_id'] == building['building_id'] for d in rawData['floors']):
            log_msg = (f"no floors were found for building {building['name']}. Skipping creation of building")
            logger.info(log_msg)
            continue
        ekahau_building_exists = True
        if building['name'] in building_df['name'].unique():
            response = yesNoLoop(f"Building {building['name']} exists, would you like to add floorPlan(s) to it?")
            if response == 'y':
                xiq_building_exist = True
                filt = location_df['name'] == building['name']
                building_id = location_df.loc[filt, 'id'].values[0]
                building['xiq_building_id'] = str(building_id)
                logger.info(f"There is already a building with the name {building['name']} that will be used")
            else:
                print('Ok we will attempt to create a new building but it will have to be renamed.')
                location_id, parent_name = getParentLocation()
                data = createBuildingInfo(location_id,parent_name)
                building['name'] = data['name']
                building['xiq_building_id'] = x.createBuilding(data)
                if building['xiq_building_id'] != 0:
                    log_msg = f"Building {building['name']} was successfully created."
                    print(log_msg+'\n')
                    logger.info(log_msg)
        elif building['name'].lower() == 'building 1':
            print(f"Building name is set to the default Ekahau building name - {building['name']}")
            response = yesNoLoop("Would you like to change the name?")
            if response == 'y':
                print('Ok we will attempt to create a new building but it will have to be renamed.')
                location_id, parent_name = getParentLocation()
                data = createBuildingInfo(location_id,parent_name)
                building['name'] = data['name']
                building['xiq_building_id'] = x.createBuilding(data)
                if building['xiq_building_id'] != 0:
                    log_msg = f"Building {building['name']} was successfully created."
                    sys.stdout.write(GREEN)
                    sys.stdout.write(log_msg+'\n\n')
                    sys.stdout.write(RESET)
                    logger.info(log_msg)
            else:
                data = building.copy()
                location_id, parent_name = getParentLocation(building=building['name'])
                del data['building_id']
                del data['xiq_building_id']
                if not data['address'].strip():
                    data['address'] = 'Unknown Address'
                data['parent_id'] = f"{location_id}"
                if len(data['name']) > 32:
                    data['name'] = checkNameLength(data['name'], type='building')
                building['xiq_building_id'] = x.createBuilding(data)
                if building['xiq_building_id'] != 0:
                    log_msg = f"Building {building['name']} was successfully created."
                    sys.stdout.write(GREEN)
                    sys.stdout.write(log_msg+'\n\n')
                    sys.stdout.write(RESET)
                    logger.info(log_msg)

        else:
            data = building.copy()
            location_id, parent_name = getParentLocation(building=building['name'])
            del data['building_id']
            del data['xiq_building_id']
            if not data['address'].strip():
                data['address'] = 'Unknown Address'
            data['parent_id'] = f"{location_id}"
            if len(data['name']) > 32:
                data['name'] = checkNameLength(data['name'], type='building')
            building['xiq_building_id'] = x.createBuilding(data)
            if building['xiq_building_id'] != 0:
                log_msg = f"Building {building['name']} was successfully created."
                sys.stdout.write(GREEN)
                sys.stdout.write(log_msg+'\n\n')
                sys.stdout.write(RESET)
                logger.info(log_msg)
            
    
if xiq_building_exist == False and ekahau_building_exists == False: 
    location_id, parent_name = getParentLocation()
    data = createBuildingInfo(location_id,parent_name)
    data['xiq_building_id'] = x.createBuilding(data)
    if data['xiq_building_id'] != 0:
        log_msg = f"Building {data['name']} was successfully created."
        sys.stdout.write(GREEN)
        sys.stdout.write(log_msg+'\n\n')
        sys.stdout.write(RESET)
        logger.info(log_msg)
    del data['parent_id']
    rawData['building'].append(data)

# Create Floor(s)
ek_building_df = pd.DataFrame(rawData['building'])
if ekahau_building_exists == True:
    for floor in rawData['floors']:
        if floor['associated_building_id'] == None:
            log_msg = f"Floor '{floor['name']}' is not associated with the buildings in Ekahau so it will be skipped."
            logger.warning(log_msg)
            sys.stdout.write(YELLOW)
            sys.stdout.write(log_msg + '\n')
            sys.stdout.write(RESET)
            continue
        filt = ek_building_df['building_id'] == floor['associated_building_id']
        xiq_building_id = int(ek_building_df.loc[filt, 'xiq_building_id'].values[0])
        building_name = ek_building_df.loc[filt, 'name'].values[0]
        #check if floor exists
        if xiq_building_exist == True:
            filt = (location_df['type'] == 'FLOOR') & (location_df['parent'] == building_name)
            floor_df = location_df.loc[filt]
            if floor['name'] in floor_df['name'].unique():
                log_msg = f"There is already a floor with the name {floor['name']} in building {building_name}"
                sys.stdout.write(YELLOW)
                sys.stdout.write(log_msg + '\n')
                sys.stdout.write(RESET)
                print("Each floor has to have a unique name. Skipping creating this floor.")
                response = yesNoLoop("Would you like to continue and place APs on floor that is already created?")
                if response == 'n':
                    sys.stdout.write(RED)
                    sys.stdout.write("script is exiting....\n")
                    sys.stdout.write(RESET)
                    logger.info(f"User selected to not place APs on existing floor {floor['name']}.")
                    raise SystemExit
                else:
                    logger.info(log_msg + " that will be used.")
                    filt = floor_df['name'] == floor['name']
                    floor['xiq_floor_id'] = floor_df.loc[filt, 'id'].values[0]
                    continue

        # upload floorplan image
        if 'FILE_TOO_BIG_' in floor['map_name']:
            filename = floor['map_name'].replace("FILE_TOO_BIG_","")
            floor['map_name'] = ''
            log_msg = f"The image file for floor '{floor['name']}' is too big to upload using the API. Please upload {filename} located in the app/images folder and assign it to the floor."
            logger.error(log_msg)
            sys.stdout.write(YELLOW)
            sys.stdout.write(log_msg + '\n')
            sys.stdout.write(RESET)
            saveImages = True
        if " " in floor['map_name']:
            oldFileName = imageFilePath + floor['map_name']
            floor['map_name'] = floor['map_name'].replace(" ", "")
            newFileName = imageFilePath + floor['map_name']
            os.rename(oldFileName, newFileName)

        if floor['map_name']:
            print(f"Uploading {floor['map_name']} to XIQ.... ", end='')
            sys.stdout.flush()
            x.uploadFloorplan(floor['map_name'],floor['name'])
            time.sleep(10)
            print("Completed\n")

        
        # get data for floor
        data = floor.copy()
        del data['associated_building_id']
        del data['floor_id']
        del data['xiq_floor_id']
        data['parent_id'] = xiq_building_id
        if len(data['name']) > 32:
            data['name'] = checkNameLength(data['name'], type='floor')
        floor['xiq_floor_id'] = x.createFloor(data)
        if floor['xiq_floor_id'] != 0:
            sys.stdout.write(GREEN)
            sys.stdout.write(f"Floor {floor['name']} was successfully created.\n\n")
            sys.stdout.write(RESET)
        
else:
    for floor in rawData['floors']:
        if floor['associated_building_id'] != None:
            log_msg = ("Fatal Error with buildings and floors")
            logger.error(log_msg)
            sys.stdout.write(RED)
            sys.stdout.write(log_msg + '\n')
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
        # upload floorplan image
        print(f"Uploading {floor['map_name']} to XIQ.... ", end='')
        sys.stdout.flush()
        x.uploadFloorplan(floor['map_name'], floor['name'])
        time.sleep(10)
        print("Completed\n")
        # get data for floor
        data = floor.copy()
        del data['associated_building_id']
        del data['floor_id']
        del data['xiq_floor_id']
        data['parent_id'] = rawData['building'][0]['xiq_building_id']
        floor['xiq_floor_id'] = x.createFloor(data)
        if floor['xiq_floor_id'] != 0:
            log_msg = (f"Floor {floor['name']} was successfully created.")
            sys.stdout.write(GREEN)
            sys.stdout.write(f"Floor {floor['name']} was successfully created.\n\n")
            sys.stdout.write(RESET)
            logger.info(log_msg)        


# ADD APS TO FLOORS
ek_floor_df = pd.DataFrame(rawData['floors'])
ek_ap_df = pd.DataFrame(rawData['aps'])
# change location_id to xiq_floor_id
listOfFloors = list(ek_ap_df['location_id'].unique())
for floor_id in listOfFloors:
    filt = ek_floor_df['floor_id'] == floor_id
    xiq_id = (ek_floor_df.loc[filt,'xiq_floor_id'].values[0])
    ek_ap_df = ek_ap_df.replace({'location_id':{floor_id : str(xiq_id)}})
# get list of serial numbers
ek_ap_df['sn'].replace('', np.nan, inplace=True)
duplicateSN = ek_ap_df['sn'].dropna().duplicated().any()
if duplicateSN:
    log_msg = ("\nMultiple APs have the same serial numbers. Please fix and try again.")
    logger.warning(log_msg)
    sys.stdout.write(RED)
    sys.stdout.write(log_msg + '\n')
    sys.stdout.write("script is exiting....")
    sys.stdout.write(RESET)
    raise SystemExit
nanValues = ek_ap_df[ek_ap_df['sn'].isna()]
listOfSN = list(ek_ap_df['sn'].dropna().unique())
if nanValues.name.size > 0 and len(listOfSN) == 0:
    log_msg = ("Serial numbers were not found for any AP. Please check to make sure they are added correctly and try again.")
    logger.warning(log_msg)
    sys.stdout.write(YELLOW)
    sys.stdout.write("\n"+log_msg + '\n')
    print("script is exiting....")
    sys.stdout.write(RESET)
    raise SystemExit
elif nanValues.name.size > 0:
    print("\nSerial numbers were not found for these APs. Please correct and run the script again if you would like to add them.\n  ", end='')
    print(*nanValues.name.values, sep = "\n  ")
    logger.info("Serial numbers were not found for these APs: " + ",".join(nanValues.name.values))

# Batch serial numbers 

sizeofbatch = 100
if len(listOfSN) > sizeofbatch:
    sys.stdout.write(YELLOW)
    sys.stdout.write("\nThis script will work in batches of 100 APs.\n\n")
    sys.stdout.write(RESET)

apsToConfigure = []
for i in range(0, len(listOfSN),sizeofbatch):
    batch = listOfSN[i:i+sizeofbatch]
    cleanBatch = listOfSN[i:i+sizeofbatch]
    apSNFound = False
    # check if they exist 
    existingAps = x.checkApsBySerial(batch) 
    for ap in existingAps:
        batch = list(filter(lambda a: a != ap['serial_number'], batch))
        updateApWithId(ap)
    
    subtracted = [i for i in cleanBatch if i not in batch]
    if subtracted:
        print("\nThese AP serial numbers already exist:\n  ", end='')
        print(*subtracted, sep = "\n  ")
        logger.info("These AP serial numbers already exist: " + ",".join(subtracted))
        response = yesNoLoop("Would you like to move these existing APs to the floorplan?")
        if response == 'n':
            logger.info("User selected not to move these APs as they already existed.")
        elif response == 'y':
            logger.info("User selected to move these APs anyways.")
            apsToConfigure.extend(subtracted)
            apSNFound = True
    cleanBatch = batch
    # if new APs onboard
    if batch:
        print("Attempting to onboard APs... ", end='')
        sys.stdout.flush()
        data = {
            "extreme":{
                "sns" : batch
            }
        }
        response = x.onboardAps(data)
        time.sleep(10)
        if response != 'Success':
            print("Failed")
            print("\nfailed to onboard APs with these serial numbers:\n  ", end='')
            print(*batch, sep = "\n  ")
            logger.error("Failed to onboard APs " + ",".join(batch))
            continue
        existingAps = x.checkApsBySerial(batch)
        for ap in existingAps:
            batch = list(filter(lambda a: a != ap['serial_number'], batch))
            updateApWithId(ap)
        if batch:
            print("Failed")
            sys.stdout.write(YELLOW)
            sys.stdout.write("\nThese AP serial numbers were not able to be onboarded at this time. Please check the serial numbers and try again.\n")
            sys.stdout.write(RESET)
            print("  ", end='')
            print(*batch, sep='\n  ')
            logger.warning(f"These APs could not be added. " + ",".join(batch))
            subtracted = [i for i in cleanBatch if i not in batch]
            if subtracted:
                print("\nThe following AP successfully onboarded:\n  ", end='')
                print(*subtracted, sep='\n  ')
                logger.info("These AP serial numbers successfully onboarded: " + ",".join(subtracted))
                response = yesNoLoop("Would you like to continue and move these APs to the floorplan?")
                if response == 'n':
                    logger.info("User selected not to move these APs as they already existed.")
                    continue
                elif response == 'y':
                    logger.info("User selected to move these onboarded APs.")
                    apsToConfigure.extend(subtracted)
        else:
            apsToConfigure.extend(cleanBatch)
            print("Complete")

    elif apSNFound == False and cleanBatch:
        sys.stdout.write(YELLOW)
        sys.stdout.write("There were no new APs found in this batch.\n")
        sys.stdout.write(RESET)
        logger.info("There were no new APs found in this batch.")
        response = yesNoLoop("Would you like to move these existing APs to the floorplan?")
        if response == 'n':
            logger.info("User selected not to move these APs as they already existed.")
            continue
        elif response == 'y':
            logger.info("User selected to move these APs anyways.")
            apsToConfigure.extend(subtracted)


print("Starting to rename APs and move them")
for ap_sn in apsToConfigure:
    filt = ek_ap_df['sn'] == ap_sn
    ap_df = ek_ap_df[filt]
    # rename AP
    response = x.renameAP(ap_df['xiq_id'].values[0], ap_df['name'].values[0])
    if response != "Success":
        log_msg = f"Failed to change name of {ap_df['xiq_id'].values[0]}"
        sys.stdout.write(RED)
        sys.stdout.write(log_msg + '\n')
        sys.stdout.write(RESET)
        logger.error(log_msg)
    else:
        logger.info(f"Changed name of AP to {ap_df['name'].values[0]}")
    data = {
        "location_id" : ap_df['location_id'].values[0],
        "x" : ap_df['x'].values[0],
        "y" : ap_df['y'].values[0],
        "latitude": 0,
        "longitude": 0
    }
    response = x.changeAPLocation(ap_df['xiq_id'].values[0], data)
    if response != "Success":
        log_msg = (f"Failed to set location of {ap_df['xiq_id'].values[0]}")
        print(log_msg)
        logging.error(log_msg)
    else:
        logger.info(f"Set location for {ap_df['name'].values[0]}")

print("Finished renaming APs and moving them")

if saveImages == False:
    shutil.rmtree(imageFilePath)

