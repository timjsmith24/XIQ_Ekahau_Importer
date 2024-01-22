#!/usr/bin/env python3
import logging
import os
from logging.handlers import RotatingFileHandler

PATH = os.path.dirname(os.path.abspath(__file__))

log_formatter = logging.Formatter('%(asctime)s: %(name)s - %(levelname)s - %(message)s')

logFile = '{}/map_importer.log'.format(PATH)

# Rotate file at 50MB
my_handler = RotatingFileHandler(logFile, mode='a', maxBytes=50*1024*1024, 
                                 backupCount=5, encoding=None, delay=0)

my_handler.setFormatter(log_formatter)
my_handler.setLevel(logging.INFO)

logger = logging.getLogger('MapImporter')
logger.setLevel(logging.INFO)

logger.addHandler(my_handler)