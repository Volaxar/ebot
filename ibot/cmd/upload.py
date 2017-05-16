import localization
import uthread


def run():
    uthread.new(unload)


def unload():
    print "Start"
    
    mg_data = []
    
    def save_solarsystems():
        ss_data = []
        
        for ssID, ss in cfg.mapSystemCache.iteritems():
            region_id = ss.regionID
            nm = localization.GetByMessageID(ss.nameID)
            security = ss.securityStatus
            security_class = ss.securityClass
            constellation_id = ss.constellationID
            
            ss_data.append((region_id, nm, security, security_class, constellation_id, ssID))
        
        query_str = "INSERT INTO map_solarsystems " \
                    "(region_id, nm, security, securityclass, " \
                    "constellation_id, solar_system_id)" \
                    "VALUES(%s, %s, %s, %s, %s, %s)"
        
        sm.bot.db.query(query_str, ss_data)
    
    def save_groups(parent_id=None):
        
        grouplist = sm.GetService('marketutils').GetMarketGroups()[parent_id]
        
        for mg in grouplist:
            mg_id = mg.marketGroupID
            mg_parent = mg.parentGroupID
            mg_nm = localization.GetByMessageID(mg.marketGroupNameID)
            mg_desc = localization.GetByMessageID(mg.descriptionID)
            mg_icon = mg.iconID
            mg_hastypes = mg.hasTypes
            
            if mg_id in [1922]:
                continue
            
            mg_count_types = len(mg.types)
            
            if mg_hastypes:
                if mg_count_types > 0:
                    save_types(mg_id)
                else:
                    continue
            else:
                save_groups(mg_id)
            
            mg_data.append((mg_id, mg_parent, mg_nm, mg_icon, mg_count_types, mg_desc, mg_hastypes))
    
    def save_types(group_id):
        ty_data = []
        
        for item in cfg.typesByMarketGroups.get(group_id, []):
            t_id = item['typeID']
            t_name = localization.GetByMessageID(item['typeNameID'])
            t_desc = None if item['descriptionID'] is None else localization.GetByMessageID(item['descriptionID'])
            t_vol = item['volume']
            t_cap = item['capacity']
            t_psize = item['portionSize']
            t_pub = item['published']
            t_mgid = item['marketGroupID']
            t_iconid = item['iconID']
            
            ty_data.append((t_id, t_name, t_desc, t_vol, t_cap, t_psize, t_pub, t_mgid, t_iconid))
        
        query_str = "INSERT INTO inv_types (type_id, nm, description, volume, capacity, portion_size, " \
                    "published, marketgroup_id, icon_id) " \
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        
        sm.bot.db.query(query_str, ty_data)
    
    sm.bot.db.query("DELETE FROM map_solarsystems")
    sm.bot.db.query("DELETE FROM inv_marketgroups")
    sm.bot.db.query("DELETE FROM inv_types")
    
    save_solarsystems()
    
    save_groups()
    
    query = "INSERT INTO inv_marketgroups (mg_id, parent_id, nm, icon_id, count_types, description, has_types) " \
            "VALUES(%s,%s,%s,%s,%s,%s,%s)"
    
    sm.bot.db.query(query, mg_data)
    
    print "Finish"
