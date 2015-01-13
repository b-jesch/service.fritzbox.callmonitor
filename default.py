# -*- coding: utf-8 -*-

from pprint import pformat
import socket
import os
import re
import time
import datetime

import traceback
import sys

import xbmc
import xbmcaddon
import xbmcgui
from resources.lib.PytzBox import PytzBox
from resources.lib.KlickTel import KlickTel

__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('id')
__path__ = __addon__.getAddonInfo('path')
__version__ = __addon__.getAddonInfo('version')
__LS__ = __addon__.getLocalizedString

__IconOk__ = xbmc.translatePath(os.path.join( __path__,'resources', 'media', 'incoming.png'))
__IconError__ = xbmc.translatePath(os.path.join( __path__,'resources', 'media', 'error.png'))
__IconUnknown__ = xbmc.translatePath(os.path.join( __path__,'resources', 'media', 'unknown.png'))
__IconKlickTel__ = xbmc.translatePath(os.path.join( __path__,'resources', 'media', 'klicktel.png'))
__IconDefault__ = xbmc.translatePath(os.path.join( __path__,'resources', 'media', 'default.png'))

# Fritz!Box

LISTENPORT = 1012

# other

PLAYER = xbmc.Player()
OSD = xbmcgui.Dialog()

# CLASSES

class PlayerProps():
    
    def __init__(self):
        self.getConditions()
        
    def getConditions(self):
        self.isPlayTV = xbmc.getCondVisibility('Pvr.isPlayingTv')
        self.isPlayMedia = xbmc.getCondVisibility('Player.HasMedia') and xbmc.getCondVisibility('Player.Playing')
        self.isPause = xbmc.getCondVisibility('Player.Paused')
        self.isMute = xbmc.getCondVisibility('Player.Muted')

class XBMCMonitor(xbmc.Monitor):

    def __init__(self, *args, **kwargs):
        xbmc.Monitor.__init__(self)
        self.SettingsChanged = False

    def onSettingsChanged(self):
        self.SettingsChanged = True

    def onScreensaverActivated(self):
        self.ScreensaverActive = True
        
    def onScreensaverDeactivated(self):
        self.ScreensaverActive = False

