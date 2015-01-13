#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import urllib, urllib2

APIKEY = 'NDM2MDg5Yjc4YmI2MWIzZTI0NDQyYzI4YzY2NGJkMjI=\n'
APIURL = 'http://openapi.klicktel.de/searchapi/invers'

class KlickTelReverseSearch:

    class ResultException(Exception): pass
    class HostCommException(Exception): pass
    class KlickTelModuleException(Exception): pass

    def __init__(self):
        self.data = None
        self.__apikey = APIKEY
        self.__apiurl = APIURL
        self.__number = None
        
    def search(self, arg):
        if 'number' in arg:
            self.__number = arg['number'][0]
        else:
            self.__number = arg
        __o = True if 'dump' in arg and arg['dump'][0] == '1' else False
        __params = urllib.urlencode({'key': self.__apikey.decode('base64'), 'number': self.__number})
        try:
            response = urllib2.urlopen('%s?%s' % (self.__apiurl, __params))
            self.data = json.loads(response.read())

            if __o:
                print '>>>>'
                print json.dumps(self.data, sort_keys=False, indent=4)
                print '<<<<'

            if self.data['response'] and 'error' in self.data['response']:
                raise self.ResultException(self.data['response']['error']['message'])
            elif self.data['response']['results']:
                __total = self.data['response']['results'][0]['total']
                if __total > 1:
        			raise self.ResultException('more than one match (%s in total)' % (__total))
                else:
                    record = self.data['response']['results'][0]['entries'][0]
                    if  record['entrytype'] == 'private':
                    	return '%s %s' %(record['firstname'], record['lastname'])
                    else:
                    	return '%s' % (record['lastname'])
            else:
                raise self.ResultException('no matches')
        except urllib2.URLError as e:
            raise self.HostCommException(e.reason)
        return False

if __name__ == '__main__':

    import sys
    from collections import defaultdict

    args = defaultdict(list)
    try:
        for par, value in ((par.lstrip('-'), value) for par, value in (arg.split('=') for arg in sys.argv[1:])):
            args[par].append(value)
        kt = KlickTelReverseSearch()
        result = kt.search(args)
        if result: print result
        
    except ValueError, e:
        print e
        print 'use KlickTel.py --number=004903008154711 [--dump=0|1]'
    except Exception, e:
        print e