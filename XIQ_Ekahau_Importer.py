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
from pprint import pprint as pp
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


def _create_char_spinner():
    """Creates a generator yielding a char based spinner.
    """
    while True:
        for character in '|/-\\':
            yield character

_spinner = _create_char_spinner()

def spinner(label=''):
    """Prints label with a spinner.

    When called repeatedly from inside a loop this prints
    a one line CLI spinner.
    """
    sys.stdout.write("\r%s %s  " % (label, next(_spinner)))
    sys.stdout.flush()

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


def getParentSite(building="new"):
    # Get Parent Site
    print("Each building needs to be part of a site in XIQ.")
    response = yesNoLoop(f"Would you like to use an existing Site for the {building} building?")
    if response == 'y':
        validResponse = False
        while validResponse != True:
            count = 0
            countmap = {}
            print("Which Site would you like the building to be under?")
            for site_id, site_info in Site_df.iterrows():
                countmap[count] = site_id
                print(f"   {count}. {site_info['name']}")
                count+=1
            print(f"   {count}. Create a new Site")
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
                site_id = (Site_df.loc[countmap[selection],'id'])
                site_name = (Site_df.loc[countmap[selection],'name'])
            elif selection == count:
                validResponse = True
                filt = location_df['type'] == 'Global'
                parent_id = location_df.loc[filt, 'id'].values[0]
                site_id, site_name = createSite(parent_id)
    elif response == 'n':
        filt = location_df['type'] == 'Global'
        parent_id = location_df.loc[filt, 'id'].values[0]
        site_id, site_name = createSite(parent_id)
    return site_id, site_name

def selectSite_group(parent_id):
    response = yesNoLoop(f"Would you like to use an existing Site Group for the new Site?")
    if response == 'y':
        validResponse = False
        while validResponse != True:
            count = 0
            countmap = {}
            print("Which Site Group would you like the Site to be under?")
            for site_group_id, site_group_info in site_group_df.iterrows():
                countmap[count] = site_group_id
                print(f"   {count}. {site_group_info['name']}")
                count+=1
            print(f"   {count}. Create a new Site Group")
            count += 1
            print(f"   {count}. Cancel. Do not create a Site Group")
            selection = input(f"Please enter 0 - {count}: ")
            try:
                selection = int(selection)
            except:
                sys.stdout.write(YELLOW)
                sys.stdout.write("Please enter a valid response!!\n")
                sys.stdout.write(RESET)
                continue
            if 0 <= selection < count -1:
                validResponse = True
                location_id = (site_group_df.loc[countmap[selection],'id'])
            elif selection == count -1:
                validResponse = True
                location_id = createSiteGroup(parent_id)
            elif selection == count:
                validResponse = True
                location_id = parent_id
    elif response == 'n':
        location_id = createSiteGroup(parent_id)
    return location_id

def createSiteGroup(parent_id):
    validResponse = False
    while validResponse != True:
        print("Each site group, site, and building will have to have a unique name.")
        site_group_name = input("What would you like the name of this Site Group to be? ")
        if site_group_name in location_df['name'].unique():
            filt = location_df['name'] == site_group_name
            type = location_df.loc[filt,'type'].values[0]
            sys.stdout.write(YELLOW)
            sys.stdout.write(f"\nThis name exists already as a {type}. Please enter a new site group name.\n") 
            sys.stdout.write(RESET)
            continue
        elif site_group_name.lower() == 'quit':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
        elif not site_group_name.strip():
            print("\nPlease enter a new site group name.\n") 
            continue
        site_group_name = checkNameLength(site_group_name, type='site')
        print(f"\nSite group '{site_group_name}' will be created.")
        response = yesNoLoop("Would you like to proceed?")
        if response == 'y':
            validResponse = True
            data = {"parent_id": parent_id, "name": site_group_name}
        elif response == 'n':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
    siteGroupId = x.createLocation(site_group_name, data)
    if siteGroupId != 0:
        log_msg = (f"Site {site_group_name} was successfully created.")
        sys.stdout.write(GREEN)
        sys.stdout.write(log_msg+'\n\n')
        sys.stdout.write(RESET)
        logger.info(log_msg)
    return siteGroupId


