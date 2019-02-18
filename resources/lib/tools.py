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
    xbmc.log('[%s] %s' % (ADDONNAME, message.encode('utf-8')), level)

def jsonrpc(query):
    querystring = {"jsonrpc": "2.0", "id": 1}
    querystring.update(query)
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(querystring, encoding='utf-8')))
        if 'result' in response: return response['result']
    except TypeError, e:
        writeLog('Error executing JSON RPC: %s' % (e.message), xbmc.LOGERROR)
    return None

def notify(header, message, icon=ICON_OK, dispTime=5000, deactivateSS=False):
    if deactivateSS and xbmc.getCondVisibility('System.ScreenSaverActive'):
        query = {
            "method": "Input.Select"
        }
        jsonrpc(query)

    xbmcgui.Dialog().notification(header.encode('utf-8'), message.encode('utf-8'), icon, dispTime)

def mask(string):
    if len(string) > 4: return '%s%s%s' % (string[0], '*' * (len(string) - 3), string[-2:])
    return '*' * len(string)

class Monitor(xbmc.Monitor):

    def __init__(self):
        self.get_settings()
        writeLog('Settings loaded', xbmc.LOGNOTICE)

    @classmethod
    def onSettingsChanged(cls):
        dialog = xbmcgui.Dialog()
        if dialog.yesno(ADDONNAME, ADDON.getLocalizedString(30037)): xbmc.executebuiltin('RestartApp()')

    def get_settings(self):
        __exnums = ADDON.getSetting('excludeNums')

        # transform possible userinput from e.g. 'p1, p2,,   p3 p4  '
        # to a list like this: ['p1','p2','p3','p4']

        __exnums = __exnums.replace(',', ' ')
        __exnums = __exnums.join(' '.join(line.split()) for line in __exnums.splitlines())

        self.exnum_list = __exnums.split(' ')
        self.server = ADDON.getSetting('phoneserver')
        self.dispMsgTime = int(re.match('\d+', ADDON.getSetting('dispTime')).group()) * 1000
        self.cCode = ADDON.getSetting('cCode')
        self.optShowOutgoing = True if ADDON.getSetting('showOutgoingCalls').upper() == 'TRUE' else False
        self.optMute = True if ADDON.getSetting('optMute').upper() == 'TRUE' else False
        self.volume = int(ADDON.getSetting('volume')) * 0.1
        self.optFade = True if ADDON.getSetting('optFade').upper() == 'TRUE' else False
        self.optPauseAudio = True if ADDON.getSetting('optPauseAudio').upper() == 'TRUE' else False
        self.optPauseVideo = True if ADDON.getSetting('optPauseVideo').upper() == 'TRUE' else False
        self.optPauseTV = True if ADDON.getSetting('optPauseTV').upper() == 'TRUE' else False
        self.optEarlyPause = True if ADDON.getSetting('optEarlyPause').upper() == 'TRUE' else False

        writeLog('Server IP/name:   %s' % (self.server))
        writeLog('excluded Numbers: %s' % (__exnums))
        writeLog('Display time:     %s' % (self.dispMsgTime))
        writeLog('Country code:     %s' % (self.cCode))
        writeLog('handle outgoings: %s' % (self.optShowOutgoing))
        writeLog('Change Volume:    %s' % (self.optMute))
        writeLog('Change to:        %s' % (self.volume))
        writeLog('Pause audio:      %s' % (self.optPauseAudio))
        writeLog('Pause video:      %s' % (self.optPauseVideo))
        writeLog('Pause tv:         %s' % (self.optPauseTV))
        writeLog('React on ring:    %s' % (self.optEarlyPause))
