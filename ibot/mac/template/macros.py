from ibot.utils.include import *

# Кеш проверок, сохраняет результаты вызова проверок
checks_cache = {}


# Декоратор, вызывается для проверок check_, кеширует результаты для повторных вызовов
def cached(func):
    def wrapper(self, *args, **kwargs):
        name = '{}_{}'.format(func.__name__, '_'.join([str(x) for x in args]))
        
        if name not in checks_cache:
            checks_cache[name] = func(self, *args, **kwargs)
        
        return checks_cache[name]
    
    return wrapper


class Macros:
    __notifybase__ = [
        'OnScriptBreak',
        'OnScriptPause'
    ]
    
    __notifyevents__ = [
    ]
    
    # Инициализация класса
    def __init__(self, _role=None):
        self.is_ready = False
        
        self.info = bot.log.info
        self.warn = bot.log.warn
        
        # ---
        
        actions = {}
        
        self.flags = []  # Переключатели событий (wait, hide, full_cargo, ...)
        self.funcs = []  # Флаги функции, для исключения повторного вызова
        
        self.actions = dict(actions, **self.actions)  # Настройки действий
        
        self.role = _role  # Имя роли
        self.main_action = None  # Текущее действие
        
        self._run_action = None  # Таймер
        
        self._check_pass = None  # Таймер, проверка на бездействие
        self.check_pass_limit = 5  # Допустимое время бездействия в минутах
        self.check_pass_pause = True  # Пауза при проверке бездействия
        self.last_pass = dt.now()  # Время выполнения последнего действия
        
        # ---
        
        self.pendings = {}  # Задержки
        
        self.places = {}
        
        # ---
        
        reg_notify(self, Macros.__notifyevents__ + Macros.__notifybase__ + self.__class__.__notifyevents__)
        
        if _role:
            # Загрузка настроек
            self.s = setting.Setting(_role)
            
            self.s.updateall()
            
            set_bot_params('online', True)
            
            self.upd_bots_params()
        
        self._check_pass = base.AutoTimer(10000, self.check_pass)
    
    # Уничтожение класса
    def __deinit__(self):
        set_bot_params('role', None)
        
        unreg_notify(self, Macros.__notifyevents__ + Macros.__notifybase__ + self.__class__.__notifyevents__)
        
        self.clear_places()
        
        self.s = None
        
        self.unlock_func('do_action')
        
        if self._run_action:
            self._run_action.KillTimer()
            self._run_action = None
        
        if self._check_pass:
            self._check_pass.KillTimer()
            self._check_pass = None
        
        for name, action in self.actions.items():
            
            timer = action.get('tm')
            
            if timer:
                self.actions[name]['tm'] = None
        
        for pen in self.pendings:
            self.pendings[pen] = None
        
        if hasattr(bot, 'macros'):
            delattr(bot, 'macros')
        
        self.info('Макрос остановлен', self.role)
    
    # Только один экземпляр do_action выполняется, при повторных вызовах ожидает выполнения предыдущего экземпляра
    def run_action(self):
        if self.check_func() or self.flag('break'):
            return
        
        self.lock_func()
        
        if self.check_func('do_action'):
            if not self._run_action:
                self._run_action = base.AutoTimer(500, self.run_action)
            
            self.unlock_func()
            return
        
        if self._run_action:
            self._run_action.KillTimer()
            self._run_action = None
        
        stackless.tasklet(self.do_action)()
        
        self.unlock_func()
    
    # Точка входа в макрос
    # Доступные фазы для действий
    #   pr - приоритет, по умолчанию None (priority), чем больше число, тем выше приоритет
    #   pl - флаг параллельности, если True выполнение действия не приводит к блокировке остальных действий
    #        у параллельных действий не может быть места выполенния, они всегда выполняются в текущем месте
    #   co - условия, массив функций возвращающих True или False (conditions) - обязательный параметр
    #   po - функция возвращающая место действия
    #   go - функция перемещения к месту действия (go point)
    #   do - функция действия (do action) - обязательный параметр
    #   iv - интервал таймера
    #   tm - таймер, если не запущен  = None
    #   ft - функция выполняющаяся один раз перед началом основного действия (first) - не реализовано !!!!!!!!!!!
    #   ed - функция выполняющаяся один раз после завершения основного действия (end)
    def do_action(self):
        if self.check_func('do_action') or self.flag('break') or sm.GetService('autoPilot').InWarp():
            return
        
        self.lock_func('do_action')
        
        wait_session_timer()
        
        actions_to_do = []  # Список действий которые будут выполены
        
        current_action = None  # Текущее действие
        
        # Проходим по общему списку, для составления списка активных действий
        for name, action in self.actions.items():
            priority = action.get('pr', 0)
            parallel = action.get('pl')
            
            conditions = action.get('co')
            
            # Если выполняются все условия для действия
            if all(x() for x in conditions):
                # Возможно параллельное выполение действия
                if parallel:
                    actions_to_do.append(name)
                # Вычисляем действие с максимальным приоритетом
                elif not current_action or current_action and self.actions[current_action].get('pr', 0) < priority:
                    current_action = name
        
        # Отключаем основное действие
        if self.main_action:
            
            # Место выполения основного действия
            place = self.get_place(self.main_action)
            
            # Если текущее действие отсутствует
            # Если текущее действие не равно основному действию (сменилась основная задача)
            # Если текущее и основное действия совпадают, но не достигнута точка выполнения действия
            if not current_action or current_action != self.main_action or place and not place.is_achived():
                
                main_action = self.main_action
                self.main_action = None
                
                timer = self.actions[main_action].get('tm')
                
                if timer:
                    self.info('Отключаем таймер для действия: {}'.format(main_action), self.role)
                    self.actions[main_action]['tm'] = None
                
                exit_action = self.actions[main_action].get('ed')
                
                if exit_action:
                    self.info('Выход для действия: {}'.format(main_action), self.role)
                    stackless.tasklet(exit_action)()
                    
                    checks_cache.clear()  # Очищаем кеш после вызова вех проверок
                    
                    self.unlock_func('do_action')
                    
                    return
        
        # Текущее действие делаем основным
        if current_action:
            action = self.actions.get(current_action)
            
            if action and not action.get('tm'):
                actions_to_do.append(current_action)
                
                self.main_action = current_action
        
        # Выполняем текущие действия
        for name in actions_to_do:
            action = self.actions[name]
            place = self.get_place(name)
            
            # Если достигли заданного места или место для действия не задано, выполняем действие
            if place and place.is_achived() or 'po' not in self.actions[name]:
                do = action.get('do')
                
                if do:
                    interval = action.get('iv')
                    
                    try:
                        # Если таймер предусмотрен, но не задан
                        if 'tm' in action and not action.get('tm') and interval:
                            self.info('Запускаем таймер действия: {}'.format(name), self.role)
                            self.actions[name]['tm'] = base.AutoTimer(int(interval), do)
                        else:
                            self.info('Запускаем действие: {}'.format(name), self.role)
                            stackless.tasklet(do)()
                    except:
                        pass
                
                continue
            
            # Если не достигли места выполнения действия, перемещаемся к нему
            if place and not place.is_achived():
                go = action.get('go')
                
                if go:
                    self.info('Перемещаемся к месту для действия: {} - {}'.format(name, place.name), self.role)
                    stackless.tasklet(go)(place)
            
            if not place:
                self.info('Место назначение не задано: action - {}'.format(action), self.role)
        
        checks_cache.clear()  # Очищаем кеш после вызова вех проверок
        
        self.unlock_func('do_action')
    
    # Получить место выполнения указанного действия
    def get_place(self, action):
        if action and action in self.actions:
            func_place = self.actions[action].get('po')
            
            if func_place:
                return func_place()
        
        return None
    
    def j_notification(self, login, data):
        if not self.is_ready: return
        
        if data['func'] == 'update_data':
            stackless.tasklet(self.upd_bot)(data['args'])
        
        elif data['func'] == 'add_flag':
            self.add_flag(data['flag'])
        
        elif data['func'] == 'del_flag':
            self.del_flag(data['flag'])
    
    def j_quest(self, login, data):
        if not self.is_ready: return
    
    # Пришло уведомление
    def notification(self, _from, func, *args):
        if not self.is_ready: return
        
        if func == 'add_flag':
            self.add_flag(args[0])
        
        elif func == 'del_flag':
            self.del_flag(args[0])
    
    # region Связь ботов
    
    # Обновляем информацию о боте
    def upd_bot(self, data=None):
        if not data or 'login' not in data:
            self.info('Отсутствуют данные для обновления данных: {}'.format(data), self.role)
            
            return
        
        login = data['login']
        
        if login not in bot.bots:
            bot.bots[login] = {}
        
        for k, v in data.items():
            bot.bots[login][k] = v
        
        self.info('Обновляем информацию о {}: {}'.format(bot.bots[login]['name'], data), self.role, 'DEBUG')
    
    # Получить параметры уже работающих ботов
    def upd_bots_params(self):
        data = {'type': 'get_bots_params'}
        
        ans = j_get_far('ruller', data)
        
        if ans != 'error':
            for rec in ans:
                self.upd_bot(rec)
    
    # Получить список ботов для роли
    def get_bots_by_role(self, role):
        bots = []
        
        for v in bot.bots.values():
            if v['role'] == role:
                bots.append(v)
        
        return bots
    
    # Проверяем выставление любого флага в списке
    def flag(self, flags):
        if not isinstance(flags, list):
            flags = [flags]
        
        for flag in flags:
            if flag in self.flags:
                return True
        
        return False
    
    # Добавляем новый флаг
    def add_flag(self, flags):
        if not isinstance(flags, list):
            flags = [flags]
        
        for flag in flags:
            if not self.flag(flag):
                self.info('Устанавливаем флаг - {}'.format(flag), self.role)
                self.flags.append(flag)
    
    # Удаляем флаг
    def del_flag(self, flags):
        if not isinstance(flags, list):
            flags = [flags]
        
        for flag in flags:
            if self.flag(flag):
                self.info('Удаляем флаг - {}'.format(flag), self.role)
                self.flags.remove(flag)
    
    # Функция выполняется
    def lock_func(self, funcName=None):
        if not funcName:
            info = traceback.extract_stack()
            funcName = '' + info[-2][0] + '_' + info[-2][2]
        
        if funcName not in self.funcs:
            self.funcs.append(funcName)
    
    # Выполнение функции завершено
    def unlock_func(self, funcName=None):
        if not funcName:
            info = traceback.extract_stack()
            funcName = '' + info[-2][0] + '_' + info[-2][2]
        
        if funcName in self.funcs:
            self.funcs.remove(funcName)
    
    # Проверка выполнения функции
    def check_func(self, funcName=None):
        if not funcName:
            info = traceback.extract_stack()
            funcName = '' + info[-2][0] + '_' + info[-2][2]
        
        return funcName in self.funcs
    
    # Проверяем активна ли задержка
    def pen(self, name):
        return name in self.pendings
    
    # Добавляем или обновляем задержку
    def set_pen(self, name, pending):
        if name in self.pendings:
            # Если новая задержка больше чем осталось старой
            if self.pendings[name].wakeupAt < blue.os.GetWallclockTime() / 10000 + pending:
                self.pendings[name].Reset(pending)
        else:
            self.pendings[name] = base.AutoTimer(pending, self.pending, name)
    
    # Функция задержки
    def pending(self, name):
        if name in self.pendings:
            self.pendings[name] = None
            del self.pendings[name]
    
    # Проверка бездействия
    def check_pass(self):
        if self.check_pass_pause:
            return
        
        if dt.now() - self.last_pass > datetime.timedelta(minutes=self.check_pass_limit) and not self.pen('pass'):
            self.warn('Бот бездействует больше {} мин.'.format(self.check_pass_limit), self.role)
            
            self.set_pen('pass', 60000)
    
    # Выполняется какое-либо действие
    def do_pass(self):
        self.last_pass = dt.now()
        self.check_pass_pause = False
    
    # Включить паузу проверки бездействия
    def pause_pass(self):
        self.check_pass_pause = True
    
    # Добавляем текущее место в общий список
    def add_place(self, place):
        if place.id not in self.places:
            self.places[place.id] = place
    
    # Удаляем место
    def del_place(self, place_id):
        if place_id in self.places:
            del self.places[place_id]
    
    # Получить текущее положение
    def get_current(self):
        for place in self.places.values():
            if place.is_achived():
                return place
        
        return
    
    # Получить place по его id
    def get_place_by_id(self, _id):
        
        if _id in self.places:
            return self.places[_id]
        
        return
    
    # Список ИД по краткому имени
    def get_ids_by_sn(self, _name):
        ids = []
        
        for k, v in self.places.items():
            if v.shotName == _name:
                ids.append(k)
        
        return ids
    
    def clear_places(self):
        self.places = {}
    
    # endregion
    
    # region Работа с событиями
    
    @staticmethod
    def add_notify(cls):
        Macros.__notifyevents__ += cls.__notifyevents__
    
    # endregion
    
    # region События
    
    # Сообщение завершения работы скрипта
    def OnScriptBreak(self):
        if 'break' not in self.flags:
            self.is_ready = False
            
            self.add_flag('break')
            
            self.info('Работа макроса прервана, команда break', self.role)
            self.__deinit__()
            
            bot.macros = None
    
    # Сообщение переключателя паузы
    def OnScriptPause(self):
        # Скрипт на паузе, паузу отключаем
        if 'pause' in self.flags:
            self.del_flag('pause')
            
            self.info('Снимаем скрипт с паузы', self.role)
            reg_notify(self, Macros.__notifyevents__ + self.__class__.__notifyevents__)
        else:
            self.add_flag('pause')
            
            self.info('Ставим скрипт на паузу', self.role)
            unreg_notify(self, Macros.__notifyevents__ + self.__class__.__notifyevents__)
            
            # endregion
