# -*- coding: utf-8 -*-

import socket
import os
import re

import xbmc
import xbmcaddon
from resources.lib.PhoneBooks.PhoneBookFacade import PhoneBookFacade
from resources.lib.KlickTel import KlickTel
import resources.lib.tools as tools
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

__ImageCache__ = xbmc.translatePath(os.path.join('special://userdata', 'addon_data', __addonname__, 'cache'))
if not os.path.exists(__ImageCache__): os.makedirs(__ImageCache__)

# Fritz!Box

LISTENPORT = 1012

# CLASSES

class PlayerProperties:
    def __init__(self):
        self.Condition = {'playTV': False, 'playVideo': False, 'playAudio': False, 'paused': False, 'muted': False, 'volume': 0}
        self.connCondition = {}
        self.discCondition = {}

    def getCurrentConditions(self):
        self.Condition['playTV'] = bool(xbmc.getCondVisibility('Pvr.isPlayingTv'))
        self.Condition['playVideo'] = bool(xbmc.getCondVisibility('Player.HasVideo') and xbmc.getCondVisibility('Player.Playing'))
        self.Condition['playAudio'] = bool(xbmc.getCondVisibility('Player.HasAudio') and xbmc.getCondVisibility('Player.Playing'))
        self.Condition['paused'] = bool(xbmc.getCondVisibility('Player.Paused'))
        self.Condition['muted'] = bool(xbmc.getCondVisibility('Player.Muted'))

        # Get the Volume

        query = {
                "jsonrpc": "2.0",
                "method": "Application.GetProperties",
                "params": {"properties": ["volume"]},
                "id": 1
                }
        res = tools.jsonrpc(query)
        if 'result' in res and 'volume' in res['result']:
            self.Condition['volume'] = int(res['result'].get('volume'))

        return self.Condition

    def getConnectConditions(self, state):
        self.connCondition.update(self.getCurrentConditions())
        for cond in self.connCondition: tools.writeLog('actual condition on %s %s: %s' % (state, cond.rjust(10), self.connCondition[cond]), level=xbmc.LOGDEBUG)

    def getDisconnectConditions(self, state):
        self.discCondition.update(self.getCurrentConditions())
        for cond in self.discCondition: tools.writeLog('actual condition on %s %s: %s' % (state, cond.rjust(10), self.discCondition[cond]), level=xbmc.LOGDEBUG)

    def setVolume(self, volume):

        query =  {"jsonrpc": "2.0",
                  "method": "Application.SetVolume",
                  "params": {"volume": volume}, "id": 1}

        res = tools.jsonrpc(query)
        if 'result' in res: return res['result']

