#!/usr/bin/env python3
from math import floor
from zipfile import ZipFile
import json
import logging
import os
import inspect
import shutil
import sys
import cv2
import pandas as pd
from pprint import pprint
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir) 
from mapImportLogger import logger

logger = logging.getLogger('MapImporter.EkahauImporter')

PATH = current_dir

class Ekahau:
    def __init__(self, filename):
        self.filename = filename
        self.metersPerUnit = {}
        self.scale = 1
        self.cropRotateSupport = True

        directory = PATH + '/images'
        if os.path.isdir(directory):
            for f in os.listdir(directory):
                os.remove(os.path.join(directory, f))
        else:
            os.makedirs(directory)
        
        self.projectFolder = f"{PATH}/project"
        if os.path.exists(self.projectFolder) and os.path.isdir(self.projectFolder):
            shutil.rmtree(self.projectFolder)



    def exportFile(self):
        data = {}
        itemList = ['project', 'buildings', 'floorPlans', 'accessPoints', 'buildingFloors', 'floorTypes', 'images', 'notes', 'tagKeys', 'deviceProfiles','images']
        self.buildingexists = True
        # Unzip Ekahau folder in to a created 'project' directory
        try:
            with ZipFile(self.filename, 'r') as zip:
                zip.extractall('app/project')
        except FileNotFoundError:
            log_msg = f"{self.filename} file does not exist"
            logger.error(log_msg)
            raise ValueError(log_msg)
        except json.JSONDecodeError:
            log_msg = f"{self.filename} file is corrupted, script cannot proceed"
            logger.info(log_msg)
            shutil.rmtree(self.projectFolder)
            raise ValueError(log_msg)
        
        #Check version
        dir_list = os.listdir(self.projectFolder)
        if 'project.xml' in dir_list:
            log_msg = ("Older Ekahau file detected. Please update file using Ekahau 10.x and try again.")
            logger.error(log_msg)
            shutil.rmtree(self.projectFolder)
            raise ValueError(log_msg)
        # Import itemList json files 
        for item in itemList:
            try:
                 with open(f"{self.projectFolder}/{item}.json", 'r') as f:
                    data[item] = json.load(f)
            except FileNotFoundError:
                if item == 'buildings' or item == 'buildingFloors':
                    self.buildingexists = False
                    continue
                elif item == 'notes' or item == 'tagKeys':
                    continue
                else:
                    logger.error(f"{item}.json file does not exist")
                    raise ValueError(f"The {item} details were able to be exported from the Ekahau file")
            except json.JSONDecodeError:
                logger.info(f"{item}.json file is corrupted, script cannot proceed")
                raise ValueError(f"The {item} details from Ekahau are corrupted, script cannot proceed")
        # clean APs:

        ap_data = []
        for ap in data['accessPoints']['accessPoints']:
            if 'location' in ap:
                ap_data.append(ap)
        data['accessPoints']['accessPoints'] = ap_data

        #TODO Need to set these values - 'notes', 'tagKeys', 'deviceProfiles'
        self.project_info = data['project']['project']
        if self.buildingexists:
            self.building_df = pd.DataFrame(data['buildings']['buildings'])
            self.building_df = self.building_df.set_index('id')
        self.floorPlans_df = pd.DataFrame(data['floorPlans']['floorPlans'])
        self.floorPlans_df = self.floorPlans_df.set_index('id')
        self.ap_df = pd.DataFrame(data['accessPoints']['accessPoints'])
        self.ap_df = self.ap_df.set_index('id')
        if self.buildingexists:
            self.buildingFloors_df = pd.DataFrame(data['buildingFloors']['buildingFloors'])
            self.buildingFloors_df = self.buildingFloors_df.set_index('id')
        self.floorTypes_df = pd.DataFrame(data['floorTypes']['floorTypes'])
        self.floorTypes_df = self.floorTypes_df.set_index('id')
        self.images_df = pd.DataFrame(data['images']['images'])
        self.images_df = self.images_df.set_index('id')

        self.__versionCheck()

        self.__processEkahauData()
        shutil.rmtree(current_dir + '/project')
        return self.EkahauData
        
    def __versionCheck(self):
        if 'rotateUpDirection' not in self.floorPlans_df.columns:
            log_msg = "This Ekahau file seems to be prior to version 10.3 so crop and rotation of Floors is not supported with this script."
            logger.warning(log_msg)
            print('\n' + log_msg)
            self.floorPlans_df = self.floorPlans_df.assign(rotateUpDirection = "UP")
            self.floorPlans_df = self.floorPlans_df.assign(cropMinX = 0.0)
            self.floorPlans_df = self.floorPlans_df.assign(cropMinY = 0.0)
            self.floorPlans_df = self.floorPlans_df.assign(cropMaxX = lambda x: x.width)
            self.floorPlans_df = self.floorPlans_df.assign(cropMaxY = lambda x: x.height)


    def __floorImageProcessing(self, imageId, imageType):

        if imageType == 'bitmap':
            filt = self.floorPlans_df['bitmapImageId'] == imageId
            rawWidth = int(self.images_df.loc[imageId, 'resolutionWidth'])
            rawHeight = int(self.images_df.loc[imageId, 'resolutionHeight'])
            self.scale = rawWidth / int(self.floorPlans_df.loc[filt, 'width'].values[0])
        else:
            filt = self.floorPlans_df['imageId'] == imageId
            rawWidth = int(self.floorPlans_df.loc[filt, 'width'].values[0])
            rawHeight = int(self.floorPlans_df.loc[filt, 'height'].values[0])
        floorName = self.floorPlans_df.loc[filt, 'name'].values[0]
        imageFormat = (self.images_df.loc[imageId, 'imageFormat'])
        orientation = self.floorPlans_df.loc[filt, 'rotateUpDirection'].values[0]

        
        #if imageFormat == 'JPEG':
        fileExt = 'jpg'
        #elif imageFormat == 'PNG':
        #    fileExt = 'png'
    

        floorplan_name = f"{imageId}.{fileExt}"
        filename = f"{self.projectFolder}/image-{imageId}"
        newfilename = f"{PATH}/images/{floorplan_name}"
        try:
            file_size = os.path.getsize(filename)
        except FileNotFoundError:
            if not os.path.isfile(filename):
                log_msg = f"{filename} file does not exist"
                logger.error(log_msg)
                raise ValueError(log_msg)
            elif not os.path.isdir(PATH + '/images/'):
                log_msg = "The /images/ directory is missing in the /app/ directory."
                logger.error(log_msg)
                raise ValueError(log_msg)
        quality = 75
        if file_size > 1000000:
            quality = 50
        image = cv2.imread(filename)
        if image is None:
            log_msg = f"Script failed to read in file {filename}"
            logger.error(log_msg)
            raise ValueError(log_msg)
            
       
        #Cropping image as necessary
        minX=int(int(self.floorPlans_df.loc[filt, 'cropMinX'].values[0]) * self.scale)
        minY=int(int(self.floorPlans_df.loc[filt, 'cropMinY'].values[0]) * self.scale)
        maxX=int(int(self.floorPlans_df.loc[filt, 'cropMaxX'].values[0]) * self.scale)
        maxY=int(int(self.floorPlans_df.loc[filt, 'cropMaxY'].values[0]) * self.scale)
        #print(minY,maxY, minX,maxX)
        crop_image = image[minY:maxY, minX:maxX]
    
        #Get width and height of the floorplan
        width = (rawWidth - minX - (rawWidth -maxX)) * self.floorPlans_df.loc[filt, 'metersPerUnit'].values[0]
        height = (rawHeight - minY - (rawHeight -maxY)) * self.floorPlans_df.loc[filt, 'metersPerUnit'].values[0]

        #rotate image and width height of floorplan
        if orientation == "LEFT":
            image = cv2.rotate(crop_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            width, height = height, width
        elif orientation == "RIGHT":
            image = cv2.rotate(crop_image, cv2.ROTATE_90_CLOCKWISE)
            width, height = height, width
        elif orientation == "DOWN":
            image = cv2.rotate(crop_image, cv2.ROTATE_180) 
        elif orientation == "UP":
            image = crop_image

        #write cropped and rotated image file
        write_status = cv2.imwrite(newfilename, image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not write_status:
            log_msg = f"Failed to write {newfilename} after croping"
            logger.error(log_msg)
            raise ValueError(log_msg)
        
        file_size = os.path.getsize(newfilename)
        if file_size > 1000000:
            floorplan_name = 'FILE_TOO_BIG_' + floorplan_name
        return floorplan_name, width, height

    def __updateAPCoord(self, floor_id, rawX,rawY):
        #get correct x,y coords
        minX=int(int(self.floorPlans_df.loc[floor_id, 'cropMinX']) * self.scale)
        minY=int(int(self.floorPlans_df.loc[floor_id, 'cropMinY']) * self.scale)
        maxX=int(int(self.floorPlans_df.loc[floor_id, 'cropMaxX']) * self.scale)
        maxY=int(int(self.floorPlans_df.loc[floor_id, 'cropMaxY']) * self.scale)
        metersPerUnit = self.floorPlans_df.loc[floor_id, 'metersPerUnit']
        orientation = self.floorPlans_df.loc[floor_id, 'rotateUpDirection']
        rawX = rawX  * self.scale
        rawY = rawY  * self.scale

        if orientation == 'UP':
            x = (rawX - minX) * metersPerUnit
            y = (rawY - minY) * metersPerUnit
        elif orientation == "RIGHT":
            y = (rawX - minX) * metersPerUnit
            x = (maxY - rawY) * metersPerUnit
        elif orientation == "LEFT":
            x = (rawY - minY) * metersPerUnit
            y = (maxX - rawX) * metersPerUnit
        elif orientation == "DOWN":
            x = (maxX - rawX) * metersPerUnit
            y = (maxY - rawY) * metersPerUnit
        
        return x,y
        
    def __processEkahauData(self):

        self.EkahauData = {'building':[],'floors':[],'aps':[]}

        if self.buildingexists:
            # Building data
            for building_id, row in self.building_df.iterrows():
                data = {
                    'building_id': building_id,
                    'name': row['name'],
                    'address': self.project_info['location'],
                    'xiq_building_id' : None
                }
                self.EkahauData['building'].append(data)

        # Floor data
        for floor_id, row in self.floorPlans_df.iterrows():
            # collect needed data
            self.metersPerUnit[floor_id] = row['metersPerUnit']
            if self.buildingexists and floor_id in self.buildingFloors_df['floorPlanId'].unique():
                filt = self.buildingFloors_df['floorPlanId'] == floor_id
                floorHeight = self.buildingFloors_df.loc[filt, 'height'].values[0]
                floorThickness = self.buildingFloors_df.loc[filt, 'thickness'].values[0]
                floorTypeId = self.buildingFloors_df.loc[filt, 'floorTypeId'].values[0]
                buildingId = self.buildingFloors_df.loc[filt, 'buildingId'].values[0]
                typeFilt = self.floorTypes_df['id'] = floorTypeId
                if 'propagationProperties' in self.floorTypes_df:
                    propProperties = self.floorTypes_df.loc[typeFilt,'propagationProperties']
                    floorAttenuation = propProperties[0]['attenuationFactor'] * floorThickness
                elif 'attenuationPerMeter' in self.floorTypes_df:
                    floorAttenuation = self.floorTypes_df.loc[typeFilt, 'attenuationPerMeter'] * floorThickness
            else:
                #TODO Figure out what to do about height - 
                #TODO I could read in the simulatedRadios.json and find the 
                #TODO most frequent height? check if radio is ceiling mounted.
                floorHeight = 4
                buildingId = None
                floorAttenuation = 15

            # Change image names
            if 'bitmapImageId' in row:
                imageType = 'bitmap'
                imageId = row['bitmapImageId']
            else:
                imageType = 'regular'
                imageId = row['imageId']
            try:
                floorImageName, width, height = self.__floorImageProcessing(imageId, imageType)
            except ValueError as e:
                raise ValueError(e)

            #Floor Payload
            data = {
                "floor_id" : floor_id, 
                "associated_building_id" : buildingId,
                 "name": row['name'],
                 "environment": "AUTO_ESTIMATE",
                 "db_attenuation": str(floorAttenuation),
                 "measurement_unit": "METERS",
                "installation_height": str(floorHeight),
                "map_size_width": str(width),
                "map_size_height": str(height),
                "map_name": floorImageName,
                "xiq_floor_id" : None
            }
            self.EkahauData['floors'].append(data)
            
        for ap_id, row in self.ap_df.iterrows():
            # collect needed data
            if " : " in row['name']:
                ap_name, ap_sn = [x.strip() for x in row['name'].split(" : ")]
            else:
                ap_name = row['name']
                ap_sn = ''
            ap_floor_id = (row['location']['floorPlanId'])
            rawX = row['location']['coord']['x']
            rawY = row['location']['coord']['y']
            x,y = self.__updateAPCoord(ap_floor_id,rawX,rawY)
            
            data = {
                'xiq_id': None,
                'name' : ap_name,
                'sn' : ap_sn,
                'location_id' : ap_floor_id,
                'x' : x,
                'y' : y
            }
            self.EkahauData['aps'].append(data)