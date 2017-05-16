from ibot.mac.template.macros import *


class Space(Macros):
    __notifyevents__ = [
        'OnViewStateChanged'
    ]
    
    # Инициализация класса
    def __init__(self, _role=None):
        actions = {
        }
        
        self.actions = dict(actions, **self.actions)  # Настройки действий
        
        Macros.add_notify(Space)
        
        Macros.__init__(self, _role)
        
        self.act_delay = {}
    
    # region Методы в космосе
    
    # Отстыковка от станции или цитадели
    def undocking(self):
        itemID = session.stationid or session.structureid
        
        if not itemID:
            return
        
        structName = cfg.evelocations.Get(itemID).name
        
        self.info('Андок от {}'.format(ed(structName)), self.role)
        
        do_action(1 + rnd_keys())
        
        uicore.cmd.CmdExitStation()
    
    # endregion
    
    # region Проверки
    
    # Проверяем находимся ли на станции или цитадели
    def check_in_station(self):
        return bool(session.stationid or session.structureid)
    
    # Проверяем находимся ли в космосе
    def check_in_inflight(self):
        return bool(session.solarsystemid and not session.structureid)
    
    # endregion
    
    # region Служебные
    
    # Получить главного бота в группе
    def get_primary(self, roles=None, group=None, place=None):
        if not roles:
            roles = [self.role]
        
        if not isinstance(roles, list):
            roles = [roles]
        
        min_id = session.charid
        
        corp_list = [x for x in sm.GetService('LSC').GetMembers((('corpid', eve.session.corpid),))]
        
        for v in bot.bots.values():
            if v['id'] in corp_list:
                if v['role'] not in roles:
                    continue
                
                if group and group != v['group']:
                    continue
                
                if place and place != v['place']:
                    continue
                
                if min_id > v['id']:
                    min_id = v['id']
        
        if min_id == session.charid:
            return None
        else:
            for k, v in bot.bots.items():
                if v['id'] == min_id:
                    return bot.bots[k]
    
    # Является ли текущий бот главным
    def i_am_is_primary(self, roles=None, group=None, place=None):
        primary = self.get_primary(roles, group, place)
        
        if primary:
            return primary['id'] == session.charid
        else:
            return True
    
    # Отправляем уведомления ботам о выполненом действии
    def send_action_info(self, act, grid='default', gr=None):
        rec = {'type': 'do_action', 'action': act, 'grid': grid, 'gr': gr}
        send_to('ruller', '?{}'.format(pickle.dumps(rec)))
    
    # Отмена выполнения действия
    def unlock_action(self, act, grid='default', gr=None):
        rec = {'type': 'unlock_action', 'action': act, 'grid': grid, 'gr': gr}
        send_to('ruller', '?{}'.format(pickle.dumps(rec)))
    
    def act_is_ready(self, act, grid='default', add_time=0, gr=None, lock=False):
        if grid not in self.act_delay:
            self.act_delay[grid] = {}
        
        if act in self.act_delay[grid]:
            if self.act_delay[grid][act] - datetime.datetime.now() > datetime.timedelta(seconds=0):
                return False
            else:
                del self.act_delay[grid][act]
        
        rec = {'type': 'act_status', 'action': act, 'grid': grid, 'add_time': add_time, 'gr': gr, 'lock': lock}
        ans = j_get_far('ruller', rec)
        
        if ans != 'error':
            if ans == 'ready':
                return True
            else:
                self.act_delay[grid][act] = ans
        
        return False
    
    # endregion
    
    # region События
    
    # Смена сессии
    def OnViewStateChanged(self, old_state, new_state):
        if not self.is_ready: return
        
        true_state = ['inflight', 'hangar']
        
        if old_state in true_state and new_state in true_state:
            self.info('Смена сессии: {} > {}'.format(old_state, new_state), self.role)
            
            self.run_action()
            
            # endregion
