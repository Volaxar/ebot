# Скрипт выгрузки ask ордеров в текущем регионе

import uthread
import util

from ibot.mac import Macros
from ibot.utils import *
from ibot.utils import progress


def run():
    if not hasattr(sm.bot, 'export_orders'):
        sm.bot.export_orders = ExportOrders()


class ExportOrders(Macros):
    __notifyevents__ = [
    ]
    
    # Инициализация класса
    def __init__(self):
        Macros.__init__(self)
        
        uthread.new(self.__action)
    
    # Уничтожение класса
    def __deinit__(self):
        Macros.__deinit__(self)
        
        del sm.bot.export_orders
    
    # Основной метод скрипта
    def __action(self):
        
        timestart = datetime.datetime.now()
        
        type_ids = sm.bot.trade.get_type_ids(allow_t=True)
        
        p = progress.Progress()
        
        p.start(len(type_ids), 10)
        
        for type_id in type_ids:
            if poe(self):
                return
            
            p.tick()
            
            self.clear_orders(eve.session.regionid, type_id)
            
            min_price = sm.bot.trade.get_min_price(type_id)
            
            volume = sm.bot.trade.get_volume(type_id)
            
            if not min_price or not volume:
                continue
            
            rand_pause()
            
            _ords = sm.ProxySvc('marketProxy').GetOrders(type_id)
            
            ords = {'asks': _ords[0], 'bids': _ords[1]}
            
            date = datetime.datetime.now()
            
            if len(ords['asks']) == 0 and len(ords['bids']) == 0:
                continue
            
            for key in ords.keys():
                ords[key] = [list(x[:-1]) for x in ords[key]]
                
                exclude = []
                
                for item in ords[key]:
                    solar_system = cfg.mapSystemCache.Get(item[12])
                    
                    if item[0] > min_price and key == 'asks' or item[0] < min_price and key == 'bids' \
                            or solar_system.securityStatus < 0.5:
                        exclude.append(item)
                        continue
                    
                    item[8] = util.FmtDate(item[8])
                    
                    item.append(date)
                    item.append(sm.GetService('clientPathfinderService').GetAutopilotJumpCount(XXXXXXXX, item[12]))
                
                for x in exclude:
                    ords[key].remove(x)
                
                if len(ords[key]) > 0:
                    ords[key] = [tuple(x) for x in ords[key]]
                    
                    self.unload_types(key, ords[key])
        
        self.clear_orders(eve.session.regionid, None, timestart)
        
        sm.ScatterEvent('OnExportOrdersFinished')
        
        self.__deinit__()
    
    @staticmethod
    def clear_orders(region_id, type_id=None, time_start=None):
        query = "DELETE FROM trade_asks WHERE region_id = %s"
        params = [region_id]
        
        if type_id:
            query += " AND type_id = %s"
            params.append(type_id)
        
        if time_start:
            query += " AND created_at < %s"
            params.append(time_start)
        
        sm.bot.db.query(query, tuple(params))
    
    @staticmethod
    def unload_types(name, params):
        query = "INSERT INTO trade_" + name + ' ' + \
                "(price, vol_remaining, type_id, ranges, order_id, vol_entered, min_volume, bid, " \
                "issue_date, duration, station_id, region_id, solarsystem_id, created_at, jumps) " \
                "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        sm.bot.db.query(query, params)