class FritzCallmonitor(PlayerProps, XBMCMonitor):
    __pytzbox = None
    __fb_phonebook = None
    __klicktel = None
    __kt_name = None
    __hide = None

    def __init__(self):

        self.PlayerProps = PlayerProps()
        self.PlayerOnIC = None
        XBMCMonitor.__init__(self)
        self.getSettings()
        self.getPhonebook()

        self.ScreensaverActive = xbmc.getCondVisibility('System.ScreenSaverActive')
        
    def error(*args, **kwargs):
        xbmc.log('%s %s' % (args, kwargs), xbmc.LOGERROR)

    class CallMonitorLine(dict):

        def __init__(self, line, **kwargs):
            if isinstance(line, str) or isinstance(line, unicode):
                token = line.split(';')
                try:
                    self['date'] = datetime.datetime.strptime(token[0].strip(), '%d.%m.%y %H:%M:%S')
                except TypeError:
                    self['date'] = datetime.datetime(*(time.strptime(token[0].strip(), '%d.%m.%y %H:%M:%S')[0:6]))

                self.command = token[1]
                self['connection_id'] = token[2]

                if self.command == 'CALL':
                    self['extension'] = token[3]
                    self['number_used'] = token[4]
                    self['number_called'] = token[5]
                    self['sip'] = token[6]

                elif self.command == 'RING':
                    self['date'] = token[0]
                    self['number_caller'] = token[3]
                    self['number_called'] = token[4]
                    self['sip'] = token[5]

                elif self.command == 'CONNECT':
                    self['date'] = token[0]
                    self['extension'] = token[3]
                    self['number'] = token[4]

                elif self.command == 'DISCONNECT':
                    self['date'] = token[0]
                    self['duration'] = token[3]

        def __getattr__(self, item):
            if item in self:
                return self[item]
            else:
                return False
                
    # END OF CLASS CallMonitorLine #

    # Get the Addon-Settings

    def getSettings(self):

        self.__server = __addon__.getSetting('phoneserver')
        __exnums = __addon__.getSetting('excludeNums')

        # transform possible userinput from e.g. 'p1, p2,,   p3 p4  '
        # to a list like this: ['p1','p2','p3','p4']

        __exnums = __exnums.replace(',', ' ')
        __exnums = __exnums.join(' '.join(line.split()) for line in __exnums.splitlines())
        self.__exnum_list = __exnums.split(' ')

        self.__dispMsgTime = int(re.match('\d+', __addon__.getSetting('dispTime')).group())*1000
        self.__fbUserName = False if len(__addon__.getSetting('fbUsername')) == 0 else __addon__.getSetting('fbUsername')
        self.__fbPasswd = False if len(__addon__.getSetting('fbPasswd')) == 0 else __addon__.getSetting('fbPasswd')

        # BOOLEAN CONVERSIONS

        self.__optShowOutgoing = True if __addon__.getSetting('showOutgoingCalls').upper() == 'TRUE' else False
        self.__optMute = True if __addon__.getSetting('optMute').upper() == 'TRUE' else False
        self.__optPause = True if __addon__.getSetting('optPause').upper() == 'TRUE' else False
        self.__optPauseTV = True if __addon__.getSetting('optPauseTV').upper() == 'TRUE' else False
        self.__usePhoneBook = True if __addon__.getSetting('usePhonebook').upper() == 'TRUE' else False
        self.__useKlickTelReverse = True if __addon__.getSetting('useKlickTelReverse').upper() == 'TRUE' else False
        
    # Get the Phonebook

    def getPhonebook(self, force = False):

        if self.__usePhoneBook:
            if self.__pytzbox is None or force: self.__pytzbox = PytzBox.PytzBox(password=self.__fbPasswd, host=self.__server, username=self.__fbUserName)
            if self.__fb_phonebook is None:
                self.__fb_phonebook = self.__pytzbox.getPhonebook(id = -1)
                self.notifyLog('Getting %s entries from %s' % (len(self.__fb_phonebook), self.__server))

    def compareNumbers(self, a, b):
        a = unicode(a).strip()
        b = unicode(b).strip()

        a = unicode(re.sub('[^0-9]*', '', a))
        b = unicode(re.sub('[^0-9]*', '', b))

        if a.startswith('00'): a = a[4:]
        a = a.lstrip('0')

        if b.startswith('00'): b = b[4:]
        b = b.lstrip('0')

        a = a[-len(b):]
        b = b[-len(a):]

        return (a == b)

    def getNameByKlickTel(self, request_number):
    
        if self.__useKlickTelReverse:
            if self.__klicktel is None:
            
                self.__klicktel = KlickTel.KlickTelReverseSearch()
                try:
                    if self.__kt_name is None: self.__kt_name = self.__klicktel.search(request_number)
                    return self.__kt_name
                except Exception, e:
                    self.notifyLog(str(e), xbmc.LOGERROR)
        return False
            
    def getRecordByNumber(self, request_number):

        if self.__usePhoneBook:
            if isinstance(self.__fb_phonebook, dict):
                for item in self.__fb_phonebook:
                    if 'numbers' in self.__fb_phonebook[item]:
                        for number in self.__fb_phonebook[item]['numbers']:
                            if self.compareNumbers(number, request_number):
                                self.notifyLog('Match an entry in database for %s' % (request_number))
                                if 'imageHttpURL' in self.__fb_phonebook[item]:
                                    self.notifyLog('There\'s an icon in database, getting it')
                                    self.notifyLog('Force login to prevent session timeouts', xbmc.LOGNOTICE)
                                    self.getPhonebook(force = True)
                                    image = self.__fb_phonebook[item]['imageHttpURL']
                                else:
                                    image = ''
                                return {'name': item, 'imageURL': image}
        return {'name': '', 'imageURL': ''}
        
    def isExcludedNumber(self, exnum):
        self.__hide = False
        if exnum in self.__exnum_list:
            self.notifyLog('%s is excluded from monitoring, do not notify...' % (exnum))
            self.__hide = True
        return self.__hide

    def handleOutgoingCall(self, line):
        if not self.isExcludedNumber(line.number_used):
            if self.__optShowOutgoing:
                record = self.getRecordByNumber(line.number_called)
                name = __LS__(30012) if record['name'] == '' else record['name']
                icon = __IconDefault__ if record['imageURL'] == '' else record['imageURL']
                self.notifyOSD(__LS__(30013), __LS__(30014) % (name, line.number_called), icon)
            self.notifyLog('Outgoing call from %s to %s' % (line.number_used, line.number_called))

    def handleIncomingCall(self, line):
        if not self.isExcludedNumber(line.number_called):
            if len(line.number_caller) > 0:
                caller_num = line.number_caller
                self.notifyLog('trying to resolve name from incoming number %s' % (caller_num))
                record = self.getRecordByNumber(caller_num)
                name = record['name']
                icon = __IconOk__ if record['imageURL'] == '' else record['imageURL']
                if not name:
                    name = self.getNameByKlickTel(caller_num)
                    if name:
                        icon = __IconKlickTel__
                    else:
                        icon = __IconUnknown__
                        name = __LS__(30012)
            else:
                name = __LS__(30012)
                caller_num = __LS__(30016)
                icon = __IconUnknown__

            self.PlayerOnIC = self.PlayerProps
            self.PlayerOnIC.getConditions()
            self.notifyOSD(__LS__(30010), __LS__(30011) % (name, caller_num), icon)
            self.notifyLog('Incoming call from %s (%s)' % (name, caller_num))

    def handleConnected(self, line):
        self.notifyLog('Line connected')
        if not self.__hide:
            if self.PlayerOnIC is not None:           
                if self.__optPause and not self.PlayerOnIC.isPause:
                    if self.__optPauseTV and self.PlayerOnIC.isPlayTV:
                        self.notifyLog('Player is playing TV, pausing...')
                        PLAYER.pause()
                    elif self.PlayerOnIC.isPlayMedia and not self.PlayerOnIC.isPlayTV:
                        self.notifyLog('Player is playing Video/Audio, pausing...')
                        PLAYER.pause()
    
                if self.__optMute and not self.PlayerOnIC.isMute:
                    if not self.__optPause or (not self.__optPauseTV and self.PlayerOnIC.isPlayTV):
                        self.notifyLog('Muting Volume...')
                        xbmc.executebuiltin('Mute')

    def handleDisconnected(self, line):
        self.notifyLog('Line disconnected')
        if not self.__hide:
            if self.PlayerOnIC is not None:
                self.PlayerProps.getConditions()
                if self.__optPause and self.PlayerProps.isPause and (self.PlayerOnIC.isPlayMedia or self.PlayerOnIC.isPlayTV):
                    self.notifyLog('Resume Play...')
                    PLAYER.pause()
                elif self.PlayerOnIC.isPause and not self.PlayerProps.isPause:
                    self.notifyLog('Play Property changed between connect and disconnect, do nothing...')
                if self.__optMute and self.PlayerProps.isMute:
                    self.notifyLog('Unmute...')
                    xbmc.executebuiltin('Mute')
                elif self.PlayerOnIC.isMute and not self.PlayerProps.isMute:
                    self.notifyLog('Mute Property changed between connect and disconnect, do nothing...')
        else:
            self.notifyLog('excluded number seems disconnected, reset status of callmonitor')
            self.__hide = False
        
    def notifyOSD(self, header, message, icon=__IconDefault__):
        OSD.notification(header.encode('utf-8'), message.encode('utf-8'), icon, self.__dispMsgTime)

    def notifyLog(self, message, level=xbmc.LOGNOTICE):
        xbmc.log('%s: %s' % (__addonname__, message.encode('utf-8')), level)

    def traceError(self, e, exc_tb):
        while exc_tb:
            tb = traceback.format_tb(exc_tb)
            self.notifyLog('%s' % e, xbmc.LOGERROR)
            self.notifyLog('In module: %s' % sys.argv[0].strip() or '<not defined>', xbmc.LOGERROR)
            self.notifyLog('At line:   %s' % traceback.tb_lineno(exc_tb), xbmc.LOGERROR)
            self.notifyLog('In file:   %s' % tb[0].split(",")[0].strip()[6:-1],xbmc.LOGERROR)
            exc_tb = exc_tb.tb_next
        
    def start(self):

        try:
            __s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            __s.settimeout(60)
            __s.connect((self.__server, LISTENPORT))
        except Exception, e:
            self.notifyOSD(__LS__(30030), __LS__(30031) % (self.__server, LISTENPORT), __IconError__)
            self.notifyLog('Could not connect to %s:%s' % (self.__server, LISTENPORT), xbmc.LOGERROR)
            self.traceError(e, sys.exc_traceback)
            # self.notifyLog(pformat(e), xbmc.LOGERROR)
            # __s.close()
            self.notifyLog('Monitoring aborted')
        else:
            self.notifyLog('listen to %s on port %s' % (self.__server, LISTENPORT))
            __s.settimeout(0.2)

            # MAIN SERVICE
            
            while not xbmc.abortRequested:

                try:
                    fbdata = __s.recv(512)
                    line = self.CallMonitorLine(fbdata)

                    {
                        'CALL': self.handleOutgoingCall,
                        'RING': self.handleIncomingCall,
                        'CONNECT': self.handleConnected,
                        'DISCONNECT': self.handleDisconnected
                    }.get(line.command, self.error)(line)

                except socket.timeout:
                    pass
                except IndexError:
                    self.notifyLog('Something went wrong with messages from Fritzbox...', xbmc.LOGERROR)
                except socket.error, e:
                    self.notifyLog('Could not connect to %s:%s' % (self.__server, LISTENPORT), xbmc.LOGERROR)
                    self.notifyLog(pformat(e), xbmc.LOGERROR)
                    xbmc.sleep(10000)
                except Exception, e:
                    self.traceError(e, sys.exc_traceback)
                    # self.notifyLog(pformat(e), xbmc.LOGERROR)

                if self.SettingsChanged:
                    self.notifyLog('Settings changed, perform update')
                    self.getSettings()
                    self.SettingsChanged = False
                    self.getPhonebook()
                    
                xbmc.sleep(200)
                

            __s.close()
            self.notifyLog('Monitoring finished')

# START

CallMon = FritzCallmonitor()
CallMon.start()
del CallMon
