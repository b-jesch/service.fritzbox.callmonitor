#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import socket
import xml.sax
import requests
from requests.auth import HTTPDigestAuth
from PhoneBookBase import PhoneBookBase
from .. import tools
import xbmc

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
                if name == "imageURL":
                    self.phone_book[self.contact_name]['imageBMP'] = ''
                self.key = name

            # noinspection PyUnusedLocal
            def endElement(self, name):
                self.key = None
                self.imageURL = None

            def characters(self, content):
                if self.key == "realName":
                    self.contact_name = content
                    if not self.contact_name in self.phone_book:
                        self.phone_book[self.contact_name] = {'numbers': []}
                if self.contact_name in self.phone_book:
                    if self.key == "number":
                        self.phone_book[self.contact_name]['numbers'].append(content)
                    if self.key == "imageURL":
                        self.phone_book[self.contact_name]['imageBMP'] += content

        handler = FbAbHandler(self)
        xml.sax.parseString(xml_phonebook, handler=handler)
        for item in handler.phone_book:
            if handler.phone_book[item].get('imageBMP', False):
                self.cacheImages(handler.phone_book[item]['imageBMP'].replace('"', '&quot;'), handler.phone_book[item]['numbers'])
        return handler.phone_book

    def cacheImages(self, url, numbers):

        # mask log output
        _n = []
        _mn = []

        for number in numbers:
            _mn.append(tools.mask(number))
            _n.append(re.sub('\D', '', number.replace('+', '00')))

        tools.writeLog('Cache picture for %s from %s' % (', '.join(_mn), url))
        try:
            response = requests.get(self.__url_file_download[self._encrypt].format(
                host=self._host,
                imageurl=url,
                sid=self.__sid),
                verify=False
            )
            if response.status_code == 200:
                pb_image = response.content
                for number in _n:
                    with open(os.path.join(self._imagepath, number), 'w') as fh: fh.write(pb_image)
                    self._imagecount += 1
        except IOError as e:
            tools.writeLog('IOError: %s' % str(e), xbmc.LOGERROR)
            raise self.IOErrorException(e)
        except Exception as e:
            tools.writeLog('unhandled global Exception: %s' % str(e), xbmc.LOGERROR)
            raise self.InternalServerErrorException(e)

    def getPhonebookList(self):

        try:
            response = requests.post(self.__url_contact[self._encrypt].format(host=self._host),
                                     auth=HTTPDigestAuth(self._user, self._password),
                                     data=self.__soapenvelope_phonebooklist,
                                     headers={'Content-Type': 'text/xml; charset="utf-8"',
                                              'SOAPACTION': self.__soapaction_phonebooklist},
                                     verify=False)

        except socket.error as e:
            tools.writeLog('Socket error: %s' % str(e.message), xbmc.LOGERROR)
            raise self.HostUnreachableException()
        except requests.exceptions.ConnectionError as e:
            tools.writeLog('Connection error: %s' % str(e.message), xbmc.LOGERROR)
            raise self.HostUnreachableException()
        except Exception as e:
            tools.writeLog('unhandled global Exception: %s' % str(e.message), xbmc.LOGERROR)
            raise self.RequestFailedException()
        else:
            if response.status_code == 200:
                response = response.content
                phonbook_ids = []

                for this_line in re.findall(r'<NewPhonebookList>([\d,]*)</NewPhonebookList>', response.decode('utf-8')):
                    for this_id in this_line.split(','):
                        phonbook_ids.append(int(this_id))

                return list(set(phonbook_ids))
            elif response.status_code == 401:
                tools.writeLog('401 - Forbidden', xbmc.LOGERROR)
                raise self.LoginFailedException()
            else:
                tools.writeLog('Request failed with status code: %s' % response.status_code, xbmc.LOGERROR)
                raise self.RequestFailedException()

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
            tools.writeLog('Socket error: %s' % str(e.message), xbmc.LOGERROR)
            raise self.HostUnreachableException()
        except requests.exceptions.ConnectionError as e:
            tools.writeLog('Connection error: %s' % str(e.message), xbmc.LOGERROR)
            raise self.HostUnreachableException()
        except Exception as e:
            tools.writeLog('unhandled global Exception: %s' % str(e.message), xbmc.LOGERROR)
            raise self.RequestFailedException()
        else:
            if response.status_code == 200:
                response = response.content
                phonbook_urls = re.findall(r'<NewPhonebookURL>(.*)</NewPhonebookURL>', response.decode('utf-8'))
                sids = re.findall(r'sid=([0-9a-fA-F]*)', response.decode('utf-8'))
                if not len(sids):
                    raise self.LoginFailedException()
                self.__sid = sids[0]
            elif response.status_code == 401:
                tools.writeLog('401 - Forbidden', xbmc.LOGERROR)
                raise self.LoginFailedException()
            else:
                tools.writeLog('Request failed with status code: %s' % response.status_code, xbmc.LOGERROR)
                raise self.RequestFailedException()

        try:
            response = requests.get(phonbook_urls[0], verify=False)
        except socket.error as e:
            tools.writeLog('Socket error: %s' % str(e.message), xbmc.LOGERROR)
            raise self.HostUnreachableException()
        except IOError as e:
            tools.writeLog('IOError: %s' % str(e.message), xbmc.LOGERROR)
            raise self.HostUnreachableException()
        except Exception as e:
            tools.writeLog('unhandled global Exception: %s' % str(e.message), xbmc.LOGERROR)
            raise self.RequestFailedException()
        else:
            xml_phonebook = response.content

        return self.__analyzeFritzboxPhonebook(xml_phonebook)
