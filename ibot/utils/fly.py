from eve.client.script.ui.services.menuSvcExtras import movementFunctions

from ibot.utils import *


# Возвращает следующий объект в маршруте врата или станцию
def get_next_point():
    bp = sm.GetService('michelle').GetBallpark()
    
    if not bp:
        return None
    
    dest_path = sm.GetService('starmap').GetDestinationPath()
    
    # Если маршрут не задан
    if not dest_path[0]:
        return None
    
    # while True:
    #     pause(1000)
    
    next_point = sm.GetService('autoPilot').GetGateOrStation(bp, dest_path[0])[0]
    
    if next_point:
        return next_point
    
    return None


# Варпаем к объекту
def warp_to(_id, _name='', dist=0):
    name = _name
    
    if _name == '':
        bp = sm.GetService('michelle').GetBallpark(True)
        
        if bp:
            slim_item = bp.GetInvItem(_id)
            
            if slim_item:
                name = slim_item.name
    
    _m = str(name) + ' (' + str(_id) + ')'
    bot.log.info('Варпаем к ' + _m, 'miner  ')
    
    do_action(3 + rnd_keys())
    
    movementFunctions.WarpToItem(_id, dist)
