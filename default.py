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

IMAGECACHE = os.path.join(ADDONPROFILES, 'pb_images')
if not os.path.exists(IMAGECACHE): os.makedirs(IMAGECACHE, 0o755)

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

        _cond['volume'] = int(tools.jsonrpc(query).get('volume', 0))
        return _cond

    def getConnectConditions(self, state):
        self.connCondition.update(self.getCurrentConditions())
        for cond in self.connCondition: tools.writeLog('cur property on %s: %s: %s' % (state, cond.rjust(10), self.connCondition[cond]))

    def getCallingConditions(self, state):
        self.callCondition.update(self.getCurrentConditions())
        for cond in self.callCondition: tools.writeLog('set property on %s: %s: %s' % (state, cond.rjust(10), self.callCondition[cond]))

    def getDisconnectConditions(self, state):
        self.discCondition.update(self.getCurrentConditions())
        for cond in self.discCondition: tools.writeLog('cur property on %s: %s: %s' % (state, cond.rjust(10), self.discCondition[cond]))

    def setVolume(self, volume, fade):

        query = {
                "method": "Application.GetProperties",
                "params": {"properties": ["volume"]}
                }

        currVolume = int(tools.jsonrpc(query).get('volume', 0))
        res = currVolume
        _d = -2 if currVolume - int(volume) > 0 else 2
        steps = abs(currVolume - int(volume)) / 2
        if steps > 0 and fade:
            delay = int(1200 / steps)
            while steps > 0:
                currVolume += _d
                query = {
                        "method": "Application.SetVolume",
                        "params": {"volume": int(currVolume)}
                        }
                res = tools.jsonrpc(query)
                steps -= 1
                xbmc.sleep(delay)
            return res
        else:
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
    __connects = 0

    def __init__(self):

        self.PlayerProps = PlayerProperties()
        self.Mon = tools.Monitor()
        self.ScreensaverActive = xbmc.getCondVisibility('System.ScreenSaverActive')

        HOME.setProperty('FritzCallMon.InCall', 'false')

    def CallMonitorLine(self, line):

        items = dict()
        if len(line) > 0:
            token = line.split(';')
            items.update({'command': token[1], 'connection_id': token[2]})
            if items['command'] == 'CALL':
                items.update({'extension': token[3], 'number_used': token[4], 'number_called': token[5], 'sip': token[6]})
            elif items['command'] == 'RING':
                items.update({'date': token[0], 'number_caller': token[3], 'number_called': token[4], 'sip': token[5]})
            elif items['command'] == 'CONNECT':
                items.update({'date': token[0], 'extension': token[3], 'number': token[4]})
            elif items['command'] == 'DISCONNECT':
                items.update({'date': token[0], 'duration': token[3]})
        return items

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
                    len(self.__phonebook), self.Mon.server, self.__phoneBookFacade.imagecount()), xbmc.LOGINFO)
            except self.__phoneBookFacade.HostUnreachableException as e:
                tools.writeLog('Host %s unreachable: %s' % (self.Mon.server, str(e)), level=xbmc.LOGERROR)
                tools.notify(LOC(30030), LOC(30031) % (self.Mon.server, LISTENPORT), ICON_ERROR)
            except self.__phoneBookFacade.LoginFailedException as e:
                tools.writeLog('Login failed. Check username/password', level=xbmc.LOGERROR)
                tools.writeLog(str(e), level=xbmc.LOGERROR)
                tools.notify(LOC(30033), LOC(30034), ICON_ERROR)
            except self.__phoneBookFacade.InternalServerErrorException as e:
                tools.writeLog('Internal server error: %s' % (str(e)), level=xbmc.LOGERROR)
                tools.notify(LOC(30035), LOC(30036), ICON_ERROR)

    def getRecordByNumber(self, request_number):

        name = ''
        imageBMP = None

        if isinstance(self.__phonebook, dict):
            for item in self.__phonebook:
                for number in self.__phonebook[item]['numbers']:
                    if self.__phoneBookFacade.compareNumbers(number, request_number, ccode=self.Mon.cCode):
                        tools.writeLog('Match an entry in database for %s: %s' % (tools.mask(request_number), tools.mask(item)), xbmc.LOGINFO)
                        name = item
                        fname = os.path.join(IMAGECACHE, re.sub('\D', '', number.replace('+', '00')))
                        if os.path.isfile(fname):
                            tools.writeLog('Load image from cache', xbmc.LOGINFO)
                            imageBMP = fname
                            break

        return {'name': name, 'imageBMP': imageBMP}

    def handlePlayerProps(self, state):

        tools.writeLog('Handle Player Properties for state \'%s\'' % state)
        try:
            if self.Mon.optEarlyPause and (state == 'incoming' or state == 'outgoing'):
                self.PlayerProps.getConnectConditions(state)
                #
                # handle sound
                #
                if self.Mon.optMute and \
                        not self.PlayerProps.connCondition.get('muted', False) and \
                        not self.PlayerProps.connCondition.get('volChanged', False):
                    if self.__connects == 0:
                        vol = self.PlayerProps.connCondition['volume'] * self.Mon.volume
                        tools.writeLog('Change volume to %s' % vol, xbmc.LOGINFO)
                        self.PlayerProps.setVolume(vol, self.Mon.optFade)
                        self.PlayerProps.connCondition['volChanged'] = True
                    self.__connects += 1
                #
                # handle audio, video & TV
                #
                if (self.Mon.optPauseAudio and self.PlayerProps.connCondition['playAudio']) \
                        or (self.Mon.optPauseVideo and self.PlayerProps.connCondition['playVideo']
                            and not self.PlayerProps.connCondition['playTV']) \
                        or (self.Mon.optPauseTV and self.PlayerProps.connCondition['playTV']):
                    tools.writeLog('Pausing audio, video or tv...', xbmc.LOGINFO)
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
                    tools.writeLog('Change volume to %s' % vol, xbmc.LOGINFO)
                    self.PlayerProps.setVolume(vol, self.Mon.optFade)
                    self.PlayerProps.connCondition['volChanged'] = True
                #
                # handle audio, video & TV
                #
                if (self.Mon.optPauseAudio and self.PlayerProps.connCondition['playAudio']) \
                        or (self.Mon.optPauseVideo and self.PlayerProps.connCondition['playVideo']
                            and not self.PlayerProps.connCondition['playTV']) \
                        or (self.Mon.optPauseTV and self.PlayerProps.connCondition['playTV']):
                    tools.writeLog('Pausing audio, video or tv...', xbmc.LOGINFO)
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
                        tools.writeLog('Volume hasn\'t changed during call', xbmc.LOGINFO)
                        vol = self.PlayerProps.setVolume(self.PlayerProps.connCondition['volume'], self.Mon.optFade)
                        tools.writeLog('Changed volume back to %s' % vol, xbmc.LOGINFO)
                    else:
                        tools.writeLog('Volume has changed during call, don\'t change it back', xbmc.LOGINFO)
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
                    tools.writeLog('Resume audio, video or tv...', xbmc.LOGINFO)
                    xbmc.executebuiltin('PlayerControl(Play)')
            else:
                tools.writeLog('unhandled condition for state %s, ignore' % state, xbmc.LOGERROR)
                # self.PlayerProps.getConnectConditions(state)
        except Exception as e:
            tools.writeLog('Error at line %s' % (str(sys.exc_info()[-1].tb_lineno)), level=xbmc.LOGERROR)
            tools.writeLog(str(type(e).__name__), level=xbmc.LOGERROR)
            tools.writeLog(e.args, level=xbmc.LOGERROR)

    def handleOutgoingCall(self, line):

        if line['number_used'] in self.Mon.exnum_list:
            self.__hide = True
            return

        if self.Mon.optShowOutgoing:

            self.handlePlayerProps('outgoing')

            record = self.getRecordByNumber(line['number_called'])
            name = LOC(30012) if record['name'] == '' else record['name']
            icon = ICON_OK if record['imageBMP'] == '' else record['imageBMP']
            tools.notify(LOC(30013), LOC(30014) % (name, line['number_called']), icon, deactivateSS=True)
            tools.writeLog('Outgoing call from %s to %s' % (tools.mask(line['number_used']),
                                                            tools.mask(line['number_called'])), xbmc.LOGINFO)

    def handleIncomingCall(self, line):

        if line['number_called'] in self.Mon.exnum_list:
            self.__hide = True
            return

        self.handlePlayerProps('incoming')

        if len(line['number_caller']) > 0:
            caller_num = line['number_caller']
            tools.writeLog('trying to resolve name from incoming number %s' % (tools.mask(caller_num)), xbmc.LOGINFO)
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

        tools.writeLog('Incoming call from %s (%s)' % (tools.mask(name), tools.mask(caller_num)), xbmc.LOGINFO)
        tools.notify(LOC(30010), LOC(30011) % (name, caller_num), icon, self.Mon.dispMsgTime, deactivateSS=True)

    def handleConnected(self, line):
        tools.writeLog('Line connected', xbmc.LOGINFO)
        HOME.setProperty('FritzCallMon.InCall', 'true')
        if not self.__hide: self.handlePlayerProps('connected')

    def handleDisconnected(self, line):
        tools.writeLog('Line disconnected', xbmc.LOGINFO)
        if self.__connects > 0: self.__connects -= 1
        if self.__connects == 0:
            HOME.setProperty('FritzCallMon.InCall', 'false')
            if not self.__hide: self.handlePlayerProps('disconnected')
        else:
            tools.writeLog('still hold %s connection(s)' % self.__connects, xbmc.LOGINFO)

    def connect(self, notify=False):
        if self.__s is not None:
            self.__s.close()
            self.__s = None
        try:
            self.__s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__s.settimeout(30)
            self.__s.connect((self.Mon.server, LISTENPORT))
            tools.writeLog('Connected, listen to %s on port %s' % (self.Mon.server, LISTENPORT), xbmc.LOGINFO)
            self.__s.settimeout(1.0)
            return True

        except socket.error as e:
            if notify: tools.notify(LOC(30030), LOC(30031) % (self.Mon.server, LISTENPORT), ICON_ERROR)
            tools.writeLog('Could not connect to %s:%s' % (self.Mon.server, LISTENPORT), level=xbmc.LOGERROR)
            tools.writeLog(e, level=xbmc.LOGERROR)

        except Exception as e:
            tools.writeLog('Error at line %s' % sys.exc_info()[-1].tb_lineno, xbmc.LOGERROR)
            tools.writeLog(str(type(e).__name__), level=xbmc.LOGERROR)
            tools.writeLog(e.args, level=xbmc.LOGERROR)

        return False


    def start(self):

        if self.connect(notify=True):
            self.getPhonebook()

            # MAIN SERVICE

            while not self.Mon.abortRequested():
                try:
                    fbdata = self.__s.recv(512)
                    line = self.CallMonitorLine(str(fbdata))
                    if line['command'] == 'CALL': self.handleOutgoingCall(line)
                    elif line['command'] == 'RING': self.handleIncomingCall(line)
                    elif line['command'] == 'CONNECT': self.handleConnected(line)
                    elif line['command'] == 'DISCONNECT': self.handleDisconnected(line)
                    else: pass

                except socket.timeout:
                    pass
                except socket.error as e:
                    tools.writeLog('No connection to %s, try to respawn' % self.Mon.server, level=xbmc.LOGERROR)
                    tools.writeLog(e.strerror, level=xbmc.LOGERROR)
                    self.connect()
                except KeyError:
                    tools.writeLog('Communication failure', level=xbmc.LOGERROR)
                    self.connect()
                except Exception as e:
                    tools.writeLog('Error at line %s' % (str(sys.exc_info()[-1].tb_lineno)), level=xbmc.LOGERROR)
                    tools.writeLog(str(type(e).__name__), level=xbmc.LOGERROR)
                    tools.writeLog(e.args, level=xbmc.LOGERROR)

                xbmc.sleep(500)

            self.__s.close()


# START
if __name__ == '__main__':
    CallMon = FritzCallmonitor()
    CallMon.start()
    del CallMon
tools.writeLog('Monitoring finished', level=xbmc.LOGINFO)