def createSite(parent_id):
    response = yesNoLoop(f"Would you like to add the new Site to a Site Group?")
    if response == 'y':
        parent_id = selectSite_group(parent_id)
    validResponse = False
    while validResponse != True:
        print("Each site group, site, and building will have to have a unique name.")
        site_name = input("What would you like the name of this Site to be? ")
        if site_name in location_df['name'].unique():
            filt = location_df['name'] == site_name
            type = location_df.loc[filt,'type'].values[0]
            sys.stdout.write(YELLOW)
            sys.stdout.write(f"\nThis name exists already as a {type}. Please enter a new site name.\n") 
            sys.stdout.write(RESET)
            continue
        elif site_name.lower() == 'quit':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
        elif not site_name.strip():
            print("\nPlease enter a new site name.\n") 
            continue
        site_name = checkNameLength(site_name, type='site')
        response = yesNoLoop("Is this Site in the US? ")
        if response == 'y':
            country_code = 840
        else:
            validResponse = False
            alpha_list = x.collectCountries()
            while not validResponse:
                alpha_code = input("Please enter the 2 character abbreviation for the country you would like to use. ")
                cc = [d for d in alpha_list if d['alpha2_code'] == alpha_code.upper()]
                if cc:
                    print(f"Country '{cc[0]['alpha2_code']} - {cc[0]['short_name']} - {cc[0]['country_code']}' was found.")
                    response = yesNoLoop('Is this correct? ')
                    if response == 'y':
                        country_code = cc[0]['country_code']
                        validResponse = True
                else:
                    print(f"'{alpha_code}' is an invalid response.")
                    response = yesNoLoop("Would you like to see a list of valid responses?")
                    if response == 'y':
                        cdata = [{d['alpha2_code']:d['short_name']} for d in alpha_list]
                        for country in cdata:
                            print(country)
        print(f"\nSite '{site_name}' will be created.")
        response = yesNoLoop("Would you like to proceed?")
        if response == 'y':
            validResponse = True
            data = {"parent_id": parent_id, "name": site_name, "country_code":country_code }
        elif response == 'n':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit
    siteId = x.createSite(site_name, data)
    if siteId != 0:
        log_msg = f"Site {site_name} was successfully created."
        sys.stdout.write(GREEN)
        sys.stdout.write(log_msg+'\n\n')
        sys.stdout.write(RESET)
        logger.info(log_msg)
    return siteId, site_name

def createBuildingInfo(site_id, site_name):
    validResponse = False
    while validResponse != True:
        print("Each site group, site, and building will have to have a unique name.")
        building_name = input("What would you like the name of the building to be? ")
        if building_name in location_df['name'].unique():
            filt = location_df['name'] == building_name
            type = location_df.loc[filt,'type'].values[0]
            sys.stdout.write(YELLOW)
            sys.stdout.write(f"\nThis name already exists as a {type}. Please enter a new building name.\n\n") 
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
        building_name = checkNameLength(building_name, type='building')
        address_response = yesNoLoop("Would you like to add an address for the building?")
        if address_response == 'y':
            state = input("What state is the building in? ")
            city = input("Which city is the building in? ")
            address = input("What is the street address for the building? ")
            postal_code = input("What is the postal code for the building? ")
            building_address = {
                "address": address,
                "city": city,
                "state": state,
                "postal_code": postal_code
            }
        else:
            building_address = {
                            "address": "Unknown",
                            "city": "Unknown",
                            "state": "Unknown",
                            "postal_code": "Unknown"
                        }
        print(f"\n\nBuilding '{building_name}' with address '{', '.join(building_address.values())}' will be created under location '{site_name}'.")
        response = yesNoLoop("Would you like to proceed?")
        if response == 'y':
            validResponse = True
            data = {"parent_id": site_id, "name": building_name, "address": building_address}
            return data
        elif response == 'n':
            sys.stdout.write(RED)
            sys.stdout.write("script is exiting....\n")
            sys.stdout.write(RESET)
            raise SystemExit

