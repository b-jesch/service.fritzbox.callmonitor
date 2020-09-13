# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import re
import sys
import json

ADDON = sys.modules['__main__'].ADDON
ADDONNAME = sys.modules['__main__'].ADDONNAME
ICON_OK = sys.modules['__main__'].ICON_OK

def writeLog(message, level=xbmc.LOGDEBUG):
    xbmc.log('[%s] %s' % (ADDONNAME, message), level)

def jsonrpc(query):
    querystring = {"jsonrpc": "2.0", "id": 1}
    querystring.update(query)
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(querystring)))
        if 'result' in response: return response['result']
    except TypeError as e:
        writeLog('Error executing JSON RPC: %s' % (e.args), xbmc.LOGERROR)
    return None

def notify(header, message, icon=ICON_OK, dispTime=5000, deactivateSS=False):
    if deactivateSS and xbmc.getCondVisibility('System.ScreenSaverActive'):
        query = {
            "method": "Input.Select"
        }
        jsonrpc(query)

    xbmcgui.Dialog().notification(header, message, icon, dispTime)

def mask(string):
    if len(string) > 4: return '%s%s%s' % (string[0], '*' * (len(string) - 3), string[-2:])
    return '*' * len(string)

class Monitor(xbmc.Monitor):

    def __init__(self):
        self.get_settings()
        writeLog('Settings loaded', xbmc.LOGINFO)

    @classmethod
    def onSettingsChanged(cls):
        dialog = xbmcgui.Dialog()
        if dialog.yesno(ADDONNAME, ADDON.getLocalizedString(30037)): xbmc.executebuiltin('RestartApp()')

    def get_settings(self):

        # transform possible userinput from e.g. 'p1, p2,,   p3 p4  '
        # to a list like this: ['p1','p2','p3','p4']
        self.exnum_list = ' '.join(ADDON.getSettingString('excludeNums').replace(',', ' ').split()).split()

        self.server = ADDON.getSettingString('phoneserver')
        self.dispMsgTime = int(re.match('\d+', ADDON.getSetting('dispTime')).group()) * 1000
        self.cCode = ADDON.getSettingString('cCode')
        self.optShowOutgoing = ADDON.getSettingBool('showOutgoingCalls')
        self.optMute = ADDON.getSettingBool('optMute')
        self.volume = int(ADDON.getSetting('volume')) * 0.1
        self.optFade = ADDON.getSettingBool('optFade')
        self.optPauseAudio = ADDON.getSettingBool('optPauseAudio')
        self.optPauseVideo = ADDON.getSettingBool('optPauseVideo')
        self.optPauseTV = ADDON.getSettingBool('optPauseTV')
        self.optEarlyPause = ADDON.getSettingBool('optEarlyPause')

        writeLog('Server IP/name:   %s' % (self.server))
        writeLog('excluded Numbers: %s' % (', '.join(self.exnum_list)))
        writeLog('Display time:     %s' % (self.dispMsgTime))
        writeLog('Country code:     %s' % (self.cCode))
        writeLog('handle outgoings: %s' % (self.optShowOutgoing))
        writeLog('Change Volume:    %s' % (self.optMute))
        writeLog('Change to:        %s' % (self.volume))
        writeLog('Volume fading:    %s' % (self.optFade))
        writeLog('Pause audio:      %s' % (self.optPauseAudio))
        writeLog('Pause video:      %s' % (self.optPauseVideo))
        writeLog('Pause tv:         %s' % (self.optPauseTV))
        writeLog('React on ring:    %s' % (self.optEarlyPause))
