# Скрипт перемещения пилота в указаную точку (система, станция)

import blue
import uthread
from eve.client.script.ui.services.menuSvcExtras.movementFunctions import DockOrJumpOrActivateGate

from ibot.mac import Macros
from ibot.utils import *


# endpoint - точка назначения система или станция
def run(endpoint=None):
    if not hasattr(bot, 'fly_to'):
        bot.fly_to = FlyTo(endpoint)


# TODO: Если endpoint = None, лететь по существующему маршруту, если задан
class FlyTo(Macros):
    __notifyevents__ = [
        'OnViewStateChanged',
        'OnWarpFinished',
        'OnScriptPause'
    ]
    
    def __init__(self, endpoint):
        Macros.__init__(self)
        
        self._ep = endpoint
        self.in_fly = False
        
        if not self._ep:
            self.__deinit__()
            return
        
        sm.GetService('starmap').ClearWaypoints()
        sm.GetService('starmap').SetWaypoint(self._ep, True)
        
        uthread.new(self.__action)
    
    def __deinit__(self):
        Macros.__deinit__(self)
        
        sm.ScatterEvent('OnFlyToFinished')
        
        del bot.fly_to
    
    def __action(self):
        es = eve.session
        
        if es.solarsystemid2 == self._ep or es.stationid2 == self._ep:
            self.__deinit__()
            
            return
        
        if sm.GetService('autoPilot').InWarp():
            return
        elif es.stationid2:
            uicore.cmd.CmdExitStation()
        elif es.solarsystemid2:
            next_point = bot.fly.get_next_point()
            
            if next_point:
                self.in_fly = True
                pause(1000)
                
                DockOrJumpOrActivateGate(next_point)
    
    def __view_state_change(self, old_state, new_state):
        if new_state == 'inflight':
            # Ожидаем загрузки космоса
            sm.StartService('michelle').GetBallpark(True)
            
            self.in_fly = False
            uthread.new(self.__action)
        
        elif old_state == 'inflight' and new_state == 'hangar':
            while not eve.session.stationid2:
                blue.pyos.synchro.Yield()
            
            self.in_fly = False
            uthread.new(self.__action)
    
    def OnViewStateChanged(self, old_state, new_state):
        uthread.new(self.__view_state_change, old_state, new_state)
    
    def OnWarpFinished(self, *args):
        if not self.in_fly:
            uthread.new(self.__action)
    
    def OnScriptPause(self, _pause):
        Macros.OnScriptPause(self, _pause)
        
        if not self.is_pause:
            uthread.new(self.__action)
