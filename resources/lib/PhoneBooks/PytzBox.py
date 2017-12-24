#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
import os
import re
import socket
import xml.sax
import requests
from requests.auth import HTTPDigestAuth
from PhoneBookBase import PhoneBookBase

class PytzBox(PhoneBookBase):
    _password = False
    _host = False
    _user = False
    _encrypt = None
    _usePhoneBook = None
    _phoneBookId = None

    __sid = None
    __url_contact = ['https://{host}:49443/upnp/control/x_contact', 'http://{host}:49000/upnp/control/x_contact']
    __url_file_download = ['https://{host}:49443{imageurl}&sid={sid}', 'http://{host}:49000{imageurl}&sid={sid}']
    __soapaction_phonebooklist = 'urn:dslforum-org:service:X_AVM-DE_OnTel:1#GetPhonebookList'
    __soapenvelope_phonebooklist = '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetPhonebookList xmlns:u="urn:dslforum-org:service:X_AVM-DE_OnTel:1"></u:GetPhonebookList></s:Body></s:Envelope>'
    __soapaction_phonebook = 'urn:dslforum-org:service:X_AVM-DE_OnTel:1#GetPhonebook'
    __soapenvelope_phonebook = '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetPhonebook xmlns:u="urn:dslforum-org:service:X_AVM-DE_OnTel:1"><NewPhonebookId>{NewPhonebookId}</NewPhonebookId></u:GetPhonebook></s:Body></s:Envelope>'

    def __init__(self, imagepath):
        PhoneBookBase.__init__(self, imagepath)
        socket.setdefaulttimeout(10)

    def set_settings(self, settings):
        self._password = False if len(settings['fbPasswd']) == 0 else settings['fbPasswd']
        self._host = settings['phoneserver']
        self._user = False if len(settings['fbUsername']) == 0 else settings['fbUsername']
        self._encrypt = 0 if settings['fbSSL'].upper() == 'TRUE' else 1
        self._usePhoneBook = True if settings['usePhonebook'].upper() == 'TRUE' else False
        self._phoneBookId = -1 if settings['phoneBookID'].upper() == 'TRUE' else 0

    def get_setting_keys(self):
        return {
            'fbPasswd': None,
            'fbSSL': None,
            'phoneserver': None,
            'fbUsername': None,
            'usePhonebook': None,
            'phoneBookID': None
        }

    def imagecount(self):
        return 0 if not self._usePhoneBook else self._imagecount

    def __analyzeFritzboxPhonebook(self, xml_phonebook):

        class FbAbHandler(xml.sax.ContentHandler):

            def __init__(self, parent):
                self.contact_name = ""
                self.key = None
                self.parent = parent
                self.phone_book = dict()

            # noinspection PyUnusedLocal
            def startElement(self, name, args):
                if name == "contact":
                    self.contact_name = ""
                self.key = name

            # noinspection PyUnusedLocal
            def endElement(self, name):
                self.key = None

            def characters(self, content):
                if self.key == "realName":
                    self.contact_name = content
                    if not self.contact_name in self.phone_book:
                        self.phone_book[self.contact_name] = {'numbers': []}
                if self.contact_name in self.phone_book:
                    if self.key == "number": self.phone_book[self.contact_name]['numbers'].append(content)
                    if self.key == "imageURL": self.phone_book[self.contact_name]['imageBMP'] = self.parent.getImage(content, self.contact_name)

        handler = FbAbHandler(self)
        xml.sax.parseString(xml_phonebook, handler=handler)
        return handler.phone_book

    def getImage(self, url, caller_name):

        try:
            response = requests.post(self.__url_file_download[self._encrypt].format(
                host=self._host,
                imageurl=url,
                sid=self.__sid),
                verify=False
            )
            caller_image = response.content
            if caller_image is not None:
                imagepath = os.path.join(self._imagepath, hashlib.md5(caller_name.encode('utf-8')).hexdigest() + '.jpg')
                with open(imagepath, 'w') as fh: fh.write(caller_image)
                self._imagecount += 1
                return imagepath
        except IOError, e:
            raise self.RequestFailedException(e.message)
        except Exception, e:
            raise self.InternalServerErrorException(e.message)

    def getPhonebookList(self):

        try:
            response = requests.post(self.__url_contact[self._encrypt].format(host=self._host),
                                     auth=HTTPDigestAuth(self._user, self._password),
                                     data=self.__soapenvelope_phonebooklist,
                                     headers={'Content-Type': 'text/xml; charset="utf-8"',
                                              'SOAPACTION': self.__soapaction_phonebooklist},
                                     verify=False)

        except socket.error as e:
            raise self.HostUnreachableException(str(e))
        except requests.exceptions.ConnectionError as e:
            raise self.HostUnreachableException(str(e))
        except Exception as e:
            raise self.RequestFailedException(str(e))
        else:
            if response.status_code == 200:
                response = response.content
                phonbook_ids = []

                for this_line in re.findall(r'<NewPhonebookList>([\d,]*)</NewPhonebookList>', response.decode('utf-8')):
                    for this_id in this_line.split(','):
                        phonbook_ids.append(int(this_id))

                return list(set(phonbook_ids))
            elif response.status_code == 401:
                raise self.LoginFailedException()
            else:
                raise self.RequestFailedException('Request failed with status code: %s' % response.status_code)

    def getPhonebook(self, pbid=None):
        if not self._usePhoneBook: return {}
        if pbid == None: pbid = self._phoneBookId
        if pbid == -1:
            result = dict()
            for this_id in self.getPhonebookList():
                if this_id < 0: continue
                result.update(self.getPhonebook(pbid=this_id))
            return result

        try:
            response = requests.post(self.__url_contact[self._encrypt].format(host=self._host),
                                     auth=HTTPDigestAuth(self._user, self._password),
                                     data=self.__soapenvelope_phonebook.format(NewPhonebookId=pbid),
                                     headers={'Content-Type': 'text/xml; charset="utf-8"',
                                              'SOAPACTION': self.__soapaction_phonebook},
                                     verify=False)
        except socket.error as e:
            raise self.HostUnreachableException(str(e))
        except requests.exceptions.ConnectionError as e:
            raise self.HostUnreachableException(str(e))
        except Exception as e:
            raise self.RequestFailedException(str(e))
        else:
            if response.status_code == 200:
                response = response.content
                phonbook_urls = re.findall(r'<NewPhonebookURL>(.*)</NewPhonebookURL>', response.decode('utf-8'))
                sids = re.findall(r'sid=([0-9a-fA-F]*)', response.decode('utf-8'))
                if not len(sids):
                    raise self.LoginFailedException()
                self.__sid = sids[0]
            elif response.status_code == 401:
                raise self.LoginFailedException()
            elif response.status_code == 500:
                raise self.InternalServerErrorException()
            else:
                raise self.RequestFailedException('Request failed with status code: %s' % response.status_code)

        try:
            response = requests.get(phonbook_urls[0], verify=False)
        except socket.error as e:
            raise self.HostUnreachableException(str(e))
        except IOError as e:
            raise self.HostUnreachableException(str(e))
        except Exception as e:
            raise self.RequestFailedException(str(e))
        else:
            xml_phonebook = response.content

        return self.__analyzeFritzboxPhonebook(xml_phonebook)
