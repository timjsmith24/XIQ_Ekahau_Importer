#!/usr/bin/env python3
import logging
import os
import time

PATH = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
	filename='{}/map_importer.log'.format(PATH),
	filemode='a',
	level=os.environ.get("LOGLEVEL", "INFO"),
	format= '{}: %(name)s - %(levelname)s - %(message)s'.format(time.strftime("%Y-%m-%d %H:%M"))
)

logger = logging.getLogger('MapImporter')