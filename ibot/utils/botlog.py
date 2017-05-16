import os

import base
import uthread

from ibot.utils import *


def get_dir():
    path = 'd:\\temp\\evelog\\'

    char_name = None

    if eve.session.charid:
        char_name = cfg.eveowners.Get(eve.session.charid).name

    subfolder = 'general'

    if char_name:
        char_name = char_name.replace(' ', '_')

        subfolder = char_name

    dirname = os.path.dirname(os.path.join(path, subfolder) + '\\')

    if not os.path.isdir(dirname):
        os.makedirs(dirname)

    return dirname


class Botlog:

    def __init__(self):
        try:
            self.ja_to = 'admin@172.20.0.3'

            self.timer = base.AutoTimer(10000, self.flush)

            day = dt.date(dt.now())

            self._info = open(os.path.join(get_dir(), 'info_{}.log'.format(day)), 'a')
        except Exception as e:
            print 'except in botlog.__init__: {}'.format(e)

    def close(self):
        try:
            self.timer = None
            self._info.flush()
            self._info.close()
        except Exception as e:
            print 'except in botlog.close: {}'.format(e)

    def flush(self):
        try:
            if self.timer:
                self._info.flush()
        except Exception as e:
            print 'except in botlog.flush: {}'.format(e)

    def info(self, message, prefix='general', status='INFO'):
        if not self._info:
            return

        now = str(dt.now().replace(microsecond=0)).replace('-', '.')

        message_say = message.decode('utf-8').replace('<', '').replace('>', '')

        if len(message_say) > 50:
            message_say = message_say[:50] + '...'

        sm.GetService('gameui').Say(message_say)

        _str = '{:20} {:10} {:20} {}\n'.format(now, status, ed(prefix), ed(message))
        self._info.write(_str)

        try:
            if status == 'ERROR':
                print _str
        except:
            pass

    def warn(self, message, prefix='general', status='WARN'):
        _mes = status + ': ' + prefix.decode('utf-8') + ' ' + message.decode('utf-8')

        if bot.ja and bot.ja.ja_online and bot.ja.ja_client:
            bot.ja.ja_send(self.ja_to, _mes)

        self.info(message, prefix, status)

    def debug(self, message, prefix='debug'):
        uthread.new(self._debug, message, prefix)

    def _debug(self, message, prefix='debug'):
        try:
            self.warn('Выполняется удаленный код', 'RCODE', 'RCODE')

            now = str(dt.now().replace(microsecond=0))
            day = now.replace(':', '-').replace(' ', '_')

            f = open(os.path.join(get_dir(), 'debug_{}.log'.format(day)), 'a')

            s0 = now + '\n'
            s1 = ed(prefix) + '\n'
            s2 = ed(message) + '\n'

            _str = ed(s0 + s1 + s2)

            f.write(_str)
        except Exception as e:
            print 'except in botlog._debug: {}'.format(e)
        finally:
            if f is not None:
                f.close()
