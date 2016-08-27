import logging
from .base import PyiCloudService

#http://stackoverflow.com/questions/33175763/how-to-use-logging-nullhandler-in-python-2-6
try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

logging.getLogger(__name__).addHandler(NullHandler())