def getNPFromList():
    data = x.collectNetworkPolicies()
    if data['total_count'] > 10:
        print("There are more than 10 network policies, please search by name.")
        np_id = getNPByName()
    else:
        validResponse = False
        while validResponse != True:
            count = 0
            countmap = {}
            print("Which Network Policy would you like to use?")
            for npolicy in data['data']:
                countmap[count] = npolicy['id']
                print(f"{count} - {npolicy['name']}")
                count+=1
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
                np_id = countmap[selection]
    return np_id


def getNPByName():
    np_found = False
    while not np_found:
        np_name = input("Please enter the name of the Network Policy for the APs: ")
        np_data = x.checkNetworkPolicy(np_name)
        if np_data['total_count'] != 1:
            print(f"There were {np_data['total_count']} Network Policies found with name '{np_name}'. Please enter the full network policy name and try again.")
        else:
            np_found = True
            return np_data['data'][0]['id']


def updateApWithId(ap):
    global ek_ap_df
    filt = ek_ap_df['sn'] == ap['serial_number']
    ek_ap_df.loc[filt,'xiq_id'] = ap['id']


## EKAHAU IMPORT
filename = str(input("Please enter the Ekahau File: ")).strip()
#filename = "Mayflower.esx"
filename = filename.replace("\\ ", " ")
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
filt = location_df['type'] == 'SITE'
Site_df = location_df.loc[filt]
filt = location_df['type'] == 'Site_Group'
site_group_df = location_df.loc[filt]

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
                site_id, site_name = getParentSite()
                data = createBuildingInfo(site_id,site_name)
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
                site_id, site_name = getParentSite()
                data = createBuildingInfo(site_id,site_name)
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
                site_id, site_name = getParentSite(building=building['name'])
                del data['building_id']
                del data['xiq_building_id']
                if not data['address'].strip():
                    data['address'] = {
                            "address": "Unknown",
                            "city": "Unknown",
                            "state": "Unknown",
                            "postal_code": "Unknown"
                        }
                data['parent_id'] = f"{site_id}"
                if data['name'] in building_df['name'].unique() or data['name'] in Site_df['name'].unique():
                    print(f"{data['name']} has the same name as an existing sites. Buildings must have a unique name from other buildings and sites.")
                    data = createBuildingInfo(site_id,site_name)
                elif len(data['name']) > 32:
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
            site_id, site_name = getParentSite(building=building['name'])
            del data['building_id']
            del data['xiq_building_id']
            if not data['address']:
                data['address'] = {
                            "address": "Unknown",
                            "city": "Unknown",
                            "state": "Unknown",
                            "postal_code": "Unknown"
                        }
            data['parent_id'] = f"{site_id}"
            if data['name'] in Site_df['name'].unique():
                print(f"{data['name']} has the same name as an existing sites. Buildings must have a unique name from other buildings and sites.")
                data = createBuildingInfo(site_id,site_name)
            elif len(data['name']) > 32:
                data['name'] = checkNameLength(data['name'], type='building')
            building['xiq_building_id'] = x.createBuilding(data)
            if building['xiq_building_id'] != 0:
                log_msg = f"Building {building['name']} was successfully created."
                sys.stdout.write(GREEN)
                sys.stdout.write(log_msg+'\n\n')
                sys.stdout.write(RESET)
                logger.info(log_msg)
            
    
if xiq_building_exist == False and ekahau_building_exists == False: 
    site_id, site_name = getParentSite()
    data = createBuildingInfo(site_id,site_name)
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


# Select Network Policy to use for devices
validResponse = False
while validResponse != True:
    print("Would you like to select a network policy or search for a network policy?")
    print("0 - Select from a list")
    print("1 - Search by name")
    selection = input(f"Please enter 0 - 1: ")
    try:
        selection = int(selection)
    except:
        sys.stdout.write(YELLOW)
        sys.stdout.write("Please enter a valid response!!\n")
        sys.stdout.write(RESET)
        continue
    if selection == 0:
        np_id = getNPFromList()
        validResponse = True
    elif selection == 1:
        np_id = getNPByName()
        validResponse = True
    else:
        sys.stdout.write(YELLOW)
        sys.stdout.write("Please enter a valid response!!\n")
        sys.stdout.write(RESET)


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
ek_ap_df['sn'] = ek_ap_df['sn'].replace('', np.nan)
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
ek_ap_df.dropna(subset=["sn"], inplace=True)
# End script if no APs have serial numbers
if nanValues.name.size > 0 and len(ek_ap_df['sn'].tolist()) == 0:
    log_msg = ("\nSerial numbers were not found for any AP. Please check to make sure they are added correctly and try again.")
    logger.warning(log_msg)
    sys.stdout.write(YELLOW)
    sys.stdout.write("\n"+log_msg + '\n')
    print("script is exiting....")
    sys.stdout.write(RESET)
    raise SystemExit
