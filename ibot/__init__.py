import sys
import types
import stackless
import __builtin__

from datetime import datetime as dt

from ibot.utils import *
from ibot.utils.js import *

from ibot.utils import pickle

from ibot.utils import ja
from ibot.utils import chat as _chat
from ibot.utils import botlog

from ibot.caps import replace


def load_plugins(_type):
    import os

    plugins = {}

    for fname in os.listdir('Z:\\EveLib\\ibot\\' + _type + '\\'):

        if fname.endswith('.py') and fname != '__init__.py':
            plugins[fname[:-3]] = __import__('ibot.' + _type + '.' + fname[:-3], globals(), locals(), [''])
            reload(plugins[fname[:-3]])

            if _type == 'cmd':
                if not hasattr(bot, fname[:-3]):
                    setattr(bot, fname[:-3], plugins[fname[:-3]].run)

    return plugins


def clear_bot():
    filenames = []
    for modulename, moduleinfo in sys.modules.items():

        try:
            filenames.append((modulename, moduleinfo.__file__))
        except Exception:
            continue

    for filename in filenames:
        if not filename[1].lower().endswith('.py'):
            continue
        try:

            if filename[0] == 'ibot':
                continue

            del sys.modules[filename[0]]
        except Exception:
            continue

    del sys.path[2]

    del sys.modules['ibot']  # Удалять последним


class Bot:
    __notifyevents__ = [
        'ProcessShutdown',
        'OnKillBot',
        # 'OnLSC',
        # 'OnChannelsJoined',
        # 'OnChannelsLeft'
    ]

    def __init__(self):

        self.ja = None
        self.db = None

        self.log = None

        self.role = ''

        self.login = None
        self.char = None

        self.is_ready = False

        self.wnds = {}
        self.chats = {}

        self._ja = None

        self.mac = None
        self.cmd = None

        self.macros = None

        self.change_args = {}

        self.questions = {}  # Список запросов ботам

        self.bots = {}

        reg_notify(self, Bot.__notifyevents__)

        stackless.tasklet(self.__prepare)()

    def __deinit__(self):
        set_bot_params('online', None)

        if hasattr(self.macros, 'OnScriptBreak'):
            self.macros.OnScriptBreak()

        unreg_notify(self, Bot.__notifyevents__)

        if self._ja:
            self._ja.KillTimer()

        self._ja = None

        if self.ja:
            self.ja.ja_close()

        self.ja = None

        # tmp = []
        # for _id in self.chats:
        #     tmp.append(_id)
        #
        # for _id in tmp:
        #     self.del_chat(_id)

        if self.log:
            self.log.info('Конец записи')
            self.log.close()
            self.log = None

        self.replace.undo()

        delattr(__builtin__, 'bot')

        clear_bot()

    def ProcessShutdown(self):
        self.__deinit__()

    def verify_ja(self):
        try:
            if not self.ja.ja_online:
                self.ja.ja_close()

                self.ja = ja.Ja(self.login.lower())

            # for k, v in self.chats.items():
            #     if not v['ja'].ja_online:
            #         v['ja'].ja_close()
            #
            #         self.chats[k]['ja'] = _chat.Chat(k)
        except Exception as e:
            print 'bot.verify_ja: {}'.format(e)

    def __prepare(self):
        try:
            while not hasattr(__builtin__, 'bot'):
                pause()

            self.char = cfg.eveowners.Get(eve.session.charid).name

            self.login = get_login(self.char)

            self.replace = replace.Replace()

            self.mac = load_plugins('mac')  # Макросы
            self.cmd = load_plugins('cmd')  # Команды

            if self.login is None:
                stackless.tasklet(self.__deinit__)()

                return

            self.log = botlog.Botlog()
            self.ja = ja.Ja(self.login.lower())

            self.log.info('Начало записи')

            self._ja = base.AutoTimer(10000, self.verify_ja)

            stackless.tasklet(self.__inflight)()

        except Exception as e:
            self.log.info('except in bot.__prepare: {}'.format(e), status='ERROR')

    def __inflight(self):
        set_bot_params('online', True)

        self.is_ready = True

    def new_chat(self, channel_id, channel_name):
        self.chats[channel_id] = {}
        self.chats[channel_id]['ja'] = _chat.Chat(channel_id, channel_name)

    def del_chat(self, channnel_id):
        if channnel_id in self.chats:
            self.chats[channnel_id]['ja'].ja_close()
            self.chats[channnel_id]['ja'] = None

            del self.chats[channnel_id]

    def from_chat(self, channel_id, user, message):
        if channel_id in self.chats:
            message = str(user) + ' >\n' + message
            self.chats[channel_id]['ja'].ja_send('admin@172.20.0.3', message)

    def change_role(self, _msg):
        stackless.tasklet(self._change_role)(_msg)

    def _change_role(self, _msg):

        old_role = self.macros.role

        sm.ScatterEvent('OnScriptBreak')

        pause(5000)

        args = ()

        line = _msg.split(':')
        func = line[0]

        if len(line) > 1:
            args = tuple([eval(x) for x in line[1].split(';')])

        if func in self.mac.keys():
            stackless.tasklet(self.mac[func].run)(*args)

            self.log.info('Смена роли {}, старая роль {}, новая роль {}'.format(self.login, old_role, func))

    def OnKillBot(self):
        stackless.tasklet(self.__deinit__)()

    def OnChannelsJoined(self, channelIDs):
        for channelID in channelIDs:
            if isinstance(channelID, types.IntType):

                lsc = sm.GetService('LSC')

                if channelID not in lsc.channels:
                    return

                channel = lsc.channels[channelID]

                if channel.info.temporary:
                    charID = None

                    for _id in channel.memberList:
                        if _id != session.charid:
                            charID = _id
                            break

                    if charID:
                        charName = cfg.eveowners.Get(charID).name
                        charName = charName.replace(' ', '_').replace('\'', '_')

                        stackless.tasklet(self.new_chat)(channelID, charName)

    def OnChannelsLeft(self, toLeave):
        for channel in toLeave:
            channelID = channel[0]

            if isinstance(channelID, types.IntType):
                stackless.tasklet(self.del_chat)(channelID)

    def OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args):
        if isinstance(channelID, types.IntType):
            lsc = sm.GetService('LSC')

            if channelID not in lsc.channels:
                return

            channel = lsc.channels[channelID]

            if channel.info.temporary and identityInfo[2][0] != session.charid:
                if method == 'SendMessage':
                    stackless.tasklet(self.from_chat)(channelID, identityInfo[2][1], args[0])
                elif method == 'LeaveChannel':
                    if lsc.GetMemberCount(channelID) <= 1:
                        lsc.LeaveChannel(channelID)

