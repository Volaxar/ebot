from ibot.mac.template.oldspace import Space


def run():
    if not bot.macros:
        bot.macros = AgentRun()


class AgentRun(Space):
    __notifyevents__ = [
    ]
    
    # Инициализация класса
    def __init__(self, _run=True):
        self.actions = {
        
        }
        
        Space.__init__(self, 'agentrun')
        
        self.agentFraction = None
        self.agentCorp = None
        self.agentType = None
        self.agentFinder = None
        self.agentRegion = None
        self.agentSystem = None
        self.agentCc = None
        self.agentAvailable = None
    
    def get_agent(self):
        agentSvc = sm.GetService('agents')
        
        return agentSvc.GetAgentByID(3016129)
