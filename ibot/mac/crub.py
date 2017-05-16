from ibot.mac.template.space import *


def run():
    if not bot.macros:
        bot.macros = Crub()


class Crub(Space):
    __notifyevents__ = [
        'OnSignalTrackerAnomalyUpdate',
        'OnLSC'
    ]
    
    # Инициализация класса
    def __init__(self, _run=True):
        
        self.actions = {
            'init': {
                'co': [
                    lambda: self.flag('init'),
                ],
                'do': self.init,
                'pr': 50
            },
            'wait_anomaly': {
                'co': [
                    lambda: self.flag('wait_anomaly')
                ],
                'do': self.wait_anomaly,
                'tm': None,
                'iv': 15000,
                'pr': 40
            },
        }
        
        Space.__init__(self, 'crub')
        
        # Загрузка параметров
        self.grl = self.s.ga('GrLogic', self.role)  # Группа, для разделения крабов по аномалькам
        self.default_status = self.s.ga('DefaultStatus', 'busy')  # Статус аномалек по-умолчанию
        self.busy_only_first = self.s.ga('OnlyFirst', True)  # Статус - занято, только для существующих аномалек
        self.anomaly_type = self.s.ga('AnomalyType', None)  # Тип аномалек для крабинга
        self.add_time = int(self.s.ga('AddTime', 60000))  # Задержки между запуском групп
        
        self.crub_place = nil  # Текущая аномалька - CrubPlace
        
        chList = self.s.ga('CrubChList', None)
        self.chList = {}
        
        if chList:
            for ch in chList.split(';'):
                c = ch.split(':')
                
                self.chList[int(c[0])] = int(c[1])
        
        if self.s.ga('SendToChannel', False) and session.solarsystemid in self.chList:
            if self.chList[session.solarsystemid] not in sm.GetService('LSC').channels:
                self.warn('Не открыт краб-канал, запуск макроса не возможен', self.role)
                
                sm.ScatterEvent('OnScriptBreak')
                
                return
        
        self.is_ready = True
        
        set_bot_params('role', self.role)
        set_bot_params('group', self.grl)
        
        pause(1000)
        
        self.add_flag(['init', 'wait_anomaly'])
        
        self.run_action()
    
    def init(self):
        pause(500)
        
        if self.check_in_station():
            self.undocking()
        
        elif self.check_in_inflight():
            
            self.update_places()
            
            self.del_flag('init')
    
    # Обновить список аномалек
    def update_places(self):
        if self.check_func() or self.flag('break'):
            return
        
        if self.i_am_is_primary():
            self.lock_func()
            
            res = self.get_anomaly_list()
            
            if res != 'error':
                
                bp = sm.GetService('michelle').GetBallpark(True)
                
                if bp:
                    data = {}
                    
                    sensorSuite = sm.GetService('sensorSuite')
                    handler = sensorSuite.siteController.GetSiteHandler(ANOMALY)
                    
                    sites = handler.GetSites()
                    
                    all_places = []
                    
                    # Добавляем новые аномальки на сервер
                    for v in sites.values():
                        if v.scanStrengthAttribute == const.attributeScanAllStrength:
                            if self.anomaly_type in localization.GetByMessageID(v.dungeonNameID):
                                if v.siteID not in res:
                                    data[v.siteID] = {}
                                    
                                    data[v.siteID]['site_id'] = v.siteID
                                    data[v.siteID]['name'] = v.GetName()
                                    data[v.siteID]['status'] = self.default_status
                                    data[v.siteID]['pos'] = v.position
                                    data[v.siteID]['dni'] = v.dungeonNameID
                                
                                all_places.append(v.siteID)
                    
                    if len(data) > 0:
                        self.set_anomaly_list(data)
                    
                    del_places = []
                    
                    # Удаляем аномальки на сервере
                    for k in res:
                        if k not in all_places:
                            del_places.append(k)
                    
                    if len(del_places) > 0:
                        self.del_anomaly_list(del_places)
                    
                    if self.busy_only_first:
                        self.default_status = 'free'
            
            self.unlock_func()
    
    # Ожидание свободной аномальки
    def wait_anomaly(self):
        if self.check_func() or self.flag('break'):
            return
        
        self.lock_func()
        
        place = self.get_anomaly(self.grl)
        
        if place:
            self.crub_place = CrubPlace(place['site_id'], place['full_name'], place['pos'], place['dni'])
            
            self.del_flag('wait_anomaly')
            
            self.run_action()
        
        else:
            if self.i_am_is_primary(group=self.grl):
                stackless.tasklet(self.mark_anomaly)()
        
        self.unlock_func()
    
    # Пометить свободную аномальку
    def mark_anomaly(self):
        if self.check_func() or self.flag('break'):
            return
        
        self.lock_func()
        
        place = self.sel_anomaly(self.grl)
        
        if place and place['status'] == 'pre':
            _add_time = 0
            send_flag = self.s.gan('SendToChannel', False)
            
            if send_flag:
                _add_time = self.add_time + get_random(1000, 20000)
            
            if self.act_is_ready('send_num_anomaly', add_time=_add_time, gr=self.grl, lock=True):
                
                if send_flag and not self.get_send_status(place['site_id']):
                    
                    if session.solarsystemid in self.chList:
                        wnd = sm.GetService('LSC').GetChannelWindow(self.chList[session.solarsystemid])
                        
                        if wnd:
                            do_action(3 + rnd_keys(), 5 + rnd_keys())
                            
                            wnd.input.SetValue(place.name[-3:])
                            
                            pause(100)
                            
                            wnd.InputKeyUp()
                            
                            self.warn('Отправили в краб-канал номер аномальки: {}'.format(place.name[-3:]), self.role)
                            
                            self.set_send_status(place['site_id'])
                    else:
                        self.warn('Краб-канал системы не задан', self.role)
                    
                    pause(1000)
                
                if self.get_anomaly_status(place['site_id'], self.grl) == 'pre':
                    self.set_anomaly_status(place['site_id'], 'marked')
        
        self.unlock_func()
    
    # region Вызовы сервера
    
    # Получить список аномалек
    def get_anomaly_list(self):
        rec = {'type': 'get_anomaly_list'}
        
        return j_get_far('ruller', rec)
    
    # Отправить список аномалек
    def set_anomaly_list(self, data):
        rec = {'type': 'set_anomaly_list', 'data': data}
        
        j_send_far('ruller', rec)
    
    # Удалить из списка аномалек
    def del_anomaly_list(self, data):
        rec = {'type': 'del_anomaly_list', 'data': data}
        
        j_send_far('ruller', rec)
    
    # Получить рабочую аномальку
    def get_anomaly(self, who=None):
        
        rec = {'type': 'get_anomaly', 'who': who}
        
        return j_get_far('ruller', rec)
    
    # Выбрать и пометить свободную аномальку
    def sel_anomaly(self, who=None):
        bp = sm.GetService('michelle').GetBallpark()
        
        pos = None
        
        if bp:
            ship = bp.GetBallById(util.GetActiveShip())
            
            if ship:
                pos = (ship.x, ship.y, ship.z)
        
        rec = {'type': 'sel_anomaly', 'who': who, 'pos': pos}
        
        return j_get_far('ruller', rec)
    
    # Получить статус аномали
    def get_anomaly_status(self, siteID, who=None):
        
        rec = {'type': 'get_anomaly_status', 'site_id': siteID, 'who': who}
        
        return j_get_far('ruller', rec)
    
    # Установить статус аномали
    def set_anomaly_status(self, siteID, status):
        
        rec = {'type': 'set_anomaly_status',
               'site_id': siteID,
               'status': status}
        
        j_send_far('ruller', rec)
    
    # Получить статус отправки в краб-канал
    def get_send_status(self, siteID):
        
        return bool(j_get_far('ruller', {'type': 'get_send_status', 'site_id': siteID}))
    
    # Установить статус отправки в краб-канал
    def set_send_status(self, siteID):
        
        j_send_far('ruller', {'type': 'set_send_status', 'site_id': siteID})
    
    # endregion
    
    # region События
    
    # Обновился список аномалек
    def OnSignalTrackerAnomalyUpdate(self, solarSystemID, addedAnomalies, removedAnomalies):
        if not self.is_ready: return
        
        stackless.tasklet(self.update_places)()
    
    def _OnLSC(self, channelID, method, identityInfo, args):
        if not self.i_am_is_primary() or not self.s.gan('SendToChannel', False):
            return
        
        if session.solarsystemid in self.chList:
            if isinstance(channelID, types.IntType) and channelID == self.chList[session.solarsystemid]:
                
                j_owns = [x['id'] for x in bot.bots.values()] + [session.charid]
                
                if method == 'SendMessage':
                    res = args[0]
                    
                    p = re.compile(r'(\d{3})')
                    res = p.findall(res)
                    
                    place_list = self.get_anomaly_list()
                    
                    for site_id in res:
                        if site_id in place_list:
                            
                            # Если номер написал не наш бот
                            if identityInfo[2][0] not in j_owns:
                                self.set_anomaly_status(site_id, 'busy')
    
    def OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args):
        Space.OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args)
        
        if not self.is_ready: return
        
        stackless.tasklet(self._OnLSC)(channelID, method, identityInfo, args)
        
        # endregion
