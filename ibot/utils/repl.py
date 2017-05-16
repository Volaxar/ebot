import sys

import carbonui.const as uiconst
import const
import evetypes
import localization
import log
import util
from inventorycommon.util import GetItemVolume, IsShipFittingFlag


# Функции взяты из invControllers.py, что бы избавиться от окна с вводом количества переносимых итемов -----------------


def move_items(self, items, count=0):
    if not isinstance(items, list):
        items = [items]
    if len(items) > 1:
        items = filter(self.DoesAcceptItem, items)
    if not items:
        return
    else:
        sourceLocation = items[0].locationID
        if self.itemID != sourceLocation and not sm.GetService('crimewatchSvc').CheckCanTakeItems(sourceLocation):
            sm.GetService('crimewatchSvc').SafetyActivated(const.shipSafetyLevelPartial)
            return
        if session.shipid and self.itemID == session.shipid:
            if self.itemID != sourceLocation and not sm.GetService('consider').ConfirmTakeIllicitGoods(items):
                return
        if len(items) == 1:
            item = items[0]
            if hasattr(item, 'flagID') and IsShipFittingFlag(item.flagID):
                if item.locationID == util.GetActiveShip():
                    if not self.CheckAndConfirmOneWayMove():
                        return
                    itemKey = item.itemID
                    locationID = item.locationID
                    dogmaLocation = sm.GetService('clientDogmaIM').GetDogmaLocation()
                    containerArgs = self._GetContainerArgs()
                    if item.categoryID == const.categoryCharge:
                        return dogmaLocation.UnloadChargeToContainer(locationID, itemKey, containerArgs,
                                                                     self.locationFlag)
                    if item.categoryID == const.categoryModule:
                        return dogmaLocation.UnloadModuleToContainer(locationID, itemKey, containerArgs,
                                                                     self.locationFlag)
            ret = add_item(self, item, sourceLocation=sourceLocation, forceQuantity=int(count))
            if ret:
                sm.ScatterEvent('OnClientEvent_MoveFromCargoToHangar', sourceLocation, self.itemID, self.locationFlag)
            return ret
        elif not self.CheckAndConfirmOneWayMove():
            return
        items.sort(key=lambda item: evetypes.GetVolume(item.typeID) * item.stacksize)
        itemIDs = [node.itemID for node in items]
        dogmaLocation = sm.GetService('clientDogmaIM').GetDogmaLocation()
        masters = dogmaLocation.GetAllSlaveModulesByMasterModule(sourceLocation)
        if masters:
            inBank = 0
            for itemID in itemIDs:
                if dogmaLocation.IsInWeaponBank(sourceLocation, itemID):
                    inBank = 1
                    break
            
            if inBank:
                ret = eve.Message('CustomQuestion', {'header': localization.GetByLabel('UI/Common/Confirm'),
                                                     'question': localization.GetByLabel(
                                                         'UI/Inventory/WeaponLinkUnfitMany')}, uiconst.YESNO)
                
                bot.log.warn('Какая-то проблема с переносом из конта в конт')
                
                if ret != uiconst.ID_YES:
                    return
        for item in items:
            if item.categoryID == const.categoryCharge and IsShipFittingFlag(item.flagID):
                log.LogInfo('A module with a db item charge dropped from ship fitting into some container. '
                            'Cannot use multimove, must remove charge first.')
                ret = [add_item(self, item, forceQuantity=int(count))]
                items.remove(item)
                for _item in items:
                    ret.append(add_item(self, _item, forceQuantity=int(count)))
                
                return ret
        
        invCacheCont = self._GetInvCacheContainer()
        if self.locationFlag:
            ret = invCacheCont.MultiAdd(itemIDs, sourceLocation, flag=self.locationFlag)
        else:
            ret = invCacheCont.MultiAdd(itemIDs, sourceLocation, flag=const.flagNone)
        
        if ret:
            sm.ScatterEvent('OnClientEvent_MoveFromCargoToHangar', sourceLocation, self.itemID, self.locationFlag)
        return ret


