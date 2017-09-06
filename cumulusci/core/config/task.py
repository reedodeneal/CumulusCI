import base64
import datetime
import json
import logging
import os
import pickle
import re

from collections import OrderedDict

import hiyapyco
import raven
import sarge
from simple_salesforce import Salesforce
import yaml
import requests


from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module
from github3 import login
from cumulusci.core.config.base import BaseConfig


class TaskConfig(BaseConfig):
    """ A task with its configuration merged """
    pass
