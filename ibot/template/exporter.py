# Скрипт выгрузки ордеров по регионам

import datetime

import localization
import uthread

from ibot.mac import Macros

MAX_EXPORT_HOURS = 1


def run(route=None):
    if not hasattr(sm.bot, 'exporter') and route:
        sm.bot.exporter = Exporter(route)


class Exporter(Macros):
    __notifyevents__ = [
        'OnFlyToFinished',
        'OnExportOrdersFinished'
    ]
    
    # Инициализация класса
    def __init__(self, route):
        Macros.__init__(self)
        
        self.info = sm.bot.log.info
        
        self.last_region = None
        
        self.info('Запуск exporter`а', 'exporter')
        self.info('Маршрут: ' + str(route), 'exporter')
        
        if isinstance(route, list):
            self._route = route
        else:
            self._route = [route]
        
        uthread.new(self.__action)
    
    # Уничтожение класса
    def __deinit__(self):
        self.info('Остановка exporter`а', 'exporter')
        
        Macros.__deinit__(self)
        
        del sm.bot.exporter
    
    # Основной метод скрипта
    def __action(self):
        if self.__region_is_exported(eve.session.regionid) and eve.session.regionid != self.last_region:
            
            self.last_region = eve.session.regionid
            
            _str = 'Начинаем выгрузку ордеров в регионе ' + str(localization.GetByMessageID(
                cfg.mapRegionCache.Get(eve.session.regionid).nameID)) + ' (' + str(eve.session.regionid) + ')'
            
            self.info(_str, 'exporter')
            
            sm.bot.mac['export_orders'].run()
        else:
            
            point = self.__get_next_point()
            
            _str = 'Перемещаемся в систему ' + str(localization.GetByMessageID(
                cfg.mapSystemCache.Get(point).nameID)) + ' (' + str(point) + ')'
            
            self.info(_str, 'exporter')
            
            sm.bot.mac['fly_to'].run(point)
    
    # Нужно ли выгружать указанный регион
    def __region_is_exported(self, region):
        query = "SELECT MAX(created_at) FROM trade_asks WHERE region_id = %s"
        
        for x in self._route:
            region_id = sm.GetService('map').GetRegionForSolarSystem(x)
            
            # Если регион в списке на выгрузку
            if region_id == region:
                rle = sm.bot.db.select(query, (region_id,))[0][0]
                
                # Если данные в регионе не выгружались или выгружались раньше MAX_EXPORT_HOURS часов назад
                if not rle or rle and datetime.datetime.now() - rle > datetime.timedelta(hours=MAX_EXPORT_HOURS):
                    return True
                else:
                    break
        
        return False
    
    def __get_next_point(self):
        next_point = None
        
        for x in self._route:
            region_id = sm.GetService('map').GetRegionForSolarSystem(x)
            
            if region_id == eve.session.regionid:
                if x == eve.session.solarsystemid2:
                    idx = self._route.index(x)
                    
                    if idx == len(self._route) - 1:
                        next_point = self._route[0]
                    else:
                        next_point = self._route[idx + 1]
                else:
                    next_point = x
                
                break
        
        if not next_point:
            _range = []
            
            for x in self._route:
                _range.append(sm.GetService('clientPathfinderService').GetAutopilotJumpCount(session.solarsystemid2, x))
            
            next_point = self._route[_range.index(min(_range))]
        
        return next_point
    
    def OnFlyToFinished(self):
        uthread.new(self.__action)
    
    def OnExportOrdersFinished(self):
        uthread.new(self.__action)
    
    # Сообщение постановки или отмены паузы
    def OnScriptPause(self, pause):
        Macros.OnScriptPause(self, pause)
        
        uthread.new(self.__action)
