# -*- coding: utf-8 -*-

import socket
import os
import sys

import xbmc
import xbmcaddon
import xbmcgui
import re

ADDON = xbmcaddon.Addon()
ADDONNAME = ADDON.getAddonInfo('id')
ADDONPATH = xbmc.translatePath(ADDON.getAddonInfo('path'))
ICON_OK = os.path.join(ADDONPATH, 'resources', 'media', 'incoming.png')

LIBS = os.path.join(ADDONPATH, 'resources', 'lib')
sys.path.append(LIBS)

from resources.lib.PhoneBooks.PhoneBookFacade import PhoneBookFacade
import resources.lib.tools as tools

ADDONPROFILES = xbmc.translatePath(ADDON.getAddonInfo('profile'))
ADDONVERSION = ADDON.getAddonInfo('version')
LOC = ADDON.getLocalizedString

ICON_ERROR = os.path.join(ADDONPATH, 'resources', 'media', 'unknown.png')
ICON_UNKNOWN = os.path.join(ADDONPATH, 'resources', 'media', 'blue.png')

IMAGECACHE = os.path.join(ADDONPROFILES, 'cache')
if not os.path.exists(IMAGECACHE): os.makedirs(IMAGECACHE, 0755)

# Fritz!Box

LISTENPORT = 1012
HOME = xbmcgui.Window(10000)

# CLASSES

class PlayerProperties(object):
    def __init__(self):

        self.connCondition = dict()
        self.callCondition = dict()
        self.discCondition = dict()

    @classmethod
    def getCurrentConditions(cls):
        _cond = dict()
        _cond['playTV'] = bool(xbmc.getCondVisibility('Pvr.isPlayingTv'))
        _cond['playVideo'] = bool(xbmc.getCondVisibility('Player.HasVideo') and xbmc.getCondVisibility('Player.Playing'))
        _cond['playAudio'] = bool(xbmc.getCondVisibility('Player.HasAudio') and xbmc.getCondVisibility('Player.Playing'))
        _cond['paused'] = bool(xbmc.getCondVisibility('Player.Paused'))
        _cond['muted'] = bool(xbmc.getCondVisibility('Player.Muted'))
        _cond['volChanged'] = False

        # Get the Volume

        query = {
                "method": "Application.GetProperties",
                "params": {"properties": ["volume"]}
                }
        res = tools.jsonrpc(query)
        if res is not None: _cond['volume'] = res.get('volume', 0)
        return _cond

    def getConnectConditions(self, state):
        self.connCondition.update(self.getCurrentConditions())
        for cond in self.connCondition: tools.writeLog('act property on %s: %s: %s' % (state, cond.rjust(10), self.connCondition[cond]))

    def getCallingConditions(self, state):
        self.callCondition.update(self.getCurrentConditions())
        for cond in self.callCondition: tools.writeLog('set property on %s: %s: %s' % (state, cond.rjust(10), self.callCondition[cond]))

    def getDisconnectConditions(self, state):
        self.discCondition.update(self.getCurrentConditions())
        for cond in self.discCondition: tools.writeLog('act property on %s: %s: %s' % (state, cond.rjust(10), self.discCondition[cond]))

    @classmethod
    def setVolume(cls, volume):

        query = {
                "method": "Application.SetVolume",
                "params": {"volume": int(volume)}
                }
        return tools.jsonrpc(query)


