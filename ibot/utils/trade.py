class Trade():
    def __init__(self):
        self.__only_allow_g = True
        self.__only_allow_t = False
        
        self.__groupList = None
        self.__typeIDs = None
        
        self.min_ask_price = None  # Минимальная цена продажи
        self.min_ask_volume = None  # Минимум продаж
        self.max_item_volume = None  # Максимальный объем товара
        
        self.glist = None
        self.tlist = None  # Список разрешенных товаров для выгрузки
    
    def get_type_ids(self, allow_g=True, allow_t=False):
        self.__only_allow_g = allow_g
        self.__only_allow_t = allow_t
        
        # Параметры выгрузки
        self.min_ask_price = bot.db.select("SELECT data FROM eve_set es WHERE es.key = 'min_ask_price'")[0][0]
        self.min_ask_volume = bot.db.select("SELECT data FROM eve_set es WHERE es.key = 'min_ask_volume'")[0][0]
        self.max_item_volume = bot.db.select("SELECT data FROM eve_set es WHERE es.key = 'max_item_volume'")[0][0]
        
        params = [self.max_item_volume, self.min_ask_volume, self.min_ask_price]
        
        query = "select iys.marketgroup_id from history_avg hag inner join inv_types iys " \
                "ON hag.type_id = iys.type_id and iys.volume <= %s where hag.volume > %s and " \
                "hag.price > %s group by iys.marketgroup_id"
        
        self.glist = bot.db.select(query, params)
        
        self.glist = [x[0] for x in self.glist]
        
        query = "select iys.type_id from history_avg hag inner join inv_types iys " \
                "ON hag.type_id = iys.type_id and iys.volume <= %s where hag.volume > %s and " \
                "hag.price > %s group by iys.type_id"
        
        self.tlist = bot.db.select(query, params)
        
        self.tlist = [x[0] for x in self.tlist]
        
        # Полный список групп товаров на рынке
        self.__groupList = sm.GetService('marketutils').GetMarketGroups()
        
        # Список ID товаров
        self.__typeIDs = []
        self.__update_types_list()
        
        return self.__typeIDs
    
    # Обновляем список товаров
    def __update_types_list(self, market_group_id=None):
        try:
            for mgi in self.__groupList[market_group_id]:
                
                if (mgi.marketGroupID in self.get_deny_groups() and self.__only_allow_g) or \
                        not len(mgi.types):
                    continue
                
                if mgi.hasTypes:
                    if not mgi.marketGroupID in self.glist:
                        continue
                    
                    if self.__only_allow_t:
                        for _type in mgi.types:
                            if not _type in self.get_deny_types() and _type in self.tlist:
                                self.__typeIDs += [_type]
                    else:
                        self.__typeIDs += mgi.types
                else:
                    self.__update_types_list(mgi.marketGroupID)
        except Exception as e:
            print 'except in unloader.__UpdateTypesList: ' + str(e)
    
    # Получаем минимальную цену в регионе из eve-central, регион по умолчанию The Forge
    def get_min_price(self, typeid):
        query = "SELECT price FROM history_avg WHERE type_id = %s"
        params = [typeid]
        
        result = bot.db.select(query, tuple(params))
        
        if len(result) == 0:
            return None
        else:
            return result[0][0]
    
    # Получаем объем проданных товаров из истории по товару
    def get_volume(self, typeid):
        query = "SELECT volume FROM history_avg WHERE type_id = %s"
        params = [typeid]
        
        result = bot.db.select(query, tuple(params))
        
        if len(result) == 0:
            return None
        else:
            return result[0][0] > 0
    
    @staticmethod
    def get_deny_groups():
        query = "SELECT marketgroup_id FROM trade_denygroups"
        return [x[0] for x in bot.db.select(query)]
    
    @staticmethod
    def get_deny_types():
        query = "SELECT type_id FROM trade_denytypes"
        return [x[0] for x in bot.db.select(query)]
