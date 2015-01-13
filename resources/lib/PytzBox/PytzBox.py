#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import socket
import xml.sax
import requests
from requests.auth import HTTPDigestAuth

class PytzBox:
    __password = False
    __host = False
    __user = False
    __sid = None
    __sslverify = False

    __url_contact = 'https://{host}:49443/upnp/control/x_contact'
    __url_file_download = 'https://{host}:49443{imageurl}&sid={sid}'
    __soapaction_phonebooklist = 'urn:dslforum-org:service:X_AVM-DE_OnTel:1#GetPhonebookList'
    __soapenvelope_phonebooklist = '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetPhonebookList xmlns:u="urn:dslforum-org:service:X_AVM-DE_OnTel:1"></u:GetPhonebookList></s:Body></s:Envelope>'
    __soapaction_phonebook = 'urn:dslforum-org:service:X_AVM-DE_OnTel:1#GetPhonebook'
    __soapenvelope_phonebook = '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:GetPhonebook xmlns:u="urn:dslforum-org:service:X_AVM-DE_OnTel:1"><NewPhonebookId>{NewPhonebookId}</NewPhonebookId></u:GetPhonebook></s:Body></s:Envelope>'

    class BoxUnreachableException(Exception): pass
    class LoginFailedException(Exception): pass
    class RequestFailedException(Exception): pass

    def __init__(self, password=False, host="fritz.box", username=False):

        socket.setdefaulttimeout(10)

        self.__password = password
        self.__host = host
        self.__user = username

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
                if self.key == "number":
                    if self.contact_name in self.phone_book:
                        self.phone_book[self.contact_name]['numbers'].append(content)
                if self.key == "imageURL":
                    if self.contact_name in self.phone_book:
                        self.phone_book[self.contact_name]['imageURL'] = content
                        self.phone_book[self.contact_name]['imageHttpURL'] = self.parent.getDownloadUrl(content)

        handler = FbAbHandler(self)

        try:
            xml.sax.parseString(xml_phonebook, handler=handler)
        except Exception, e:
            raise ValueError('could not parse phonebook data (are you logged in?): %s' % str(e))

        return handler.phone_book

    def getDownloadUrl(self, imageurl):
        try:
            return self.__url_file_download.format(
                host=self.__host,
                imageurl=imageurl,
                sid=self.__sid
            )
        except Exception, e:
            print e

    def getPhonebookList(self):

        try:
            response = requests.post(self.__url_contact.format(host=self.__host),
                                     auth=HTTPDigestAuth(self.__user, self.__password),
                                     data=self.__soapenvelope_phonebooklist,
                                     headers={'Content-Type': 'text/xml; charset="utf-8"',
                                              'SOAPACTION': self.__soapaction_phonebooklist},
                                     verify=self.__sslverify)
        except requests.exceptions.ConnectionError, e:
            raise self.BoxUnreachableException(str(e))
        except Exception, e:
            raise self.RequestFailedException(str(e))
        else:
            if response.status_code == 200:
                response = response.content
                phonbook_ids = []

                for this_line in re.findall(r'<NewPhonebookList>([\d,]*)</NewPhonebookList>', response):
                    for this_id in this_line.split(','):
                        phonbook_ids.append(int(this_id))

                return list(set(phonbook_ids))
            elif response.status_code == 401:
                raise self.LoginFailedException()
            else:
                raise self.RequestFailedException('Request failed with status code: %s' % response.status_code)

    def getPhonebook(self, id=0):

        if id == -1:
            result = dict()
            for this_id in self.getPhonebookList():
                if this_id < 0:
                    continue
                result.update(self.getPhonebook(id=this_id))
            return result

        try:
            response = requests.post(self.__url_contact.format(host=self.__host),
                                     auth=HTTPDigestAuth(self.__user, self.__password),
                                     data=self.__soapenvelope_phonebook.format(NewPhonebookId=id),
                                     headers={'Content-Type': 'text/xml; charset="utf-8"',
                                              'SOAPACTION': self.__soapaction_phonebook},
                                     verify=self.__sslverify)
        except requests.exceptions.ConnectionError, e:
            raise self.BoxUnreachableException(str(e))
        except Exception, e:
            raise self.RequestFailedException(str(e))
        else:
            if response.status_code == 200:
                response = response.content
                phonbook_urls = re.findall(r'<NewPhonebookURL>(.*)</NewPhonebookURL>', response)
                sids = re.findall(r'sid=([0-9a-fA-F]*)', response)
                if not len(sids):
                    raise self.LoginFailedException()
                self.__sid = sids[0]
            elif response.status_code == 401:
                raise self.LoginFailedException()
            else:
                raise self.RequestFailedException('Request failed with status code: %s' % response.status_code)

        try:
            response = requests.get(phonbook_urls[0])
        except socket, e:
            raise self.BoxUnreachableException(str(e))
        except IOError, e:
            raise self.BoxUnreachableException(str(e))
        except Exception, e:
            raise self.RequestFailedException(str(e))
        else:
            xml_phonebook = response.content

        return self.__analyzeFritzboxPhonebook(xml_phonebook)


if __name__ == '__main__':

    import docopt
    from pprint import pprint

    __doc__ = """
    PytzBox

    usage:
      ./PytzBox.py getphonebook [--host=<fritz.box>] [--username=<user>] [--password=<pass>] [--id=<int>|--all]
      ./PytzBox.py getphonebooklist [--host=<fritz.box>] [--username=<user>] [--password=<pass>]

    options:
      --username=<user>     username usually not required
      --password=<pass>     admin password [default: none]
      --host=<fritz.box>    ip address / hostname [default: fritz.box]

    """

    arguments = docopt.docopt(__doc__)

    box = PytzBox(username=arguments['--username'], password=arguments['--password'], host=arguments['--host'])

    if arguments['getphonebook']:
        if arguments['--all']:
            phone_book_id = -1
        elif arguments['--id'] is not False:
            phone_book_id = arguments['--id']
        else:
            phone_book_id = 0
        pprint(box.getPhonebook(id=phone_book_id))
    elif arguments['getphonebooklist']:
        pprint(box.getPhonebookList())
