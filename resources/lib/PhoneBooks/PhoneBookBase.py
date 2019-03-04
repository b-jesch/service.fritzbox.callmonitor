from abc import ABCMeta, abstractmethod
from six import with_metaclass

class PhoneBookBase(with_metaclass(ABCMeta)):
    _imagepath = None
    _imagecount = None

    def __init__(self, imagepath):
        self._imagepath = imagepath
        self._imagecount = 0

    class HostUnreachableException(Exception):
        pass

    class LoginFailedException(Exception):
        pass

    class RequestFailedException(Exception):
        pass

    class InternalServerErrorException(Exception):
        pass

    class IOErrorException(Exception):
        pass

    @abstractmethod
    def set_settings(self, settings):
        pass

    @abstractmethod
    def get_setting_keys(self):
        pass

    @abstractmethod
    def imagecount(self):
        pass

    @abstractmethod
    def getPhonebook(self, pbid=None):
        """resultformat: #
        {'contact name': {'numbers': ['123', '456'], 'imageURL': 'http...', 'imageBMP': 'imagepath'}, ...}
        """
        pass
