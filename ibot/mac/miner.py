from ibot.mac.template.space import *


# from inventorycommon.const import *
# from sensorsuite.overlay.sitetype import *


def run():
    if not bot.macros:
        bot.macros = Miner()


class Miner(Space):
    __notifyevents__ = [
    ]
    
    # TODO:
    
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
        }
        
        Space.__init__(self, 'miner')
        
        self.add_flag('init')
        
        self.is_ready = True
        
        self.run_action()
    
    def init(self):
        pause(500)
        
        if self.check_in_station():
            self.undocking()
        
        if self.check_in_inflight():
            self.init_places()
            
            self.del_flag('init')
    
    # Получить места копки
    def init_places(self):
        bp = sm.GetService('michelle').GetBallpark(True)
        
        if not bp:
            return
        
        self.clear_places()
        
        sensorSuite = sm.GetService('sensorSuite')
        handler = sensorSuite.siteController.GetSiteHandler(ANOMALY)
        
        # Добавляем гравики
        for k, v in handler.GetSites().items():
            if v.scanStrengthAttribute == const.attributeScanGravimetricStrength:
                if not self.get_place_by_id(v.siteID):
                    if v.dungeonNameID in cnt.groupIce:
                        _type = 'ice'
                    elif v.dungeonNameID in cnt.groupGravics:
                        _type = 'ore'
                    else:
                        _type = None
                    
                    if _type:
                        self.add_place(AnomalePlace(v.siteID, v.GetName(), v.position, _type, v))
        
        # Добавляем белты
        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.groupID == groupAsteroidBelt and not self.get_place_by_id(ball_id):
                self.add_place(BeltPlace(ball.id, slim.name, (ball.x, ball.y, ball.z)))
    
    # region Служебные функции
    
    pass
    
    # endregion
