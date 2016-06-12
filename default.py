# -*- coding: utf-8 -*-

import socket
import os
import re
import traceback
import sys

import xbmc
import xbmcaddon
import xbmcgui
from resources.lib.PhoneBooks import PytzBox
from resources.lib.KlickTel import KlickTel
import hashlib

__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('id')
__path__ = __addon__.getAddonInfo('path')
__version__ = __addon__.getAddonInfo('version')
__LS__ = __addon__.getLocalizedString

__IconOk__ = xbmc.translatePath(os.path.join(__path__, 'resources', 'media', 'incoming.png'))
__IconError__ = xbmc.translatePath(os.path.join(__path__, 'resources', 'media', 'error.png'))
__IconUnknown__ = xbmc.translatePath(os.path.join(__path__, 'resources', 'media', 'unknown.png'))
__IconKlickTel__ = xbmc.translatePath(os.path.join(__path__, 'resources', 'media', 'klicktel.png'))
__IconDefault__ = xbmc.translatePath(os.path.join(__path__, 'resources', 'media', 'default.png'))

__ImageCache__ = xbmc.translatePath(os.path.join('special://temp', __addonname__, 'cache'))
if not os.path.exists(__ImageCache__): os.makedirs(__ImageCache__)

# Fritz!Box

LISTENPORT = 1012

# other

PLAYER = xbmc.Player()
OSD = xbmcgui.Dialog()


# CLASSES

class PlayerProperties:
    def __init__(self):
        self.getConditions()

    def getConditions(self):
        self.isPlayTV = xbmc.getCondVisibility('Pvr.isPlayingTv')
        self.isPlayVideo = xbmc.getCondVisibility('Player.HasVideo') and xbmc.getCondVisibility('Player.Playing')
        self.isPlayAudio = xbmc.getCondVisibility('Player.HasAudio') and xbmc.getCondVisibility('Player.Playing')
        self.isPause = xbmc.getCondVisibility('Player.Paused')
        self.isMute = xbmc.getCondVisibility('Player.Muted')

    def getConnectConditions(self):
        self.isConnectPause = xbmc.getCondVisibility('Player.Paused')
        self.isConnectMute = xbmc.getCondVisibility('Player.Muted')

    def getDisconnectConditions(self):
        self.isDisconnectPause = xbmc.getCondVisibility('Player.Paused')
        self.isDisconnectMute = xbmc.getCondVisibility('Player.Muted')


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


