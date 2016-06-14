import sys
import os

# This code uses a slight modified of pyicloud
# https://github.com/picklepete/pyicloud

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "pyicloud"))
sys.path.append(os.path.join(base_dir, "pyicloud", "vendorlibs"))

from PhoneBookBase import PhoneBookBase
from pyicloud import PyiCloudService


class AppleCloud(PhoneBookBase):
    def __init__(self, imagepath, user=None, password=None):
        PhoneBookBase.__init__(self, imagepath)
        self._user = user
        self._password = password
        self._useAppleCloud = True
        self._count = 0

    def set_settings(self, settings):
        self._password = False if len(settings['icloud_password']) == 0 else settings['icloud_password']
        self._user = False if len(settings['icloud_user']) == 0 else settings['icloud_user']
        self._useAppleCloud = True if settings['use_icloud'].upper() == 'TRUE' else False

    def get_setting_keys(self):
        return {
            'use_icloud': None,
            'icloud_user': None,
            'icloud_password': None
        }

    def getPhonebook(self):
        if not self._useAppleCloud: return {}
        result = {}
        api = PyiCloudService(self._user, self._password)
        for contact in api.contacts.all():
            numbers = []
            phones = contact.get('phones')
            if phones is None: continue
            for number in phones:
                numbers.append(number['field'])
            result[self._getName(contact)] = {'numbers': numbers}
            self._count = len(result)
        return result

    def _getName(self, contact):
        result = ""
        if contact.get('firstName') is not None:
            result += contact.get('firstName') + " "
        if contact.get('lastName') is not None:
            result += contact.get('lastName')
        return result

    def imagecount(self):
        if not self._useAppleCloud: return 0
        return self._count


if __name__ == '__main__':
    args = {'user': None, 'pw': None}
    try:
        if sys.argv[1]:
            for parameter in sys.argv[1:]:
                item, value = parameter.lstrip('-').split('=')
                args[item] = value
            phone_book = AppleCloud(imagepath='', user=args['user'], password=args['pw'])
            result = phone_book.getPhonebook()
            for p in result:
                print(p + " - " + str(result[p]['numbers']))
            print(str(phone_book.imagecount()) + " numbers")

    except IndexError:
        print("python AppleCloud.py --user=<user> --pw=<password>")
