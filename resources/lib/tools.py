# -*- coding: utf-8 -*-

import xbmc
import xbmcaddon
import xbmcgui
import re
import os
import json

__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('id')
__IconDefault__ = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'), 'resources', 'media', 'default.png'))

def writeLog(message, level=xbmc.LOGDEBUG):
    xbmc.log('[%s] %s' % (__addonname__, message.encode('utf-8')), level)

def notify(header, message, icon=__IconDefault__, dispTime=5000):
    xbmcgui.Dialog().notification(header.encode('utf-8'), message.encode('utf-8'), icon, dispTime)

def jsonrpc(query):
    return json.loads(xbmc.executeJSONRPC(json.dumps(query, encoding='utf-8')))

class Monitor(xbmc.Monitor):

    def __init__(self):
        writeLog('Settings loaded', xbmc.LOGNOTICE)
        self.get_settings()

    def onSettingsChanged(self):
        dialog = xbmcgui.Dialog()
        if dialog.yesno(__addonname__, __addon__.getLocalizedString(30037)): xbmc.executebuiltin('RestartApp()')

    def get_settings(self):
        __exnums = __addon__.getSetting('excludeNums')

        # transform possible userinput from e.g. 'p1, p2,,   p3 p4  '
        # to a list like this: ['p1','p2','p3','p4']

        __exnums = __exnums.replace(',', ' ')
        __exnums = __exnums.join(' '.join(line.split()) for line in __exnums.splitlines())

        self.exnum_list = __exnums.split(' ')
        self.server = __addon__.getSetting('phoneserver')
        self.dispMsgTime = int(re.match('\d+', __addon__.getSetting('dispTime')).group()) * 1000
        self.cCode = __addon__.getSetting('cCode')
        self.optShowOutgoing = True if __addon__.getSetting('showOutgoingCalls').upper() == 'TRUE' else False
        self.optMute = True if __addon__.getSetting('optMute').upper() == 'TRUE' else False
        self.volume = int(__addon__.getSetting('volume')) * 0.1
        self.optPauseAudio = True if __addon__.getSetting('optPauseAudio').upper() == 'TRUE' else False
        self.optPauseVideo = True if __addon__.getSetting('optPauseVideo').upper() == 'TRUE' else False
        self.optPauseTV = True if __addon__.getSetting('optPauseTV').upper() == 'TRUE' else False
        self.optEarlyPause = True if __addon__.getSetting('optEarlyPause').upper() == 'TRUE' else False
        self.useKlickTelReverse = True if __addon__.getSetting('useKlickTelReverse').upper() == 'TRUE' else False

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
        writeLog('React early:      %s' % (self.optEarlyPause))
        writeLog('Use klicktel:     %s' % (self.useKlickTelReverse))