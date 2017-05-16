import maputils
import trinity
from eve.client.script.ui.services.menuSvcExtras import movementFunctions

import ibot.utils.bms as _bm
from ibot.utils import *
from ibot.utils.cnt import *


# Общий грид
class Place:
    def __init__(self, _id, _name, _pos):
        
        self.id = _id
        self.name = _name
        self.shotName = _name
        
        self.x = _pos[0]
        self.y = _pos[1]
        self.z = _pos[2]
        
        self.site = None
        
        self.type = None
    
    # Заглушки для методов, инициированных в подклассах
    def surfaceDist(self):
        if not session.solarsystemid:
            return None
        
        bp = sm.GetService('michelle').GetBallpark(True)
        
        if bp:
            ball = bp.GetBallById(self.id)
            
            if ball:
                return ball.surfaceDist
            
            else:
                pos = trinity.TriVector(self.x, self.y, self.z)
                
                return (pos - maputils.GetMyPos()).Length()
        
        return
    
    # Варпаем на место
    def warp(self, distance=0.0):
        bm = _bm.get_bookmark(self.name, 'Places')
        
        point = None
        
        if bm:
            point = BmPlace(bm.bookmarkID, bm.memo.strip(), (bm.x, bm.y, bm.z), bm)
        
        if point and not point.is_achived():
            bot.log.info('Варпаем на закладку {}'.format(self.name), bot.macros.role)
            
            do_action(3 + rnd_keys())
            
            movementFunctions.WarpToBookmark(bm, distance)
        
        elif not self.is_achived():
            bot.log.info('Варпаем к {}'.format(self.name), bot.macros.role)
            
            do_action(3 + rnd_keys())
            
            if self.type == 'anomaly':
                sm.GetService('menu').WarpToScanResult(self.id, distance)
            else:
                movementFunctions.WarpToItem(self.id, distance)
        
        else:
            bot.log.info('Место назначения достигнуто: {}'.format(self.name), bot.macros.role)
    
    # Достигнута ли текущая точка
    def is_achived(self):
        if not session.solarsystemid:
            return
        
        return self.surfaceDist() < gridDistance


# Закладки
class BmPlace(Place):
    def __init__(self, _id, _name, _pos, _bm):
        Place.__init__(self, _id, _name, _pos)
        
        self.type = 'bm'
        
        self.bm = _bm
    
    def surfaceDist(self):
        if not session.solarsystemid:
            return None
        
        sensorSuite = sm.GetService('sensorSuite')
        site = sensorSuite.GetBracketBySiteID(self.id)
        
        if site:
            return site.GetDistance()
        else:
            return Place.surfaceDist(self)
    
    # Варпаем на закладку
    def warp(self, distance=0.0):
        bot.log.info('Варпаем на закладку {}'.format(self.name), bot.macros.role)
        
        do_action(2 + rnd_keys())
        
        movementFunctions.WarpToBookmark(self.bm, distance)


# Аномальки и сигнатуры
class AnomalePlace(Place):
    def __init__(self, _id, _name, _pos, _type, dungeonNameID):
        Place.__init__(self, _id, _name, _pos)
        
        self.type = 'anomaly'
        self.dungeonNameID = dungeonNameID
        
        self.res_type = _type


class CrubPlace(Place):
    def __init__(self, _id, _name, _pos, dungeonNameID):
        Place.__init__(self, _id, _name, _pos)
        
        self.type = 'anomaly'
        self.shotName = _name[-3:]
        self.dungeonNameID = dungeonNameID
        
        self.status = None


# Поясы астероидов
class BeltPlace(Place):
    def __init__(self, _id, _name, _pos):
        Place.__init__(self, _id, _name, _pos)
        
        self.type = 'belt'


# Станции или цитадель
class StationPlace(Place):
    def __init__(self, _id, _name, _pos):
        Place.__init__(self, _id, _name, _pos)
        
        self.type = 'station'
    
    # Находимся ли на станции
    def is_achived(self):
        if session.stationid and session.stationid == self.id:
            return True
        
        if session.structureid and session.structureid == self.id:
            return True
        
        return False


# Планеты
class PlanetPlace(Place):
    def __init__(self, _id, _name, _pos):
        Place.__init__(self, _id, _name, _pos)
        
        self.type = 'planet'
    
    # Достигнута ли текущая точка
    def is_achived(self):
        if not session.solarsystemid:
            return
        
        return self.surfaceDist() < planetDistance
    
    # Варпаем на планету
    def warp(self, distance=100000.0):
        bot.log.info('Варпаем к планете {}'.format(self.name), bot.macros.role)
        
        do_action(2 + rnd_keys())
        
        movementFunctions.WarpToItem(self.id, distance)
