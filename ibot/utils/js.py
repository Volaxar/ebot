import datetime
import random
from datetime import datetime as dt

import blue
import stackless

import xmpp
from ibot.utils import pickle


def db_select(_query, _params=None):
    data = {'type': 'select', 'query': _query, 'params': _params}
    
    return j_get_far('ruller', data)


def db_query(_query, _params=None):
    data = {'type': 'query', 'query': _query, 'params': _params}
    
    j_send_far('ruller', data)
    
    
def j_get_far(login, data):
    
    while True:
        rnd = str(random.randrange(1000000, 9999999))
        
        if rnd not in bot.questions:
            bot.questions[rnd] = 'wait_answer'
            
            break
    
    data['rnd'] = rnd
    
    bot.log.info('Отправляем запрос {} для {} = {}'.format(rnd, login, data), status='DEBUG')
    
    send_to(login, '?{}'.format(pickle.dumps(data)))
    
    now = dt.now()
    
    while bot.questions[rnd] == 'wait_answer':
        blue.pyos.synchro.SleepWallclock(50)
        
        if dt.now() - now > datetime.timedelta(seconds=6):
            bot.log.warn('Не удалось получить ответ на запрос {} от {}'.format(rnd, login), status='DEBUG')
            return 'error'
    
    answer = bot.questions[rnd]
    
    del bot.questions[rnd]
    
    return answer


def j_send_far(login, data):
    send_to(login, '?{}'.format(pickle.dumps(data)))


def set_bot_params(p_type, value):
    data = {'type': 'set_bot_params', 'p_type': p_type, 'value': value}
    j_send_far('ruller', data)


def j_far_message(login, datas):
    data = pickle.loads(datas)
    
    if data['type'] == 'answer':
        bot.log.info('Пришел ответ на запрос {} от {}, данные: {}'.format(data['rnd'], login, data['answer']),
                     status='DEBUG')
        
        bot.questions[data['rnd']] = data['answer']
    
    elif data['type'] == 'quest':
        bot.log.info('Пришел запрос {} от {}, данные: {}'.format(data['rnd'], login, data), status='DEBUG')
        
        if bot.macros and bot.macros.is_ready:
            bot.macros.j_quest(login, data)
        
        else:
            rec = {'rnd': data['rnd'], 'answer': 'error'}
            
            send_to(login, '?{}'.format(pickle.dumps(rec)))
    
    elif data['type'] == 'notification':
        if bot.macros and bot.macros.is_ready:
            bot.log.info('Пришло уведомление от {}, данные: {}'.format(login, data), status='DEBUG')
            
            bot.macros.j_notification(login, data)
        else:
            bot.log.info('Макрос не загружен, уведомление от {} будет проигнорировано, данные: {}'.format(login, data))
    
    else:
        bot.log.warn('Несовместимый формат сообщения: {}'.format(data), status='DEBUG')


def make_data(data):
    return str(data)[1:-1].replace(':', '|').replace(' ', '').replace(',', ';').replace('\'', '')


def parse_data(data):
    return dict([x.split('|') for x in data])


# Пришло уведомление
def notification(_from, func, *args):
    _from = _from.lower()
    
    if bot.macros and bot.macros.is_ready:
        bot.log.info('Пришло уведомление от {}, ф-я {}, аргументы: {}'.format(_from, func, args), status='DEBUG')
        
        bot.macros.notification(_from, func, *args)
    
    else:
        bot.log.info('Уведомление от {} будет проигнарировано, функция {}, агрументы: {}'.format(_from, func, args))


# Рассылка сообщений всем ботам или только с определенной ролью (при условии, что они в игре)
def send_to_role(msg, role=None):
    if not isinstance(role, list):
        if role:
            role = [role]
        else:
            role = []
    
    for v in bot.bots.values():
        if role and v['role'] not in role or not sm.GetService('onlineStatus').GetOnlineStatus(v['id'], True):
            continue
        
        if v['login'] == bot.login.lower():
            continue
        
        send_to(v['login'], msg)


# Отправить сообщение боту
def send_to(_to, msg):
    to = _to + '@172.20.0.3'
    
    stackless.tasklet(bot.ja.ja_send)(to, msg)


def send_hello():
    to_list = ['admin', 'control', 'ruller'] + [x['login'] for x in bot.bots.values()]
    
    for _bot in to_list:
        jid = '{}@172.20.0.3'.format(_bot)
        
        if jid != bot.ja.jid:
            bot.ja.ja_client.send(xmpp.Presence(to=jid, typ='subscribe'))
            bot.ja.ja_client.send(xmpp.Presence(to=jid, typ='available'))


def send_bye():
    to_list = ['admin', 'control', 'ruller'] + [x['login'] for x in bot.bots.values()]
    
    for _bot in to_list:
        jid = '{}@172.20.0.3'.format(_bot)
        
        if jid != bot.ja.jid:
            bot.ja.ja_client.send(xmpp.Presence(to=jid, typ='unavailable'))
