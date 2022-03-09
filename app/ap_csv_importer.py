#!/usr/bin/env python3
import logging
import os
import inspect
import sys
import pandas as pd
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir) 
from mapImportLogger import logger

logger = logging.getLogger('MapImporter.ap_csv_importer')

PATH = current_dir

class apSerialCSV:
    def __init__(self,filename,ap_info):
        if os.path.exists(filename):
            self.filename = filename
            self.ap_info = ap_info # import the ap dataframe created from EkahauData
        else:
            log_msg = f"File {filename} does not exist."
            logger.error(log_msg)
            print("Failed")
            print(log_msg)
            raise SystemExit
    

    def getSerialNumbers(self):
        ap_data = []
        unmatched_ap_info_ap = []
        unmatched_csv_ap = []
        try:
            csv_df = pd.read_csv(self.filename,dtype=str)
        except:
            log_msg = f"Unable to load csv file {self.filename}"
            logger.error(log_msg)
            raise ValueError(log_msg)
        for ap in self.ap_info:
            if ap['name'] in csv_df['Access Point'].values:
                filt = csv_df['Access Point'] == ap['name']
                ap['sn'] = (csv_df.loc[filt, 'Serial Number'].values[0])
            else:
                unmatched_ap_info_ap.append(ap['name'])
                log_msg = (f"{ap['name']} was not found in {self.filename}")
                logger.info(log_msg)
                continue
            ap_data.append(ap)
        for ap in csv_df['Access Point']:
            if not any(d['name'] == ap for d in self.ap_info):
                unmatched_csv_ap.append(ap)
                log_msg = (f"{ap} was found in {self.filename} but didn't match name of any known AP")
                logger.info(log_msg)
        
        return ap_data, unmatched_ap_info_ap, unmatched_csv_ap