class FritzCallmonitor(object):
    __phoneBookFacade = None
    __phonebook = None
    __klicktel = None
    __hide = False
    __s = None

    def __init__(self):

        self.PlayerProps = PlayerProperties()
        self.Mon = tools.Monitor()
        self.getPhonebook()

        self.ScreensaverActive = xbmc.getCondVisibility('System.ScreenSaverActive')
        self.screensaver = None

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

    # Get the Phonebook

    def getPhonebook(self):

        if self.__phoneBookFacade is None:
            self.__phoneBookFacade = PhoneBookFacade(imagepath=__ImageCache__)
            setting_keys = self.__phoneBookFacade.get_setting_keys()
            for key in setting_keys: setting_keys[key] = __addon__.getSetting(key)
            self.__phoneBookFacade.set_settings(setting_keys)

        if self.__phonebook is None:
            try:
                self.__phonebook = self.__phoneBookFacade.getPhonebook()
                tools.writeLog('%s entries from %s loaded, %s images cached' % (
                    len(self.__phonebook), self.Mon.server, self.__phoneBookFacade.imagecount()))
            except self.__phoneBookFacade.HostUnreachableException:
                tools.notify(__LS__(30030), __LS__(30031) % (self.Mon.server, LISTENPORT), __IconError__)
            except self.__phoneBookFacade.LoginFailedException:
                tools.notify(__LS__(30033), __LS__(30034), __IconError__)
            except self.__phoneBookFacade.InternalServerErrorException:
                tools.notify(__LS__(30035), __LS__(30036), __IconError__)

    def getNameByKlickTel(self, request_number):

        if self.Mon.useKlickTelReverse:
            if self.__klicktel is None: self.__klicktel = KlickTel.KlickTelReverseSearch()
            try:
                return self.__klicktel.search(request_number)
            except Exception as e:
                tools.writeLog(str(e), level=xbmc.LOGERROR)
        return False

    def getRecordByNumber(self, request_number):

        name = ''
        imageBMP = None

        if isinstance(self.__phonebook, dict):
            for item in self.__phonebook:
                for number in self.__phonebook[item]['numbers']:
                    if self.__phoneBookFacade.compareNumbers(number, request_number, ccode=self.Mon.cCode):
                        tools.writeLog('Match an entry in database for %s: %s' % (request_number, item))
                        name = item
                        fname = os.path.join(__ImageCache__, hashlib.md5(item.encode('utf-8')).hexdigest() + '.jpg')
                        if os.path.isfile(fname):
                            tools.writeLog('Load image from cache: %s' % (os.path.basename(fname)))
                            imageBMP = fname
                            break

        return {'name': name, 'imageBMP': imageBMP}

    def handlePlayerProps(self, state):

        tools.writeLog('Handle Player Properties for state \'%s\'' % (state), level=xbmc.LOGDEBUG)
        if self.Mon.optEarlyPause and (state == 'incoming' or state == 'outgoing'):
            self.PlayerProps.getConnectConditions(state)
            #
            # handle sound
            #
            if self.Mon.optMute and not self.PlayerProps.connCondition['muted']:
                vol = int(self.PlayerProps.connCondition['volume'] * self.Mon.volume)
                tools.writeLog('Change volume to %s' % (vol))
                self.PlayerProps.setVolume(vol)
            #
            # handle audio, video & TV
            #
            if (self.Mon.optPauseAudio and self.PlayerProps.connCondition['playAudio']) \
                    or (self.Mon.optPauseVideo and self.PlayerProps.connCondition['playVideo']
                        and not self.PlayerProps.connCondition['playTV']) \
                    or (self.Mon.optPauseTV and self.PlayerProps.connCondition['playTV']):
                tools.writeLog('Pausing audio, video or tv...')
                xbmc.executebuiltin('PlayerControl(Play)')

        elif not self.Mon.optEarlyPause and state == 'connected':
            self.PlayerProps.getConnectConditions(state)
            #
            # handle sound
            #
            if self.Mon.optMute and not self.PlayerProps.connCondition['muted']:
                vol = int(self.PlayerProps.connCondition['volume'] * self.Mon.volume)
                tools.writeLog('Change volume to %s' % (vol))
                self.PlayerProps.setVolume(vol)
            #
            # handle audio, video & TV
            #
            if (self.Mon.optPauseAudio and self.PlayerProps.connCondition['playAudio']) \
                    or (self.Mon.optPauseVideo and self.PlayerProps.connCondition['playVideo']
                        and not self.PlayerProps.connCondition['playTV']) \
                    or (self.Mon.optPauseTV and self.PlayerProps.connCondition['playTV']):
                tools.writeLog('Pausing audio, video or tv...')
                xbmc.executebuiltin('PlayerControl(Play)')

        elif state == 'disconnected':
            self.PlayerProps.getDisconnectConditions(state)
            #
            # nothing to do, all properties of disconnect are the same as connect properties
            #
            if self.PlayerProps.connCondition == self.PlayerProps.discCondition: return
            #
            # handle sound
            #
            if self.Mon.optMute and not self.PlayerProps.connCondition['muted'] \
                    and self.PlayerProps.discCondition['volume'] != self.PlayerProps.connCondition['volume']:
                vol = self.PlayerProps.setVolume(int(self.PlayerProps.connCondition['volume']))
                tools.writeLog('Changed volume back to %s' % (vol))
            #
            # handle audio, video & TV
            #
            if (self.Mon.optPauseAudio and self.PlayerProps.connCondition['playAudio']
                and not self.PlayerProps.discCondition['playAudio']) \
                    or (self.Mon.optPauseVideo and self.PlayerProps.connCondition['playVideo']
                        and not self.PlayerProps.discCondition['playVideo']) \
                    or (self.Mon.optPauseTV and self.PlayerProps.connCondition['playTV']
                        and not self.PlayerProps.discCondition['playTV']):
                tools.writeLog('Resume audio, video or tv...')
                xbmc.executebuiltin('PlayerControl(Play)')

    def handleOutgoingCall(self, line):

        if line.number_used in self.Mon.exnum_list:
            self.__hide = True
            return

        if self.Mon.optShowOutgoing:

            self.handlePlayerProps('outgoing')

            record = self.getRecordByNumber(line.number_called)
            name = __LS__(30012) if record['name'] == '' else record['name']
            icon = __IconDefault__ if record['imageBMP'] == '' else record['imageBMP']
            tools.notify(__LS__(30013), __LS__(30014) % (name, line.number_called), icon)
            tools.writeLog('Outgoing call from %s to %s' % (line.number_used, line.number_called))

    def handleIncomingCall(self, line):

        if line.number_called in self.Mon.exnum_list:
            self.__hide = True
            return

        self.handlePlayerProps('incoming')

        if len(line.number_caller) > 0:
            caller_num = line.number_caller
            tools.writeLog('trying to resolve name from incoming number %s' % (caller_num))
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

        tools.writeLog('Incoming call from %s (%s)' % (name, caller_num))
        tools.notify(__LS__(30010), __LS__(30011) % (name, caller_num), icon, self.Mon.dispMsgTime)

    def handleConnected(self, line):
        tools.writeLog('Line connected')
        if not self.__hide: self.handlePlayerProps('connected')

    def handleDisconnected(self, line):
        tools.writeLog('Line disconnected')
        if not self.__hide: self.handlePlayerProps('disconnected')

    def connect(self, notify=False):
        if self.__s is not None:
            self.__s.close()
            self.__s = None
        try:
            self.__s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__s.settimeout(30)
            self.__s.connect((self.Mon.server, LISTENPORT))
        except socket.error as e:
            if notify: tools.notify(__LS__(30030), __LS__(30031) % (self.Mon.server, LISTENPORT), __IconError__)
            tools.writeLog('Could not connect to %s:%s' % (self.Mon.server, LISTENPORT), level=xbmc.LOGERROR)
            tools.writeLog('%s' % (e), level=xbmc.LOGERROR)
            return False
        except Exception as e:
            tools.writeLog('%s' % (e), level=xbmc.LOGERROR)
            return False
        else:
            tools.writeLog('Connected, listen to %s on port %s' % (self.Mon.server, LISTENPORT))
            self.__s.settimeout(0.2)
            return True

    def start(self):

        if self.connect(notify=True):

            # MAIN SERVICE

            while not xbmc.abortRequested:

                # ToDo: investigate more from https://pymotw.com/2/select/index.html#module-select
                # i.e check exception handling

                try:
                    fbdata = self.__s.recv(512)
                    line = self.CallMonitorLine(fbdata)

                    {
                        'CALL': self.handleOutgoingCall,
                        'RING': self.handleIncomingCall,
                        'CONNECT': self.handleConnected,
                        'DISCONNECT': self.handleDisconnected
                    }.get(line.command)(line)

                except socket.timeout:
                    pass
                except socket.error as e:
                    tools.writeLog('No connection to %s, try to respawn' % (self.Mon.server), level=xbmc.LOGERROR)
                    tools.writeLog('%s' % (e), level=xbmc.LOGERROR)
                    self.connect()
                except IndexError:
                    tools.writeLog('Communication failure', level=xbmc.LOGERROR)
                    self.connect()
                except Exception as e:
                    tools.writeLog('%s' % (e), level=xbmc.LOGERROR)
                    break

                xbmc.sleep(500)

            self.__s.close()


# START

CallMon = FritzCallmonitor()
CallMon.start()
tools.writeLog('Monitoring finished')
del CallMon
