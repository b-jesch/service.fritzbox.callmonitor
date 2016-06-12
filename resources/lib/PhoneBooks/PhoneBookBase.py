from abc import ABCMeta, abstractmethod


class PhoneBookBase(metaclass=ABCMeta):
    _password = False
    _host = False
    _user = False
    _encrypt = None
    _imagepath = None
    _imagecount = None

    class HostUnreachableException(Exception):
        pass

    class LoginFailedException(Exception):
        pass

    class RequestFailedException(Exception):
        pass

    class InternalServerErrorException(Exception):
        pass

    def __init__(self, password=False, host="", username=False, encrypt=True, imagepath=None):
        self._password = password
        self._host = host
        self._user = username
        self._encrypt = 0 if encrypt else 1
        self._imagepath = imagepath
        self._imagecount = 0

    @abstractmethod
    def imagecount(self):
        pass

    @abstractmethod
    def compareNumbers(self, a, b, ccode):
        pass

    @abstractmethod
    def getPhonebook(self, id, imgpath):
        pass