class FritzCallmonitor(object):
    __phoneBookFacade = None
    __phonebook = None
    __hide = False
    __s = None

    def __init__(self):

        self.PlayerProps = PlayerProperties()
        self.Mon = tools.Monitor()
        self.getPhonebook()

        self.ScreensaverActive = xbmc.getCondVisibility('System.ScreenSaverActive')

        HOME.setProperty('FritzCallMon.InCall', 'false')

    class CallMonitorLine(dict):

        def __init__(self, line):
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
            self.__phoneBookFacade = PhoneBookFacade(imagepath=IMAGECACHE)
            setting_keys = self.__phoneBookFacade.get_setting_keys()
            for key in setting_keys: setting_keys[key] = ADDON.getSetting(key)
            self.__phoneBookFacade.set_settings(setting_keys)

        if self.__phonebook is None:
            try:
                self.__phonebook = self.__phoneBookFacade.getPhonebook()
                tools.writeLog('%s entries from %s loaded, %s images cached' % (
                    len(self.__phonebook), self.Mon.server, self.__phoneBookFacade.imagecount()), xbmc.LOGNOTICE)
            except self.__phoneBookFacade.HostUnreachableException:
                tools.writeLog('Host %s unreachable' % (self.Mon.server), level=xbmc.LOGERROR)
                tools.notify(LOC(30030), LOC(30031) % (self.Mon.server, LISTENPORT), ICON_ERROR)
            except self.__phoneBookFacade.LoginFailedException:
                tools.writeLog('Login failed. Check username/password', level=xbmc.LOGERROR)
                tools.notify(LOC(30033), LOC(30034), ICON_ERROR)
            except self.__phoneBookFacade.InternalServerErrorException:
                tools.writeLog('Internal server error', level=xbmc.LOGERROR)
                tools.notify(LOC(30035), LOC(30036), ICON_ERROR)

    def getRecordByNumber(self, request_number):

        name = ''
        imageBMP = None

        if isinstance(self.__phonebook, dict):
            for item in self.__phonebook:
                for number in self.__phonebook[item]['numbers']:
                    if self.__phoneBookFacade.compareNumbers(number, request_number, ccode=self.Mon.cCode):
                        tools.writeLog('Match an entry in database for %s: %s' % (tools.mask(request_number), tools.mask(item)), xbmc.LOGNOTICE)
                        name = item
                        fname = os.path.join(IMAGECACHE, re.sub('\D', '', number.replace('+', '00')) + '.jpg')
                        if os.path.isfile(fname):
                            tools.writeLog('Load image from cache', xbmc.LOGNOTICE)
                            imageBMP = fname
                            break

        return {'name': name, 'imageBMP': imageBMP}

    def handlePlayerProps(self, state):

        tools.writeLog('Handle Player Properties for state \'%s\'' % (state))
        try:
            if self.Mon.optEarlyPause and (state == 'incoming' or state == 'outgoing'):
                self.PlayerProps.getConnectConditions(state)
                #
                # handle sound
                #
                if self.Mon.optMute and \
                        not self.PlayerProps.connCondition.get('muted', False) and \
                        not self.PlayerProps.connCondition.get('volChanged', False):
                    vol = self.PlayerProps.connCondition['volume'] * self.Mon.volume
                    tools.writeLog('Change volume to %s' % (vol), xbmc.LOGNOTICE)
                    self.PlayerProps.setVolume(vol)
                    self.PlayerProps.connCondition['volChanged'] = True
                #
                # handle audio, video & TV
                #
                if (self.Mon.optPauseAudio and self.PlayerProps.connCondition['playAudio']) \
                        or (self.Mon.optPauseVideo and self.PlayerProps.connCondition['playVideo']
                            and not self.PlayerProps.connCondition['playTV']) \
                        or (self.Mon.optPauseTV and self.PlayerProps.connCondition['playTV']):
                    tools.writeLog('Pausing audio, video or tv...', xbmc.LOGNOTICE)
                    xbmc.executebuiltin('PlayerControl(Play)')
                self.PlayerProps.getCallingConditions(state)

            elif not self.Mon.optEarlyPause and state == 'connected':
                self.PlayerProps.getConnectConditions(state)
                #
                # handle sound
                #
                if self.Mon.optMute and \
                        not self.PlayerProps.connCondition.get('muted', False) and \
                        not self.PlayerProps.connCondition.get('volChanged', False):
                    vol = self.PlayerProps.connCondition['volume'] * self.Mon.volume
                    tools.writeLog('Change volume to %s' % (vol), xbmc.LOGNOTICE)
                    self.PlayerProps.setVolume(vol)
                    self.PlayerProps.connCondition['volChanged'] = True
                #
                # handle audio, video & TV
                #
                if (self.Mon.optPauseAudio and self.PlayerProps.connCondition['playAudio']) \
                        or (self.Mon.optPauseVideo and self.PlayerProps.connCondition['playVideo']
                            and not self.PlayerProps.connCondition['playTV']) \
                        or (self.Mon.optPauseTV and self.PlayerProps.connCondition['playTV']):
                    tools.writeLog('Pausing audio, video or tv...', xbmc.LOGNOTICE)
                    xbmc.executebuiltin('PlayerControl(Play)')
                self.PlayerProps.getCallingConditions(state)

            elif state == 'disconnected':
                self.PlayerProps.getDisconnectConditions(state)
                #
                # nothing to do, all properties of disconnect are the same as connect properties
                #
                if self.PlayerProps.connCondition == self.PlayerProps.discCondition: return
                #
                # handle sound
                #
                if self.Mon.optMute and not self.PlayerProps.connCondition.get('muted', False) \
                        and self.PlayerProps.discCondition['volume'] != self.PlayerProps.connCondition['volume']:
                    if self.PlayerProps.callCondition['volume'] == self.PlayerProps.discCondition['volume']:
                        tools.writeLog('Volume hasn\'t changed during call', xbmc.LOGNOTICE)
                        vol = self.PlayerProps.setVolume(self.PlayerProps.connCondition['volume'])
                        tools.writeLog('Changed volume back to %s' % (vol), xbmc.LOGNOTICE)
                    else:
                        tools.writeLog('Volume has changed during call, don\'t change it back', xbmc.LOGNOTICE)
                    self.PlayerProps.connCondition['volChanged'] = False

                #
                # handle audio, video & TV
                #
                if (self.Mon.optPauseAudio and self.PlayerProps.connCondition['playAudio']
                    and not self.PlayerProps.discCondition['playAudio']) \
                        or (self.Mon.optPauseVideo and self.PlayerProps.connCondition['playVideo']
                            and not self.PlayerProps.discCondition['playVideo']) \
                        or (self.Mon.optPauseTV and self.PlayerProps.connCondition['playTV']
                            and not self.PlayerProps.discCondition['playTV']):
                    tools.writeLog('Resume audio, video or tv...', xbmc.LOGNOTICE)
                    xbmc.executebuiltin('PlayerControl(Play)')
            else:
                tools.writeLog('don\'t handle properties for state %s' % state, xbmc.LOGERROR)
                # self.PlayerProps.getConnectConditions(state)
        except Exception, e:
            tools.writeLog('Error at line %s' % (str(sys.exc_info()[-1].tb_lineno)), xbmc.LOGERROR)
            tools.writeLog(str(type(e).__name__), xbmc.LOGERROR)
            tools.writeLog(e.message, level=xbmc.LOGERROR)


    def handleOutgoingCall(self, line):

        if line.number_used in self.Mon.exnum_list:
            self.__hide = True
            return

        if self.Mon.optShowOutgoing:

            self.handlePlayerProps('outgoing')

            record = self.getRecordByNumber(line.number_called)
            name = LOC(30012) if record['name'] == '' else record['name']
            icon = ICON_OK if record['imageBMP'] == '' else record['imageBMP']
            tools.notify(LOC(30013), LOC(30014) % (name, line.number_called), icon, deactivateSS=True)
            tools.writeLog('Outgoing call from %s to %s' % (tools.mask(line.number_used),
                                                            tools.mask(line.number_called)), xbmc.LOGNOTICE)

    def handleIncomingCall(self, line):

        if line.number_called in self.Mon.exnum_list:
            self.__hide = True
            return

        self.handlePlayerProps('incoming')

        if len(line.number_caller) > 0:
            caller_num = line.number_caller
            tools.writeLog('trying to resolve name from incoming number %s' % (tools.mask(caller_num)), xbmc.LOGNOTICE)
            record = self.getRecordByNumber(caller_num)
            name = record['name']
            icon = ICON_OK if record['imageBMP'] == '' else record['imageBMP']
            if not name:
                name = LOC(30012)
                icon = ICON_UNKNOWN
        else:
            caller_num = LOC(30016)
            name = LOC(30012)
            icon = ICON_UNKNOWN

        tools.writeLog('Incoming call from %s (%s)' % (tools.mask(name), tools.mask(caller_num)), xbmc.LOGNOTICE)
        tools.notify(LOC(30010), LOC(30011) % (name, caller_num), icon, self.Mon.dispMsgTime, deactivateSS=True)

    def handleConnected(self, line):
        tools.writeLog('Line connected', xbmc.LOGNOTICE)
        HOME.setProperty('FritzCallMon.InCall', 'true')
        if not self.__hide: self.handlePlayerProps('connected')

    def handleDisconnected(self, line):
        tools.writeLog('Line disconnected', xbmc.LOGNOTICE)
        HOME.setProperty('FritzCallMon.InCall', 'false')
        if not self.__hide: self.handlePlayerProps('disconnected')

    def connect(self, notify=False):
        if self.__s is not None:
            self.__s.close()
            self.__s = None
        try:
            self.__s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__s.settimeout(30)
            self.__s.connect((self.Mon.server, LISTENPORT))
        except socket.error, e:
            if notify: tools.notify(LOC(30030), LOC(30031) % (self.Mon.server, LISTENPORT), ICON_ERROR)
            tools.writeLog('Could not connect to %s:%s' % (self.Mon.server, LISTENPORT), level=xbmc.LOGERROR)
            tools.writeLog(e.message, level=xbmc.LOGERROR)
            return False
        except Exception, e:
            tools.writeLog('Error at line %s' % (sys.exc_info()[-1].tb_lineno), xbmc.LOGERROR)
            tools.writeLog(e.message, level=xbmc.LOGERROR)
            return False
        else:
            tools.writeLog('Connected, listen to %s on port %s' % (self.Mon.server, LISTENPORT), xbmc.LOGNOTICE)
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
                except socket.error, e:
                    tools.writeLog('No connection to %s, try to respawn' % (self.Mon.server), level=xbmc.LOGERROR)
                    tools.writeLog(e.message, level=xbmc.LOGERROR)
                    self.connect()
                except IndexError:
                    tools.writeLog('Communication failure', level=xbmc.LOGERROR)
                    self.connect()
                except Exception, e:
                    tools.writeLog('Error at line %s' % (str(sys.exc_info()[-1].tb_lineno)), xbmc.LOGERROR)
                    tools.writeLog(str(type(e).__name__), xbmc.LOGERROR)
                    tools.writeLog(e.message, level=xbmc.LOGERROR)

                xbmc.sleep(500)

            self.__s.close()


# START
if __name__ == '__main__':
    CallMon = FritzCallmonitor()
    CallMon.start()
    del CallMon
tools.writeLog('Monitoring finished', xbmc.LOGNOTICE)
