import ibot.utils.bms as _bm
from ibot.mac.template.oldspace import Space
from ibot.utils import *
from ibot.utils import pickle
from ibot.utils.js import *


def run():
    if not bot.macros:
        bot.macros = Bonus()


class Bonus(Space):
    __notifyevents__ = [
        'OnWarpStarted',
        'DoBallsAdded',
        'DoBallRemove',
        'DoBallsRemove'
    ]
    
    # Инициализация класса
    def __init__(self):
        
        self.actions = {
            'distrib': {
                'co': [
                    lambda: self.check_empty_flags()
                ],
                'po': lambda: self.get_place_by_bm(_bm.get_bookmark('InPOS')),
                'go': self.go,
                'do': self.distrib,
                'tm': None,
                'iv': 500,
            }
        }
        
        self.in_do_flag = False
        
        self.ignoreRejumps = True
        self.enemyOutTime = dt.now() - datetime.timedelta(minutes=1)
        
        self.inPos = self.get_place_by_bm(_bm.get_bookmark('InPOS'))
        self.outPos = self.get_place_by_bm(_bm.get_bookmark('OutPOS'))
        
        self.point = None  # Где находимся
        self.dest = None  # Куда двигаться
        
        # Количество нейтралов в гриде
        self.enemy_in_grid = 0
        
        Space.__init__(self, 'bonus')
        
        self.actions['wait']['co'].append(lambda: False)
        self.actions['hide']['co'].append(lambda: False)
        
        if self.grid_is_safety():
            self.dest = self.outPos.id
        else:
            self.dest = self.inPos.id
        
        self.is_ready = True
        
        self.info('Макрос запущен', self.role)
        
        # if self.get_min_safety_level() <= 0:
        #     self.add_flag('enemy_in_local')
        
        self.run_action()
    
    def distrib(self):
        if self.in_do_flag:
            return
        
        self.in_do_flag = True
        
        if self.dest != self.point:
            
            # В гриде чисто
            if not self.enemy_in_grid:
                if dt.now() - self.enemyOutTime > datetime.timedelta(minutes=1):
                    self.point = self.outPos.id
                    self.approach(self.outPos)
            
            else:
                self.modules_off(self.get_modules(const.groupGangCoordinator))
                
                self.point = self.inPos.id
                self.approach(self.inPos)
        
        self.in_do_flag = False
    
    def approach(self, bm):
        if bm.surfaceDist() > 1000 and bm.id == self.dest:
            self.info('Приближаемся к {} дистанция {}'.format(bm.name, bm.surfaceDist()))
            
            bp = sm.GetService('michelle').GetRemotePark()
            if bp:
                do_action(2 + rnd_keys())
                
                bp.CmdGotoBookmark(bm.id)
                
                pause(500)
                
                while bm.surfaceDist() > 1000 and not self.check_in_flags('break') and bm.id == self.dest:
                    pause(100)
                
                uicore.cmd.CmdStopShip()
        
        if bm.surfaceDist() <= 1000 and not self.check_in_flags('break'):
            self.info('Останавились возле {} дистанция {}'.format(bm.name, bm.surfaceDist()))
            
            if self.dest == self.inPos.id:
                align = self.outPos.id
            else:
                align = self.inPos.id
                
                self.modules_on(self.get_modules(const.groupGangCoordinator))
            
            pause(1000)
            
            sm.GetService('menu').AlignToBookmark(align)
            
            pause(3000)
            
            uicore.cmd.CmdStopShip()
    
    def change_space(self, slims, value):
        old_value = self.enemy_in_grid
        
        for slim in slims:
            if slim and slim.categoryID == 6 and slim.itemID != session.shipid:
                level = self.get_char_safety_level(slim.allianceID, slim.corpID, slim.charID)
                
                if level <= 0:
                    self.enemy_in_grid += value
        
        # Враги ушли из грида
        if not self.enemy_in_grid and old_value:
            self.info('Враги ушли из грида, вылезаем из под поса')
            
            self.enemyOutTime = dt.now()
            self.dest = self.outPos.id
        
        # Враги пришли в грид
        elif self.enemy_in_grid and not old_value:
            self.info('Враги в гриде, валим под пос')
            
            self.dest = self.inPos.id
    
    def DoBallsAdded(self, balls_slimItems, *args, **kw):
        if not self.is_ready: return
        
        stackless.tasklet(self.change_space)([x[1] for x in balls_slimItems], 1)
    
    def DoBallRemove(self, ball, slimItem, terminal):
        if not self.is_ready: return
        
        stackless.tasklet(self.change_space)([slimItem], -1)
    
    def DoBallsRemove(self, pythonBalls, isRelease):
        if not self.is_ready: return
        
        stackless.tasklet(self.change_space)([x[1] for x in pythonBalls], -1)
    
    def OnWarpStarted(self):
        self.enemy_in_grid = 0
    
    def OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args):
        if not self.is_ready: return
        
        Space.OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args)
        
        if isinstance(channelID, tuple) and channelID[0][0] == 'solarsystemid2':
            
            if method == 'JoinChannel':
                safetyLevel = self.get_min_safety_level()
                
                if safetyLevel <= 0 and 'enemy_in_local' not in self.flags:
                    self.add_flag('enemy_in_local')
                    
                    self.warn('Враги в локале, отправляем уведомления валить на ПОС', self.role)
                    
                    rec = {'type': 'notification', 'func': 'gopos'}
                    send_to_role('?{}'.format(pickle.dumps(rec)), ['miner', 'crub'])
            
            elif method == 'LeaveChannel':
                safetyLevel = self.get_min_safety_level()
                
                if safetyLevel > 0 and 'enemy_in_local' in self.flags:
                    self.flags.remove('enemy_in_local')
                    
                    self.warn('В локале безопасно', self.role)