def add_item(self, item, forceQuantity=0, sourceLocation=None):
    locationID = session.locationid
    for i in xrange(2):
        try:
            if locationID != session.locationid:
                return
            itemQuantity = item.stacksize
            if itemQuantity == 1:
                quantity = 1
            elif forceQuantity > 0:
                quantity = forceQuantity
            else:
                quantity = itemQuantity
            if not item.itemID or not quantity:
                return
            if locationID != session.locationid:
                return
            if sourceLocation is None:
                sourceLocation = item.locationID
            return _add_item(self, item.itemID, sourceLocation, quantity)
        except UserError as what:
            if what.args[0] in ('NotEnoughCargoSpace', 'NotEnoughCargoSpaceOverload', 'NotEnoughDroneBaySpace',
                                'NotEnoughDroneBaySpaceOverload', 'NoSpaceForThat', 'NoSpaceForThatOverload',
                                'NotEnoughChargeSpace', 'NotEnoughSpecialBaySpace', 'NotEnoughSpecialBaySpaceOverload',
                                'NotEnoughSpace'):
                try:
                    cap = self.GetCapacity()
                except UserError:
                    raise what
                
                free = cap.capacity - cap.used
                if free < 0:
                    raise
                if item.typeID == const.typePlasticWrap:
                    volume = sm.GetService('invCache').GetInventoryFromId(item.itemID).GetCapacity().used
                else:
                    volume = GetItemVolume(item, 1)
                maxQty = min(item.stacksize, int(free / (volume or 1)))
                if maxQty <= 0:
                    if volume < 0.1:
                        req = 0.01
                    else:
                        req = volume
                    eve.Message('NotEnoughCargoSpaceFor1Unit', {'type': item.typeID,
                                                                'free': free,
                                                                'required': req})
                    
                    bot.log.warn('Недостаточно места в контейнере')
                    
                    return
                if self._DBLessLimitationsCheck(what.args[0], item):
                    return
                forceQuantity = 1
            else:
                raise
            sys.exc_clear()


def _add_item(self, itemID, sourceLocation, quantity, dividing=False):
    try:
        dropLocation = self._GetInvCacheContainer().GetItem().itemID
        dogmaLocation = sm.GetService('clientDogmaIM').GetDogmaLocation()
        stateMgr = sm.StartService('godma').GetStateManager()
        item = dogmaLocation.dogmaItems.get(itemID)
        if dropLocation == sourceLocation and not dividing:
            if getattr(item, 'flagID', None):
                if item.flagID == self.locationFlag:
                    return
        if not dividing and not self.CheckAndConfirmOneWayMove():
            return
        if self.locationFlag:
            item = stateMgr.GetItem(itemID)
            if item and self.locationFlag == const.flagCargo and IsShipFittingFlag(item.flagID):
                containerArgs = self._GetContainerArgs()
                if item.categoryID == const.categoryCharge:
                    return dogmaLocation.UnloadChargeToContainer(item.locationID, item.itemID, containerArgs,
                                                                 self.locationFlag, quantity)
                if item.categoryID == const.categoryModule:
                    return stateMgr.UnloadModuleToContainer(item.locationID, item.itemID, containerArgs,
                                                            self.locationFlag)
            else:
                return self._GetInvCacheContainer().Add(itemID, sourceLocation, qty=quantity, flag=self.locationFlag)
        else:
            lockFlag = None
            typeID = self.GetTypeID()
            if typeID and evetypes.GetGroupID(typeID) == const.groupAuditLogSecureContainer:
                thisContainer = sm.GetService('invCache').GetInventoryFromId(self.itemID)
                thisContainerItem = thisContainer.GetItem()
                rolesAreNeeded = thisContainerItem is None or not util.IsStation(thisContainerItem.locationID) and \
                                                              thisContainerItem.locationID != session.shipid
                if rolesAreNeeded:
                    config = thisContainer.ALSCConfigGet()
                    lockFlag = const.flagLocked if bool(config & const.ALSCLockAddedItems) else const.flagUnlocked
                    if lockFlag == const.flagLocked and charsession.corprole & const.corpRoleEquipmentConfig == 0:
                        bot.log.warn('Какая-то проблема с переносом из конта в конт, требуется подтверждение')
                        
                        if eve.Message('ConfirmAddLockedItemToAuditContainer', {}, uiconst.OKCANCEL) != uiconst.ID_OK:
                            return
            return self._GetInvCacheContainer().Add(itemID, sourceLocation, qty=quantity, flag=self.locationFlag)
    except:
        return
