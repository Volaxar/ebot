from ibot.utils.js import *


class Setting(object):
    def __init__(self, _mod='bot'):
        self.module = _mod
        
        self.pquery = 'SELECT sk.key_name, sv.val FROM set_keys sk, set_values sv '
        self.pquery += 'WHERE sv.key_id = sk.id AND '
        self.pquery += 'sv.char_id = (SELECT id FROM eve_bot eb WHERE eb.charid = %s) AND '
        self.pquery += 'sv.module_id = (SELECT id FROM set_modules sm WHERE sm.module_name = %s) '
        
        self.gquery = 'SELECT sk.key_name, sv.val FROM set_keys sk, set_gvalues sv '
        self.gquery += 'WHERE sv.key_id = sk.id AND '
        self.gquery += 'sv.group_id = (SELECT groupid FROM eve_bot eb WHERE eb.charid = %s) AND '
        self.gquery += 'sv.module_id = (SELECT id FROM set_modules sm WHERE sm.module_name = %s) '
    
    # Загрузка всех параметров из БД
    def updateall(self):
        
        res = {0: False, 1: False}
        qry = {0: self.gquery, 1: self.pquery}
        
        for k, v in qry.items():
            rets = db_select(v, (session.charid, self.module))
            
            if rets and rets != 'error':
                for ret in rets:
                    key, value = ret
                    
                    self.__dict__[key] = value
                
                res[k] = True
        
        return res[0] or res[1]
    
    # Получить аттрибут из кэша
    def ga(self, attr, default=None):
        return getattr(self, attr, default)
    
    # Получить аттрибут из БД
    def gan(self, attr, default=None):
        pquery = self.pquery
        pquery += 'AND sk.key_name = %s'
        
        gquery = self.gquery
        gquery += 'AND sk.key_name = %s'
        
        rets = db_select(pquery, (session.charid, self.module, attr))
        
        if not rets or rets == 'error':
            rets = db_select(gquery, (session.charid, self.module, attr))
        
        if rets and rets != 'error':
            return rets[0][1]
        else:
            return default