# remove APs that do not have serial numbers
elif nanValues.name.size > 0:
    print("\nSerial numbers were not found for these APs. Please correct and run the script again if you would like to add them.\n  ", end='')
    print(*nanValues.name.values, sep = "\n  ")
    logger.info("Serial numbers were not found for these APs: " + ",".join(nanValues.name.values))

# Build AP data
onboard_list = []
for ap_id, ap_info in ek_ap_df.iterrows():
    data = {
        "serial_number": ap_info['sn'],
        "location": {
            "location_id": ap_info['location_id'],
            "x": ap_info['x'],
            "y": ap_info['y'],
            "latitude": 0,
            "longitude": 0
        },
        "network_policy_id": np_id,
        "hostname": ap_info['name']
    }
    onboard_list.append(data)

# Check number of APs onboarding
if len(onboard_list) > 30:
    print("\nWith more the 30 APs onboarding, Long-running operation will be used.")
    payload = {"extreme": onboard_list,
               "unmanaged": False
               }
    lro_url = x.advanceOnboardAPs(payload,lro=True)
    lro_result = 'PENDING'
    while lro_result != 'SUCCEEDED':
        data = x.checkLRO(lro_url)
        lro_result = data['metadata']['status']
        print(f"\nThe long running operation's result is {lro_result}")
        if lro_result != 'SUCCEEDED':
            print("Script will sleep for 30 secs and check again.")
            t = 120
            while t > 0:
                spinner()
                time.sleep(.25)
                t -= 1
            sys.stdout.write("\r  ")
            sys.stdout.flush()
    response = data['response']

        
else:
    payload = {"extreme": onboard_list,
               "unmanaged": False
               }
    response = x.advanceOnboardAPs(payload)
    
# Log successes
if "success_devices" in response:
    print("\nThe following devices were onboarded successfully:")
    for device in response['success_devices']:
        log_msg = f"Device {device['serial_number']} successfully onboarded created with id: {device['device_id']}"
        print(log_msg)
        logger.info(log_msg)

if "failure_devices" in response:
    fd_df = pd.DataFrame(response['failure_devices'])
    error_list = fd_df['error'].unique()
    for error in error_list:
        filt = fd_df['error'] == error
        serials = fd_df.loc[filt,'serial_number'].values
        if error == 'DEVICE_EXISTED':
            print("\nThe following AP are already onboard in this XIQ instance:\n  ", end='')
            print(*serials, sep='\n  ')
            logger.warning("These AP serial numbers are already onboarded in this XIQ instance: " + ",".join(serials))
            #response = yesNoLoop("Would you like to move these existing APs to the floorplan?")
        elif error == 'EXIST_IN_REDIRECT':
            print("\nTThese AP serial numbers were not able to be onboarded at this time as the serial numbers belong to another XIQ instance. Please check the serial numbers and try again:\n  ", end='')
            print(*serials, sep='\n  ')
            logger.warning("These AP serial numbers are already onboarded in this XIQ instance: " + ",".join(serials))
        elif error == 'PRODUCT_TYPE_NOT_EXIST':
            print("\nThese AP serial numbers are not valid. Please check serial numbers and try again:\n ", end='')
            print(*serials, sep='\n  ')
            logger.warning("These AP serial numbers are not valid: " + ",".join(serials))
        else:
            print(f"\nThese AP serial numbers failed to onboard with the error '{error}':")
            print(*serials, sep='\n  ')
            logger.warning(f"These AP serial numbers failed to onboard with '{error}': " + ",".join(serials)) 


if saveImages == False:
    shutil.rmtree(imageFilePath)

