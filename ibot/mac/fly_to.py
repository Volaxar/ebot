import stackless

from ibot.mac.template.oldspace import Space


# endpoint - точка назначения система или станция
def run(endpoint=None):
    if not bot.macros:
        bot.macros = FlyTo(endpoint)


class FlyTo(Space):
    __notifyevents__ = [
    ]
    
    # Инициализация класса
    def __init__(self, endpoint=None):
        
        self.actions = {
        }
        
        Space.__init__(self, 'fly_to')
        
        self.useCloak = True
        self.useCloakOnlyNeut = False
        
        self.useMWD = True
        self.useProtect = True
        
        self.info('Макрос запущен', self.role)
        
        if endpoint:
            sm.GetService('starmap').SetWaypoint(endpoint, True)
        
        self.add_flag('fly')
        
        self.is_ready = True
        
        self.run_action()
    
    def fly_to(self):
        if self.in_fly or self.do_fly: return
        
        Space.fly_to(self)
        
        if not bool(sm.GetService('starmap').destinationPath[0]):
            self.warn('Конечная точка маршрута достигнута', self.role)
            
            self.del_flag('fly')
            
            stackless.tasklet(self.OnScriptBreak)()
