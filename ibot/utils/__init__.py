import blue

import cnt
from ibot.utils.js import *


# Генерирование случайной паузы
def get_random(fromtime=500, totime=1000):
    if fromtime > totime:
        fromtime = totime
    
    return float(random.randrange(fromtime, totime)) / 1000


def rand_pause(fromtime=500, totime=1000):
    pause(get_random(fromtime, totime) * 1000)


def pause(ms=None, self=None):
    if ms:
        if self and hasattr(self, 'is_break'):
            count = 1
            remain = 0
            
            tick = 500
            
            if ms > tick:
                count = int(ms / tick)
                remain = ms - (count * tick)
            
            for x in range(count):
                if self.is_break:
                    remain = 0
                    break
                
                blue.pyos.synchro.SleepWallclock(tick)
            
            if remain > 0:
                blue.pyos.synchro.SleepWallclock(remain)
        else:
            blue.pyos.synchro.SleepWallclock(ms)
    else:
        blue.pyos.synchro.Yield()


# До выключения серверов осталось меньше x минут?
def is_downtime():
    now = datetime.datetime.now()
    
    hour = now.time().hour
    minute = now.time().minute
    
    if hour == 15 and minute >= 53:
        return True
    
    return False


def get_last_dt():
    now = datetime.datetime.now()
    
    if now.hour < 16:
        day = (now - datetime.timedelta(days=1)).day
    else:
        day = now.day
    
    if now.day < day:
        month = now.month - 1
        
        if month == 0:
            month = 12
    else:
        month = now.month
    
    return datetime.datetime(now.year, month, day, 16, 0, 0)


# Ожидаем окончания действия таймера смены сессии
def wait_session_timer():
    while blue.os.GetSimTime() < session.nextSessionChange:
        pause()


def get_attr(itemID, attributeID):
    dogmaLocation = sm.GetService('clientDogmaIM').GetDogmaLocation()
    if dogmaLocation.IsItemLoaded(itemID):
        return dogmaLocation.GetAccurateAttributeValue(itemID, attributeID)
    
    typeID = sm.GetService('invCache').GetInventoryFromId(itemID).GetTypeID()
    
    return get_type_attr(typeID, attributeID)


def get_type_attr(typeID, attributeID):
    info = sm.GetService('godma').GetStateManager().GetShipType(typeID)
    return getattr(info, cfg.dgmattribs.Get(attributeID).attributeName)


# Строку параметров переводит в числовой массив
def load_set_list(param):
    params = []
    for res in param.split(','):
        params.append(int(res.strip()))
    
    return params


# Открытые MessageBox
def get_form(guid):
    forms = []
    
    for wnd in uicore.registry.GetWindows():
        if wnd.__guid__ == guid:
            forms.append(wnd)
    
    return forms


# Запрос на присоединение к флоту
def msg_box_close():
    pause()
    
    for mbox in get_form('form.MessageBox'):
        caption = mbox.FindChild('EveCaptionLarge').text.encode('utf-8')
        
        # if caption == 'Присоединиться к флоту?':
        #     mbox.CloseByUser()
        #     bot.log.info('Закрываем окно присоединения к флоту', 'miner  ')


def verify_text(text):
    for word in cnt.good_words:
        if word in text:
            return -1
    
    for word in cnt.bad_words[0]:
        if word in text:
            return 0
    
    for word in cnt.bad_words[1]:
        if word in text:
            return 1
    
    return -1


# Получаем список ботов из БД
def get_all_bots():
    query = 'SELECT charid, login, charname FROM eve_bot WHERE login <> %s'
    result = db_select(query, (bot.login,))
    
    if not result or result == 'error':
        return []
    
    return result


def Say(msg):
    sm.GetService('gameui').Say(msg.decode('utf-8'))


# Регистрация событий
def reg_notify(obj, __notifyevents):
    for notify in __notifyevents:
        sm.RegisterForNotifyEvent(obj, notify)


def unreg_notify(obj, __notifyevents):
    for notify in __notifyevents:
        sm.UnregisterForNotifyEvent(obj, notify)


def rnd_keys(_from=0, _to=5):
    return random.randrange(_from, _to)


def do_action(numClick=0, numKey=0):
    uicore.uilib._globalClickCounter += numClick
    uicore.uilib._globalKeyDownCounter += numKey
    
    uicore.uilib.RegisterAppEventTime()


def get_login(charname):
    try:
        login = None
        
        f = open('z:\\evelib\\ibot\\logins.txt')
        fd = f.readlines()
        
        for item in fd:
            n, l = item.split('=')
            
            if n == charname:
                login = l.replace('\n', '')
                break
        
        f.close()
        
        return login
    except:
        return None


def ed(message):
    string = ''
    
    if isinstance(message, unicode):
        string = message.encode('utf-8')
    elif isinstance(message, str):
        string = message.decode('utf-8').encode('utf-8')
    else:
        string = unicode(message).encode('utf-8')
    
    return string
