#!/usr/bin/env python3
from email import header
import logging
import os
import inspect
from socketserver import BaseRequestHandler
import sys
import json
from xmlrpc.client import APPLICATION_ERROR
from numpy import isin
from prompt_toolkit import Application
import requests
import pandas as pd
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir) 
from requests.exceptions import HTTPError
from mapImportLogger import logger

logger = logging.getLogger('MapImporter.xiq_exporter')

PATH = current_dir

class XIQ:
    def __init__(self, user_name, password):
        self.URL = "https://api.extremecloudiq.com"
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        self.totalretries = 5
        self.locationTree_df = pd.DataFrame(columns = ['id', 'name', 'type', 'parent'])
        try:
            self.__getAccessToken(user_name, password)
        except ValueError as e:
            print(e)
            raise SystemExit
        except HTTPError as e:
           print(e)
           raise SystemExit
        except:
            log_msg = "Unknown Error: Failed to generate token for XIQ"
            logger.error(log_msg)
            print(log_msg)
            raise SystemExit 

    #API CALLS
    def __setup_get_api_call(self, info, url):
        success = 0
        for count in range(1, self.totalretries):
            try:
                response = self.__get_api_call(url=url)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed to {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        if 'error' in response:
            if response['error_mssage']:
                log_msg = (f"Status Code {response['error_id']}: {response['error_message']}")
                logger.error(log_msg)
                print(f"API Failed {info} with reason: {log_msg}")
                print("Script is exiting...")
                raise SystemExit
        return response
        
    def __setup_post_api_call(self, info, url, payload):
        success = 0
        for count in range(1, self.totalretries):
            try:
                response = self.__post_api_call(url=url, payload=payload)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        if 'error' in response:
            if response['error_mssage']:
                log_msg = (f"Status Code {response['error_id']}: {response['error_message']}")
                logger.error(log_msg)
                print(f"API Failed {info} with reason: {log_msg}")
                print("Script is exiting...")
                raise SystemExit
        return response
    
    def __setup_put_api_call(self, info, url, payload=''):
        success = 0
        for count in range(1, self.totalretries):
            try:
                if payload:
                    self.__put_api_call(url=url, payload=payload)
                else:
                    self.__put_api_call(url=url)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed to {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        
        return 'Success'


    def __get_api_call(self, url):
        try:
            response = requests.get(url, headers= self.headers)
        except HTTPError as http_err:
            logger.error(f'HTTP error occurred: {http_err} - on API {url}')
            raise ValueError(f'HTTP error occurred: {http_err}') 
        if response is None:
            log_msg = "ERROR: No response received from XIQ!"
            logger.error(log_msg)
            raise ValueError(log_msg)
        if response.status_code != 200:
            log_msg = f"Error - HTTP Status Code: {str(response.status_code)}"
            logger.error(f"{log_msg}")
            logger.warning(f"\t\t{response}")
            raise ValueError(log_msg)  
        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error(f"Unable to parse json data - {url} - HTTP Status Code: {str(response.status_code)}")
            raise ValueError("Unable to parse the data from json, script cannot proceed")
        return data

    def __post_api_call(self, url, payload):
        try:
            response = requests.post(url, headers= self.headers, data=payload)
        except HTTPError as http_err:
            logger.error(f'HTTP error occurred: {http_err} - on API {url}')
            raise ValueError(f'HTTP error occurred: {http_err}') 
        if response is None:
            log_msg = "ERROR: No response received from XIQ!"
            logger.error(log_msg)
            raise ValueError(log_msg)
        if response.status_code == 202:
            return "Success"
        elif response.status_code != 200:
            log_msg = f"Error - HTTP Status Code: {str(response.status_code)}"
            logger.error(f"{log_msg}")
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.warning(f"\t\t{response.text()}")
            else:
                if 'error_message' in data:
                    logger.warning(f"\t\t{data['error_message']}")
                    raise Exception(data['error_message'])
            raise ValueError(log_msg)
        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error(f"Unable to parse json data - {url} - HTTP Status Code: {str(response.status_code)}")
            raise ValueError("Unable to parse the data from json, script cannot proceed")
        return data
    
    def __put_api_call(self, url, payload=''):
        try:
            if payload:
                response = requests.put(url, headers= self.headers, data=payload)
            else:
                response = requests.put(url, headers= self.headers)
        except HTTPError as http_err:
            logger.error(f'HTTP error occurred: {http_err} - on API {url}')
            raise ValueError(f'HTTP error occurred: {http_err}') 
        if response is None:
            log_msg = "ERROR: No response received from XIQ!"
            logger.error(log_msg)
            raise ValueError(log_msg)
        if response.status_code != 200:
            log_msg = f"Error - HTTP Status Code: {str(response.status_code)}"
            logger.error(f"{log_msg}")
            logger.warning(f"\t\t{response}")
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.warning(f"\t\t{response.text()}")
            else:
                if 'error_message' in data:
                    logger.warning(f"\t\t{data['error_message']}")
                    raise Exception(data['error_message'])
                raise ValueError(log_msg)
        return response.status_code

    def __image_api_call(self, url, files):
        headers = self.headers.copy()
        del headers['Content-Type']
        try:
            response = requests.post(url, headers= headers, files=files)
        except HTTPError as http_err:
            logger.error(f'HTTP error occurred: {http_err} - on API {url}')
            raise ValueError(f'HTTP error occurred: {http_err}') 
        if response is None:
            log_msg = "ERROR: No response received from XIQ!"
            logger.error(log_msg)
            raise ValueError(log_msg)
        if response.status_code != 200:
            log_msg = f"Error - HTTP Status Code: {str(response.status_code)}"
            logger.error(f"{log_msg}")
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.warning(f"\t\t{response.text()}")
            else:
                if 'error_message' in data:
                    logger.warning(f"\t\t{data['error_message']}")
                    raise Exception(data['error_message'])
            raise ValueError(log_msg)
        return 1

    def __getAccessToken(self, user_name, password):
        info = "get XIQ token"
        success = 0
        url = self.URL + "/login"
        payload = json.dumps({"username": user_name, "password": password})
        for count in range(1, self.totalretries):
            try:
                data = self.__post_api_call(url=url,payload=payload)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed to get XIQ token. Cannot continue to import")
            print("exiting script...")
            raise SystemExit
        
        if "access_token" in data:
            #print("Logged in and Got access token: " + data["access_token"])
            self.headers["Authorization"] = "Bearer " + data["access_token"]
            return 0

        else:
            log_msg = "Unknown Error: Unable to gain access token for XIQ"
            logger.warning(log_msg)
            raise ValueError(log_msg)
    
    # EXTERNAL ACCOUNTS
    def __getVIQInfo(self):
        info="get current VIQ name"
        success = 0
        url = "{}/account/home".format(self.URL)
        for count in range(1, self.totalretries):
            try:
                data = self.__get_api_call(url=url)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print(f"Failed to {info}")
            return 1
            
        else:
            self.viqName = data['name']
            self.viqID = data['id']


    #BUILDINGS
    def __buildLocationDf(self, location, pname = 'Global'):
        if 'parent_id' not in location:
            temp_df = pd.DataFrame([{'id': location['id'], 'name':location['name'], 'type': 'Global', 'parent':pname}])
            self.locationTree_df = pd.concat([self.locationTree_df, temp_df], ignore_index=True)
        else:
            temp_df = pd.DataFrame([{'id': location['id'], 'name':location['name'], 'type': location['type'], 'parent':pname}])
            self.locationTree_df = pd.concat([self.locationTree_df, temp_df], ignore_index=True)
        r = json.dumps(location['children'])
        if location['children']:
            parent_name = location['name']
            for child in location['children']:
                self.__buildLocationDf(child, pname=parent_name)


    ## EXTERNAL FUNCTION

    #ACCOUNT SWITCH
    def selectManagedAccount(self):
        self.__getVIQInfo()
        info="gather accessible external XIQ acccounts"
        success = 0
        url = "{}/account/external".format(self.URL)
        for count in range(1, self.totalretries):
            try:
                data = self.__get_api_call(url=url)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print(f"Failed to {info}")
            return 1
            
        else:
            return(data, self.viqName)


    def switchAccount(self, viqID, viqName):
        info=f"switch to external account {viqName}"
        success = 0
        url = "{}/account/:switch?id={}".format(self.URL,viqID)
        payload = ''
        for count in range(1, self.totalretries):
            try:
                data = self.__post_api_call(url=url, payload=payload)
            except ValueError as e:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"API to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"API to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("failed to get XIQ token to {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        
        if "access_token" in data:
            #print("Logged in and Got access token: " + data["access_token"])
            self.headers["Authorization"] = "Bearer " + data["access_token"]
            self.__getVIQInfo()
            if viqName != self.viqName:
                logger.error(f"Failed to switch external accounts. Script attempted to switch to {viqName} but is still in {self.viqName}")
                print("Failed to switch to external account!!")
                print("Script is exiting...")
                raise SystemExit
            return 0

        else:
            log_msg = "Unknown Error: Unable to gain access token for XIQ"
            logger.warning(log_msg)
            raise ValueError(log_msg) 
        

    # LOCATIONS
    def gatherLocations(self):
        info=f"gather location tree"
        url = "{}/locations/tree".format(self.URL)
        response = self.__setup_get_api_call(info,url)
        for location in response:
            self.__buildLocationDf(location)
        return (self.locationTree_df)

    def createLocation(self, location_name, data):
        info=f"create location '{location_name}'"
        url = "{}/locations".format(self.URL)
        payload = json.dumps(data)
        response = self.__setup_post_api_call(info,url,payload)
        return response['id']


    
    #BUILDINGS
    def createBuilding(self, data):
        info=f"create building '{data['name']}'"
        url = "{}/locations/building".format(self.URL)
        payload = json.dumps(data)
        response = self.__setup_post_api_call(info, url, payload)
        return response['id']

    #FLOORS
    def uploadFloorplan(self, filename, floorname):
        info=f"upload file '{filename}'"
        success = 0
        url = "{}/locations/floorplan".format(self.URL)
        filepathname = PATH + f"/images/{filename}"
        files={
            'file' : (f'{filename}', open(filepathname, 'rb'), 'image/png'),
            'type': 'image/png'
        }
        for count in range(1, self.totalretries):
            try:
                self.__image_api_call(url=url, files=files)
            except ValueError as e:
                print(f"\nAPI to {info} failed attempt {count} of {self.totalretries} with {e}")
            except Exception as e:
                print(f"\nAPI to {info} failed with {e}")
                print('script is exiting...')
                raise SystemExit
            except:
                print(f"\nAPI to {info} failed attempt {count} of {self.totalretries} with unknown API error")
            else:
                success = 1
                break
        if success != 1:
            print("\nfailed to {}. Cannot continue to import".format(info))
            print("exiting script...")
            raise SystemExit
        else:
            logger.info(f"Successfully uploaded {filename} for {floorname}")

    def createFloor(self, data):
        info=f"create floor '{data['name']}'"
        url = "{}/locations/floor".format(self.URL)
        payload = json.dumps(data)
        response = self.__setup_post_api_call(info,url,payload)
        return response['id']

    #APS
    def checkApsBySerial(self, listOfSerials):
        info="check APs by Serial Number"
        url = "{}/devices?limit=100&sns=".format(self.URL)
        snurl = "&sns=".join(listOfSerials)
        url = url + snurl
        response = self.__setup_get_api_call(info, url)
        return(response['data'])

    def onboardAps(self, data):
        info="onboard APs"
        url = "{}/devices/:onboard".format(self.URL)
        payload = json.dumps(data)
        response = self.__setup_post_api_call(info,url,payload)
        return response

    def renameAP(self, ap_id, name):
        info="rename AP '{}'".format(ap_id)
        url = f"{self.URL}/devices/{ap_id}/hostname?hostname={name}"
        response = self.__setup_put_api_call(info,url)
        return response

    def changeAPLocation(self, ap_id, data):
        info="set location for AP '{}'".format(ap_id)
        payload = json.dumps(data)
        url = f"{self.URL}/devices/{ap_id}/location"
        response = self.__setup_put_api_call(info,url,payload=payload)
        return response
