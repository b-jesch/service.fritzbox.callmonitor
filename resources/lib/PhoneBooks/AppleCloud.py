import os
import sys

# This code uses a slight modified of pyicloud
# https://github.com/picklepete/pyicloud

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, "pyicloud"))
sys.path.append(os.path.join(base_dir, "pyicloud", "vendorlibs"))

import hashlib

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

    def getPhonebook(self, id=None):
        if not self._useAppleCloud: return {}
        result = {}
        api = PyiCloudService(self._user, self._password)
        for contact in api.contacts.all():
            numbers = []
            phones = contact.phones
            if phones is None: continue
            for number in phones:
                numbers.append(number['field'])
            key = self._getName(contact)
            result[key] = {'numbers': numbers}
            self._download_image(contact, result, key)
        return result

    def _download_image(self, contact, phone_entry, key):
        if contact.hasPicture and self._imagepath is not None:
            stream = contact.download()
            imagepath = os.path.join(self._imagepath,
                                     hashlib.md5(key.encode('utf-8')).hexdigest() + '.jpg')
            with open(imagepath, 'wb') as f:
                for chunk in stream.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            phone_entry[key]['imageBMP'] = imagepath
            self._count += 1

    def _getName(self, contact):
        result = ""
        if contact.firstName is not None:
            result += contact.firstName + " "
        if contact.lastName is not None:
            result += contact.lastName
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
                entry = result[p]
                print("%s - %s %s" % (p, entry['numbers'],
                                      entry['imageBMP'] if 'imageBMP' in entry else ''))
            print(str(phone_book.imagecount()) + " caller images")

    except IndexError:
        print("python AppleCloud.py --user=<user> --pw=<password>")
