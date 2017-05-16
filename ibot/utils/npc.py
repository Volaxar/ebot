from ibot.utils import *


class Npc():
    def __init__(self, ball_id):
        
        self.is_filled = False
        
        self.itemID = ball_id
        self.typeID = None
        self.name = None
        
        # Хит поинты
        self.hullHP = None  # Структура
        self.armorHP = None  # Броня
        self.shieldHP = None  # Щит
        
        # Резисты брони
        self.armorEM = None
        self.armorEX = None
        self.armorKN = None
        self.armorTH = None
        
        # Резисты щита
        self.shieldEM = None
        self.shieldEX = None
        self.shieldKN = None
        self.shieldTH = None
        
        # Повреждения
        self.damageEM = None
        self.damageEX = None
        self.damageKN = None
        self.damageTH = None
        
        self.damageMULT = None
        
        self.maxRange = None
        self.falloff = None
        self.trackingSpeed = None
        self.rate = None
        
        self.load_attr()
    
    def load_attr(self):
        bp = sm.GetService('michelle').GetBallpark()
        
        if not bp:
            return
        
        slim = bp.GetInvItem(self.itemID)
        
        if slim:
            self.typeID = slim.typeID
            
            self.hullHP = get_type_attr(self.typeID, const.attributeHp)
            self.armorHP = get_type_attr(self.typeID, const.attributeArmorHP)
            self.shieldHP = get_type_attr(self.typeID, const.attributeShieldCapacity)
            
            self.is_filled = True
