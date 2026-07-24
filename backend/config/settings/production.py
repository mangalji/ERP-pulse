from .base import *

DEBUG = False

from .database import PRODUCTION_DATABASE

DATABASES = {
    "default": PRODUCTION_DATABASE
}