class FritzCallmonitor(PlayerProperties, XBMCMonitor):
    __pytzbox = None
    __fb_phonebook = None
    __klicktel = None
    __hide = None
    __s = None

    def __init__(self):

        self.PlayerProperties = PlayerProperties()
        XBMCMonitor.__init__(self)
        self.getSettings()
        self.getPhonebook()

        self.ScreensaverActive = xbmc.getCondVisibility('System.ScreenSaverActive')

        self.connectionEstablished = None
        self.userActionPlay = None
        self.userActionMute = None

    def error(*args, **kwargs):
        xbmc.log('%s %s' % (args, kwargs), xbmc.LOGERROR)

    class CallMonitorLine(dict):

        def __init__(self, line, **kwargs):
            if isinstance(line, str):

                token = line.split(';')
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

        self.__dispMsgTime = int(re.match('\d+', __addon__.getSetting('dispTime')).group()) * 1000
        self.__fbUserName = False if len(__addon__.getSetting('fbUsername')) == 0 else __addon__.getSetting(
            'fbUsername')
        self.__fbPasswd = False if len(__addon__.getSetting('fbPasswd')) == 0 else __addon__.getSetting('fbPasswd')
        self.__fbSSL = True if __addon__.getSetting('fbSSL').upper() == 'TRUE' else False
        self.__cCode = __addon__.getSetting('cCode')

        # BOOLEAN CONVERSIONS

        self.__optShowOutgoing = True if __addon__.getSetting('showOutgoingCalls').upper() == 'TRUE' else False
        self.__optMute = True if __addon__.getSetting('optMute').upper() == 'TRUE' else False
        self.__optPauseAudio = True if __addon__.getSetting('optPauseAudio').upper() == 'TRUE' else False
        self.__optPauseVideo = True if __addon__.getSetting('optPauseVideo').upper() == 'TRUE' else False
        self.__optPauseTV = True if __addon__.getSetting('optPauseTV').upper() == 'TRUE' else False
        self.__usePhoneBook = True if __addon__.getSetting('usePhonebook').upper() == 'TRUE' else False
        self.__phoneBookID = -1 if __addon__.getSetting('phoneBookID').upper() == 'TRUE' else 0
        self.__useKlickTelReverse = True if __addon__.getSetting('useKlickTelReverse').upper() == 'TRUE' else False

    # Get the Phonebook

    def getPhonebook(self):

        if self.__usePhoneBook:
            if self.__pytzbox is None: self.__pytzbox = PytzBox.PytzBox(password=self.__fbPasswd, host=self.__server,
                                                                        username=self.__fbUserName,
                                                                        encrypt=self.__fbSSL,
                                                                        imagepath=__ImageCache__)
            if self.__fb_phonebook is None:
                try:
                    self.__fb_phonebook = self.__pytzbox.getPhonebook(id=self.__phoneBookID)
                    self.notifyLog('%s entries from %s loaded, %s images cached' % (
                    len(self.__fb_phonebook), self.__server, self.__pytzbox.imagecount()))
                except self.__pytzbox.HostUnreachableException:
                    self.notifyOSD(__LS__(30030), __LS__(30031) % (self.__server, LISTENPORT), __IconError__)
                except self.__pytzbox.LoginFailedException:
                    self.notifyOSD(__LS__(30033), __LS__(30034), __IconError__)
                except self.__pytzbox.InternalServerErrorException:
                    self.notifyOSD(__LS__(30035), __LS__(30036), __IconError__)

    def getNameByKlickTel(self, request_number):

        if self.__useKlickTelReverse:
            if self.__klicktel is None: self.__klicktel = KlickTel.KlickTelReverseSearch()
            try:
                return self.__klicktel.search(request_number)
            except Exception as e:
                self.notifyLog(str(e), level=xbmc.LOGERROR)
        return False

    def getRecordByNumber(self, request_number):

        name = ''
        imageBMP = None

        if self.__usePhoneBook and isinstance(self.__fb_phonebook, dict):

            for item in self.__fb_phonebook:
                for number in self.__fb_phonebook[item]['numbers']:
                    if self.__pytzbox.compareNumbers(number, request_number, ccode=self.__cCode):
                        self.notifyLog('Match an entry in database for %s: %s' % (request_number, item))
                        name = item
                        fname = os.path.join(__ImageCache__, hashlib.md5(item.encode('utf-8')).hexdigest() + '.jpg')
                        if os.path.isfile(fname):
                            self.notifyLog('Load image from cache: %s' % (os.path.basename(fname)))
                            imageBMP = fname

        return {'name': name, 'imageBMP': imageBMP}

    def isExcludedNumber(self, exnum):
        self.__hide = False
        if exnum in self.__exnum_list:
            self.notifyLog('%s is excluded from monitoring, do not notify...' % (exnum))
            self.__hide = True
        return self.__hide

    def handleOutgoingCall(self, line):
        self.PlayerProperties.getConditions()
        self.connectionEstablished = False
        self.userActionPlay = False
        self.userActionMute = False
        if not self.isExcludedNumber(line.number_used):
            if self.__optShowOutgoing:
                record = self.getRecordByNumber(line.number_called)
                name = __LS__(30012) if record['name'] == '' else record['name']
                icon = __IconDefault__ if record['imageBMP'] == '' else record['imageBMP']
                self.notifyOSD(__LS__(30013), __LS__(30014) % (name, line.number_called), icon)
            self.notifyLog('Outgoing call from %s to %s' % (line.number_used, line.number_called))

    def handleIncomingCall(self, line):
        self.PlayerProperties.getConditions()
        self.connectionEstablished = False
        self.userActionPlay = False
        self.userActionMute = False
        if not self.isExcludedNumber(line.number_called):
            if len(line.number_caller) > 0:
                caller_num = line.number_caller
                self.notifyLog('trying to resolve name from incoming number %s' % (caller_num))
                record = self.getRecordByNumber(caller_num)
                name = record['name']
                icon = __IconOk__ if record['imageBMP'] == '' else record['imageBMP']
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

            self.notifyOSD(__LS__(30010), __LS__(30011) % (name, caller_num), icon, self.__dispMsgTime)
            self.notifyLog('Incoming call from %s (%s)' % (name, caller_num))

    def handleConnected(self, line):
        self.notifyLog('Line connected')
        if not self.__hide:
            self.PlayerProperties.getConnectConditions()
            if self.PlayerProperties.isPause != self.PlayerProperties.isConnectPause:
                self.userActionPlay = True
            if self.PlayerProperties.isMute != self.PlayerProperties.isConnectMute:
                self.userActionMute = True
            #
            # Save connection for handleDisconnected:
            # this condition determines whether the play and mute commands has to be executed again
            #
            self.connectionEstablished = True
            # Extra condition: only do this if the user hasn't changed the status of the player
            if (
                self.__optPauseAudio or self.__optPauseVideo) and not self.PlayerProperties.isPause and not self.userActionPlay:
                if self.__optPauseTV and self.PlayerProperties.isPlayTV:
                    self.notifyLog('Player is playing TV, pausing...')
                    xbmc.executebuiltin('PlayerControl(Play)')
                    # Save the status of the player for later comparison
                    self.PlayerProperties.isConnectPause = True
                elif self.__optPauseVideo and self.PlayerProperties.isPlayVideo and not self.PlayerProperties.isPlayTV:
                    self.notifyLog('Player is playing Video, pausing...')
                    xbmc.executebuiltin('PlayerControl(Play)')
                    # Save the status of the player for later comparison
                    self.PlayerProperties.isConnectPause = True
                elif self.__optPauseAudio and self.PlayerProperties.isPlayAudio and not self.PlayerProperties.isPlayTV:
                    self.notifyLog('Player is playing Audio, pausing...')
                    xbmc.executebuiltin('PlayerControl(Play)')
                    # Save the status of the player for later comparison
                    self.PlayerProperties.isConnectPause = True

            if self.__optMute and not self.PlayerProperties.isMute and not self.userActionMute:
                if not (self.__optPauseAudio or self.__optPauseVideo) or (
                    not self.__optPauseTV and self.PlayerProperties.isPlayTV):
                    self.notifyLog('Muting Volume...')
                    xbmc.executebuiltin('Mute')
                    # Save the status of the player for later comparison
                    self.PlayerProperties.isConnectMute = True

    def handleDisconnected(self, line):
        if not self.__hide:
            self.notifyLog('Line disconnected')

            # Use the conditions before connect. These are the real conditions to give back.
            # Check whether the status of the player has changed in the meantime by the user

            self.PlayerProperties.getDisconnectConditions()
            if self.connectionEstablished and self.PlayerProperties.isConnectPause != self.PlayerProperties.isDisconnectPause:
                self.userActionPlay = True
            if self.connectionEstablished and self.PlayerProperties.isConnectMute != self.PlayerProperties.isDisconnectMute:
                self.userActionMute = True

            # Use condition before connect.
            # Also, only do this if connection was established and user hasn't changed the status of the player

            if self.__optPauseAudio and self.PlayerProperties.isPlayAudio and not self.PlayerProperties.isPause and self.connectionEstablished and not self.userActionPlay:
                self.notifyLog('Player was not pausing Audio, resume...')
                xbmc.executebuiltin('PlayerControl(Play)')
            elif self.__optPauseVideo and self.PlayerProperties.isPlayVideo and not self.PlayerProperties.isPause and self.connectionEstablished and not self.userActionPlay:
                self.notifyLog('Player was not playing Video, resume...')
                xbmc.executebuiltin('PlayerControl(Play)')

            # Use condition before connect.
            # Also, only do this if connection was established and user hasn't changed the condition of the player

            if self.__optMute and not self.PlayerProperties.isMute and self.connectionEstablished and not self.userActionMute:
                # Extra condition: You don't want another condition to unmute than to mute.
                if not (self.__optPauseAudio or self.__optPauseVideo) or (
                    not self.__optPauseTV and self.PlayerProperties.isPlayTV):
                    self.notifyLog('Volume was not muted, unmute...')
                    xbmc.executebuiltin('Mute')
        else:
            self.notifyLog('excluded number seems disconnected, reset status of callmonitor')
            self.__hide = False

    def notifyOSD(self, header, message, icon=__IconDefault__, dispTime=5000):
        OSD.notification(header.encode('utf-8'), message.encode('utf-8'), icon, dispTime)

    def notifyLog(self, message, level=xbmc.LOGNOTICE):
        xbmc.log('[%s] %s' % (__addonname__, message.encode('utf-8')), level)

    def traceError(self, e, exc_tb):
        while exc_tb:
            tb = traceback.format_tb(exc_tb)
            self.notifyLog('%s' % e, level=xbmc.LOGERROR)
            self.notifyLog('In module: %s' % sys.argv[0].strip() or '<not defined>', level=xbmc.LOGERROR)
            self.notifyLog('At line:   %s' % traceback.tb_lineno(exc_tb), level=xbmc.LOGERROR)
            self.notifyLog('In file:   %s' % tb[0].split(",")[0].strip()[6:-1], level=xbmc.LOGERROR)
            exc_tb = exc_tb.tb_next

    def connect(self, notify=False):
        if self.__s is not None:
            self.__s.close()
            self.__s = None
        try:
            self.__s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__s.settimeout(60)
            self.__s.connect((self.__server, LISTENPORT))
        except socket.error as e:
            if notify: self.notifyOSD(__LS__(30030), __LS__(30031) % (self.__server, LISTENPORT), __IconError__)
            self.notifyLog('Could not connect to %s:%s' % (self.__server, LISTENPORT), level=xbmc.LOGERROR)
            self.notifyLog('%s' % (e), level=xbmc.LOGERROR)
            return False
        except Exception as e:
            self.traceError(e, sys.exc_traceback)
            return False
        else:
            self.notifyLog('Connected, listen to %s on port %s' % (self.__server, LISTENPORT))
            self.__s.settimeout(0.2)
            return True

    def start(self):

        if self.connect(notify=True):

            # MAIN SERVICE

            while not xbmc.abortRequested:

                try:
                    fbdata = self.__s.recv(512)
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
                    self.notifyLog('Communication failure', level=xbmc.LOGERROR)
                    self.connect()
                except socket.error as e:
                    self.notifyLog('No connection to %s, try to respawn' % (self.__server), level=xbmc.LOGERROR)
                    self.connect()
                except Exception as e:
                    self.traceError(e, sys.exc_traceback)
                    break

                if self.SettingsChanged:
                    self.notifyLog('Settings changed, perform update')
                    self.getSettings()
                    self.SettingsChanged = False
                    self.getPhonebook()

            self.__s.close()


# START

CallMon = FritzCallmonitor()
CallMon.start()
CallMon.notifyLog('Monitoring finished')
del CallMon
