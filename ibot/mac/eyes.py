from ibot.mac.template.oldspace import Space
from ibot.utils import pickle
from ibot.utils.js import *


def run():
    if not bot.macros:
        bot.macros = Eyes()


class Eyes(Space):
    __notifyevents__ = [
    ]
    
    # Инициализация класса
    def __init__(self, _run=True):
        
        self.actions = {
        }
        
        Space.__init__(self, 'eyes')
        
        self.in_do_flag = False
        
        self.is_ready = True
        
        self.info('Макрос запущен', self.role)
        
        if self.get_min_safety_level() <= 0:
            self.add_flag('enemy_in_local')
    
    def OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args):
        if not self.is_ready: return
        
        # Space.OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args)
        
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
