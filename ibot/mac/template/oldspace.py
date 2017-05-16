import math
import types

import evetypes
import invCtrl
import localization
import stackless
import util
from eve.client.script.ui.services.menuSvcExtras import movementFunctions

import ibot.utils.bms as _bm
from ibot.mac.template.macros import *
from ibot.utils import fly


class Oldspace(Macros):
    __notifyevents__ = [
        'OnViewStateChanged',
        'OnWarpFinished',
        'OnGoHome',
        'OnGoPos',
        'OnGoWork',
        'ProcessActiveShipChanged',
        'OnPlayerPodDeath',
        'OnJamStart',
        'OnJamEnd',
        'OnWindowOpened',
        'OnLSC',
        'OnSessionMutated',
        'DoDestinyUpdate',
        'OnWarpStarted',
        'OnWarpStarted2'
    ]
    
    # Инициализация класса
    def __init__(self, _role=None):
        actions = {
            'wait': {
                'co': [
                    lambda: self.check_in_flags(['wait']),
                    lambda: not self.check_scrambler()
                ],
                'po': self.get_home,
                'go': self.go,
                'do': self.wait
            },
            'hide': {
                'co': [
                    lambda: self.check_in_flags(['panic', 'enemy', 'topos']),
                    lambda: not bool(session.stationid),
                    lambda: not self.check_scrambler()
                ],
                'po': lambda: self.get_place_by_bm(_bm.get_bookmark('POS')),
                'go': self.go,
                'do': self.wait
            },
            'change_fit': {
                'co': [
                    lambda: self.check_in_flags(['change_fit'])
                ],
                'po': self.get_home,
                'go': self.go,
                'do': self.change_fit,
                'pr': 50
            },
            'repair': {
                'co': [
                    lambda: self.check_in_flags('damaged'),
                    lambda: not self.check_scrambler()
                ],
                'po': self.get_rapair_place,
                'go': self.go,
                'do': self.repair
            },
            'fly_to': {
                'co': [
                    lambda: self.check_in_flags('fly')
                ],
                'do': self.fly_to
            }
        }
        
        self.actions = dict(actions, **self.actions)  # Настройки действий
        
        Oldspace.add_notify(Space)
        
        Macros.__init__(self, _role)
        
        _bm.create_folder('Places')
        
        self.home_id = int(self.s.ga('HomeID', 0))
        self.ignoreRejumps = self.s.ga('IgnoreRejumps', False)
        self.warpDist = int(self.s.ga('WarpDist', 0))
        
        self.fit_name = None
        
        self.in_drone_ret = False
        self.act_delay = {}
        self.in_repair = False
        
        self.alignTo = None
        self.gate_cloak = False
        
        self.gate_opened = False
        
        self.useCloak = True
        self.useCloakOnlyNeut = True
        
        self.useMWD = False
        self.useProtect = False
        
        self.ewar = []
        
        self.endpoint = None
        self.in_fly = False
        self.do_fly = False
        self.warp_stage = 0
        
        # print 'space - 2'
    
    # region Проверки
    
    # Проверяем осталось ли до ДТ меньше 5 минут
    @cached
    def check_is_downtime(self):
        return is_downtime()
    
    # Проверяем есть ли нейтралы или враги в локале
    @cached
    def check_enemy_in_local(self):
        return self.get_min_safety_level() <= 0
    
    # Проверяем поступала ли команда ожидания
    def check_in_flags(self, what):
        if not isinstance(what, list):
            what = [what]
        
        for x in what:
            if x in self.flags:
                return True
        
        return False
    
    # Проверяем установлены ли флаги
    def check_empty_flags(self):
        return not self.flags
    
    # Проверяем находимся ли на станции
    def check_in_station(self):
        return bool(session.stationid or session.structureid)
    
    # Проверяем находимся ли в космосе
    def check_in_inflight(self):
        return bool(session.solarsystemid)
    
    @cached
    def check_in_buble(self):
        return bool(self.in_bubble())
    
    def check_scrambler(self):
        tactical = sm.GetService('tactical')
        
        w1 = 'warpScrambler' in tactical.jammersByJammingType \
             and bool(tactical.jammersByJammingType['warpScrambler'])
        
        w2 = 'warpScramblerMWD' in tactical.jammersByJammingType \
             and bool(tactical.jammersByJammingType['warpScramblerMWD'])
        
        return w1 or w2
    
    def check_fit(self):
        fitSvc = sm.GetService('fittingSvc')
        
        cur_fit = util.KeyVal()
        cur_fit.shipTypeID, cur_fit.fitData = fitSvc.GetFittingDictForActiveShip()
        
        fit = self.get_fit_by_name(self.fit_name)
        
        try:
            if not fit or not fitSvc.VerifyFitting(fit):
                self.warn('Fit not found - {}'.format(self.fit_name))
                return
        except Exception as e:
            self.warn('Fit {} error: {}'.format(self.fit_name, e), self.role)
            return
        
        new_fit = util.KeyVal()
        new_fit.shipTypeID, new_fit.fitData = fit.shipTypeID, fit.fitData
        
        if cfg.evelocations.Get(util.GetActiveShip()).name != fit.description:
            self.add_flag('change_fit')
            return
        
        if not self.equal_fit(new_fit, cur_fit):
            self.add_flag('change_fit')
            return
        
        self.del_flag('change_fit')
    
    # endregion
    
    # region Функции
    
    # Получить главного бота в группе
    def get_primary(self, roles=None, group=None, place=None):
        if not roles:
            roles = [self.role]
        
        if not isinstance(roles, list):
            roles = [roles]
        
        min_id = session.charid
        
        for v in bot.bots.values():
            if sm.GetService('onlineStatus').GetOnlineStatus(v['id'], True):
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
    
    def get_order(self):
        botIDs = []
        
        for v in bot.bots.values():
            if sm.GetService('onlineStatus').GetOnlineStatus(v['id'], True) and v['role'] == self.role:
                botIDs.append(v['id'])
        
        botIDs += [session.charid]
        
        botIDs.sort()
        
        return botIDs.index(session.charid)
    
    # Отношение альянса и корпы к чару
    def get_char_safety_level(self, alliID, corpID, charID):
        if session.corpid == corpID:
            return 20
        
        if alliID and session.allianceid == alliID:
            return 15
        
        standing = 0
        
        _f = [session.allianceid]  # , session.corpid, session.charid
        _t = [alliID, corpID, charID]
        
        for f in _f:
            if not f:
                continue
            
            for t in _t:
                if t:
                    s = sm.GetService('standing').GetStanding(f, t)
                    
                    if s < 0:
                        return s
                    
                    if s > standing:
                        standing = s
        
        return standing
    
    # Минимальный уровень отношений к чарам в системе, если 0 в системе нейтралы
    def get_min_safety_level(self):
        lsc = sm.GetService('LSC')
        mbrs = None
        
        for channel in lsc.channels:
            if isinstance(channel, tuple):
                if channel[0][0] == 'solarsystemid2':
                    mbrs = lsc.GetMembers(channel)
        
        if not mbrs:
            return 50
        
        min_level = 50
        
        ignoreList = self.s.gan('IgnoreNetrals', '').split(',')
        
        try:
            for charID in mbrs:
                if charID == session.charid:
                    continue
                
                charID = mbrs[charID].charID
                
                if mbrs[charID].corpID != session.corpid:
                    corpCharInfo = sm.GetService('corp').GetInfoWindowDataForChar(charID, 1)
                    
                    corpID = corpCharInfo.corpID
                    allianceID = corpCharInfo.allianceID
                    
                    if allianceID != session.allianceid:
                        if cfg.eveowners.Get(charID).name in ignoreList:
                            continue
                
                else:
                    
                    corpID = mbrs[charID].corpID
                    allianceID = mbrs[charID].allianceID
                
                level = self.get_char_safety_level(allianceID, corpID, charID)
                
                if min_level > level:
                    min_level = level
        
        except:
            pass
        
        return min_level
    
    # Получить домашнюю станцию
    def get_home(self):
        if hasattr(self, 'home_id') and self.home_id:
            
            place = Place.get_place_by_id(self.home_id)
            
            if place:
                return place
            
            sta = cfg.stations.Get(self.home_id)
            
            place = StationPlace(self.home_id, sta.stationName, (sta.x, sta.y, sta.z))
            
            Place.add_place(place)
            
            return place
        
        return None
    
    # Бука для варпа, в случае если основная точка перекрыта
    def get_warp_planet(self):
        
        bms = _bm.get_bookmarks('Rejumps')
        
        planets = []
        
        for bm in bms:
            place = BmPlace(bm.bookmarkID, bm.memo.strip(), (bm.x, bm.y, bm.z), bm)
            
            if not self.get_barrier(place) and place.surfaceDist() > const.minWarpDistance:
                planets.append((place.surfaceDist(), place))
        
        bp = sm.GetService('michelle').GetBallpark(True)
        
        if planets:
            planets.sort()
            
            return planets[0][1]
        else:
            self.info('Закладка для реварпа не найдена, прыгаем на звезду', self.role)
            
            for ball_id, ball in bp.balls.items():
                
                slim = bp.GetInvItem(ball_id)
                
                if slim and slim.groupID == const.groupSun:
                    return PlanetPlace(ball.id, slim.name, (ball.x, ball.y, ball.z))
    
    def get_align_place(self):
        
        place = None
        
        if self.check_in_flags(['panic', 'enemy']):
            place = self.get_place_by_bm(_bm.get_bookmark('POS'))
        
        elif self.check_in_flags('wait'):
            place = self.get_home()
        
        return self.get_safe_place(place)
    
    def get_safe_place(self, place, dist=15000):
        if place and place.surfaceDist() > const.minWarpDistance:
            barrier = self.get_barrier(place, dist)
            
            if barrier:
                planet = self.get_warp_planet()
                
                self.info('Варп к {} не возможен, новая точка варпа {}'.format(place.name, planet.name), self.role)
                
                if planet:
                    place = planet
        
        return place
    
    # Получить имя типа объекта в космосе
    def get_raw_name(self, _id):
        bp = sm.GetService('michelle').GetBallpark(True)
        
        if not bp:
            return None
        
        slim = bp.GetInvItem(_id)
        
        if slim:
            return evetypes.GetEnglishName(slim.typeID)
        
        return None
    
    # Перекрывает ли barrier point?
    def is_overlap(self, point, barrier, dist=15000):
        bp = sm.GetService('michelle').GetBallpark(True)
        ship = bp.GetBallById(util.GetActiveShip())
        
        if not point or not barrier:
            return False
        
        if point.id == barrier.id or point.surfaceDist() < barrier.surfaceDist or barrier.surfaceDist > dist:
            return False
        
        x1 = ship.x
        y1 = ship.y
        z1 = ship.z
        
        x2 = point.x
        y2 = point.y
        z2 = point.z
        
        x = barrier.x
        y = barrier.y
        z = barrier.z
        
        slim = bp.GetInvItem(barrier.id)
        
        if slim and slim.groupID == const.groupMobileWarpDisruptor:
            r = get_type_attr(slim.typeID, const.attributeWarpScrambleRange)
        else:
            r = barrier.radius + 200
        
        ax = x2 - x1
        ay = y2 - y1
        az = z2 - z1
        
        mx = x1 - x
        my = y1 - y
        mz = z1 - z
        
        sx = my * az - mz * ay
        sy = mx * az - mz * ax
        sz = mx * ay - my * ax
        
        d = math.sqrt(sx * sx + sy * sy + sz * sz) / math.sqrt(ax * ax + ay * ay + az * az)
        
        px = (x - x2) / (x1 - x2)
        py = (y - y2) / (y1 - y2)
        pz = (z - z2) / (z1 - z2)
        
        if d > r or \
                (px < 0 and py < 0) or \
                (px < 0 and pz < 0) or \
                (py < 0 and pz < 0) or \
                (px > 1 and py > 1) or \
                (px > 1 and pz > 1) or \
                (py > 1 and pz > 1):
            return False
        
        return True
    
    # Получить ближайшее препятствие закрывающее цель
    def get_barrier(self, point, dist=15000):
        bp = sm.GetService('michelle').GetBallpark(True)
        
        if not bp:
            return None
        
        barriers = []
        
        for ball_id, ball in bp.balls.items():
            
            slim = bp.GetInvItem(ball_id)
            
            # Объекты считающиеся препятствием: астероиды, структуры, корабли игроков
            # 3  - Station
            # 6  - Ship
            # 23 - Structure
            # 25 - Asteroid
            # 40 - Sovereignty Structure
            if slim and slim.categoryID not in [3, 6, 23, 25, 40]:
                continue
            
            if slim and ball_id != util.GetActiveShip() and self.is_overlap(point, ball, dist):
                barriers.append((ball.surfaceDist, ball))
        
        if barriers:
            barriers.sort()
            
            return barriers[0][1]
        
        return None
    
    # Получаем BmPlace из закладки
    def get_place_by_bm(self, bm):
        if not bm:
            return None
        
        return BmPlace(bm.bookmarkID, bm.memo.strip(), (bm.x, bm.y, bm.z), bm)
    
    # Максимальное число целей для лока (минимальное для корабля и чара)
    def get_max_target(self):
        godma = sm.GetService('godma')
        
        max_target = []
        for _id in [session.charid, session.shipid]:
            max_target.append(int(godma.GetItem(_id).maxLockedTargets))
        
        return min(max_target)
    
    # Список модулей указанной группы
    def get_modules(self, _groupID):
        result = []
        
        if not isinstance(_groupID, list):
            _groupID = [_groupID]
        
        for x in range(3):
            for y in range(8):
                if uicore.layer.shipui.isopen:
                    slot = uicore.layer.shipui.slotsContainer.slotsByOrder.get((x, y), None)
                    
                    if slot.sr.module:
                        groupID = slot.sr.module.moduleinfo.groupID
                        
                        if groupID in _groupID:
                            result.append(slot.sr.module)
        
        return result
    
    # Проверяем, достаточно ли капы для активации модуля
    def need_charge(self, itemID):
        godma = sm.GetService('godma')
        
        # Проверяем количество капы для включения модуля
        if godma.GetItem(session.shipid).charge < godma.GetItem(itemID).capacitorNeed * 1.1:
            return False
        
        return True
    
    # targetID для модуля
    def get_target_id(self, laser):
        if laser.def_effect.isActive and laser.def_effect.targetID:
            return laser.def_effect.targetID
        
        return None
    
    # Включение защитных модулей
    def protect_mod_on(self):
        for x in [
            const.groupDamageControl,
            const.groupShieldHardener,
            const.groupArmorHardener,
            const.groupSensorBooster,
        ]:
            self.modules_on(self.get_modules(x))
    
    # Выключение защитных модулей
    def protect_mod_off(self):
        for x in [const.groupShieldHardener, const.groupDamageControl]:
            self.modules_off(self.get_modules(x))
    
    # Включение ковро-клоки
    def covert_cloak_on(self):
        cloaks = self.get_modules(const.groupCloakingDevice)
        
        # Ковроклока
        if self.useCloak and cloaks and cloaks[0].moduleinfo.typeID == 11578:
            if self.useCloakOnlyNeut and self.check_enemy_in_local() or not self.useCloakOnlyNeut:
                stackless.tasklet(self.modules_on)(cloaks)
    
    # Проверка включен ли модуль
    def module_state(self, module):
        if module.InLimboState() or module.effect_activating:
            return None
        
        if module.def_effect.isActive:
            return 'on'
        else:
            return 'off'
    
    # Включение модулей
    def modules_on(self, modules):
        if not isinstance(modules, list):
            modules = [modules]
        
        for module in modules:
            state = self.module_state(module)
            
            if not state or state == 'on' or not module.online:
                continue
            
            info = module.moduleinfo
            itemName = evetypes.GetEnglishName(info.typeID)
            
            if not self.need_charge(info.itemID):
                self.info('Недостаточно энергии для включения {} ({})'.format(itemName, info.itemID), self.role)
                return
            
            self.info('Включаем {} ({})'.format(itemName, info.itemID), self.role)
            try:
                pause(100)
                
                do_action(1 + rnd_keys())
                
                stackless.tasklet(module.Click)()
            
            except:
                print 'Error module on {}'.format(itemName)
    
    # Выключение модулей
    def modules_off(self, modules):
        if not isinstance(modules, list):
            modules = [modules]
        
        for module in modules:
            while not self.module_state(module):
                pause(100)
            
            if self.module_state(module) == 'off' or not module.online:
                return
            
            info = module.moduleinfo
            itemName = evetypes.GetEnglishName(info.typeID)
            
            self.info('Отключаем {} ({})'.format(itemName, info.itemID), self.role)
            try:
                pause(100)
                
                do_action(1 + rnd_keys())
                
                # uthread.new(module.Click)
                stackless.tasklet(module.Click)()
            except:
                pass
            
            pause(100)
    
    # Список пиратских групп
    def get_npc_pirates(self):
        npc = localization.GetByLabel('UI/Services/State/NonPlayerCharacter/Generic')
        pirate = localization.GetByLabel('UI/Services/State/NonPlayerCharacter/Pirate')
        mission = localization.GetByLabel('UI/Services/State/NonPlayerCharacter/Mission')
        
        return util.GetNPCGroups()[npc][pirate]
    
    # Если есть непись в гриде возвращаем True
    def npc_in_space(self):
        bp = sm.GetService('michelle').GetBallpark()
        
        if not bp:
            return False
        
        pirates = self.get_npc_pirates()
        
        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.categoryID == const.categoryEntity and slim.groupID in pirates:
                return True
        
        return False
    
    # Список неписи в гриде
    def get_npc(self):
        bp = sm.GetService('michelle').GetBallpark()
        
        result = []
        
        if not bp:
            return result
        
        pirates = self.get_npc_pirates()
        
        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.categoryID == const.categoryEntity and slim.groupID in pirates:
                result.append(ball)
        
        return result
    
    # Безопасно ли в гриде, если есть нейтралы, то нет
    def grid_is_safety(self):
        bp = sm.GetService('michelle').GetBallpark(True)
        
        if not bp:
            return True
        
        for ball_id, ball in bp.balls.items():
            
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.categoryID == 6 and slim.itemID != session.shipid:
                level = self.get_char_safety_level(slim.allianceID, slim.corpID, slim.charID)
                
                if level <= 0:
                    return False
        
        return True
    
    # Статус безопасности текущей системы
    def get_cc(self):
        return sm.GetService('map').GetSecurityStatus(session.solarsystemid2)
    
    # Проверка хай-сек?
    def is_highsec(self):
        return self.get_cc() >= 0.5
    
    def is_nullsec(self):
        return self.get_cc() < 0.1
    
    # Грид забублен?
    def place_is_bubbled(self):
        if not session.solarsystemid:
            return False
        
        bp = sm.GetService('michelle').GetBallpark(True)
        
        if not bp:
            return None
        
        for ball_id, ball in bp.balls.iteritems():
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.groupID == const.groupMobileWarpDisruptor:
                return True
        
        return False
    
    # Проверяем не в бубле ли корабль, если да возвращаем бубль
    def in_bubble(self):
        if not session.solarsystemid:
            return None
        
        bp = sm.GetService('michelle').GetBallpark(True)
        
        if not bp:
            return None
        
        bubbles = []
        
        for ball_id, ball in bp.balls.iteritems():
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.groupID == const.groupMobileWarpDisruptor:
                radius = get_type_attr(slim.typeID, const.attributeWarpScrambleRange)
                
                if ball.surfaceDist < radius:
                    bubbles.append((radius - ball.surfaceDist, ball))
        
        if bubbles:
            bubbles.sort()
            
            return bubbles[0]
        
        return None
    
    # Получить сожержимое трюма, определенной категории или типа
    def get_cargo_items(self, cargo, category=[], _types=[]):
        if not isinstance(category, list):
            category = [category]
        
        if not isinstance(_types, list):
            _types = [_types]
        
        all_items = []
        
        try:
            all_items = cargo.GetItems()
        except:
            pass
        
        items = []
        
        for item in all_items:
            
            if not category and not _types:
                items.append(item)
                
                continue
            
            if category:
                if item.categoryID in category:
                    items.append(item)
                    
                    continue
            
            if _types:
                if item.typeID in _types:
                    items.append(item)
        
        return items
    
    def get_fit_by_name(self, name):
        for k, v in sm.GetService('fittingSvc').GetFittings(session.charid).items():
            if v.name == name:
                return v
    
    def equal_fit(self, new_fit, cur_fit):
        if not new_fit or not cur_fit:
            return
        
        if new_fit.shipTypeID == cur_fit.shipTypeID:
            for typeID, flag, qty in new_fit.fitData:
                if (typeID, flag, qty) not in cur_fit.fitData:
                    return False
        else:
            return False
        
        return True
    
    def get_ships(self):
        if not session.stationid:
            return
        
        hangar = invCtrl.StationShips()
        
        return [ship for ship in hangar.GetItems() if ship.singleton == 1 and ship.itemID != util.GetActiveShip()]
    
    def get_ship_by_name(self, name):
        for ship in self.get_ships():
            if name == cfg.evelocations.Get(ship.itemID).name:
                return ship
    
    # Методы -----------------------------------------------------------------------------------------------------------
    
    # Отстыкова от станции
    def undocking(self):
        if not session.stationid2 and not session.structureid:
            return
        
        item_id = session.stationid2 or session.structureid
        
        self.info('Андок от {}'.format(item_id), self.role)
        
        do_action(1 + rnd_keys())
        
        uicore.cmd.CmdExitStation()
    
    # Встать в разгон
    def align(self, place, set_align_to=True):
        if place.type == 'bm':
            self.info('Встаем в разгон на закладку {}'.format(place.name), self.role)
            sm.GetService('menu').AlignToBookmark(place.id)
        else:
            self.info('Встаем в разгон на {}'.format(place.name), self.role)
            sm.GetService('menu').AlignTo(place.id)
        
        do_action(2 + rnd_keys())
        
        if set_align_to:
            self.alignTo = place
    
    # Переместиться к месту действия
    def go(self, place):
        if sm.GetService('autoPilot').InWarp():
            return
        
        if self.alignTo:
            place = self.alignTo
            self.alignTo = None
        
        if (session.stationid or session.structureid) and not place.is_achived():
            self.undocking()
            
            return
        
        if place.surfaceDist() > const.minWarpDistance:
            if place.type == 'anomaly':
                warpDist = self.warpDist
            else:
                warpDist = 0
            
            if self.ignoreRejumps:
                place.warp(warpDist)
            
            else:
                self.get_safe_place(place, 5000).warp(warpDist)
        
        elif place.type == 'station':
            self.protect_mod_off()
            
            # Переключаем овервью на станцию
            wnd = form.ActiveItem.GetIfOpen()
            if wnd:
                wnd.OnMultiSelect([place.id])
                
                do_action(1 + rnd_keys())
            
            if place.surfaceDist() > 250:
                self.info('Приближаюсь к станции {}, дистанция {} м'.format(place.name, place.surfaceDist()), self.role)
                
                do_action(3 + rnd_keys())
                
                sm.GetService('menu').Approach(place.id)
                
                while place.surfaceDist() > 250:
                    pause()
            
            self.info('Стыкуюсь со станцией {}'.format(place.name), self.role)
            
            do_action(2 + rnd_keys())
            
            sm.GetService('menu').Dock(place.id)
        else:
            self.info('Достигли {}'.format(place.name), self.role)
    
    # Достигли домашней станции, ожидаем дальнейших инструкций
    def wait(self):
        self.info('Ожидаем инструкций', self.role)
    
    # Приблизиться к объекту в космосе
    def aproach_to(self, ball, dist=0.0):
        barrier = self.get_barrier(ball)
        
        bp = sm.GetService('michelle').GetBallpark(True)
        ship = bp.GetBallById(util.GetActiveShip())
        
        if barrier and barrier.surfaceDist < 5000:
            
            if ship.followId != barrier.id:
                try:
                    slim = bp.GetInvItem(barrier.id)
                    
                    self.info('Обнаружено препятствие, облетаем {}'.format(slim.name), self.role)
                    
                    if slim and slim.groupID == const.groupMobileWarpDisruptor:
                        radius = get_type_attr(slim.typeID, const.attributeWarpScrambleRange) + 2500
                    else:
                        radius = 2500
                    
                    do_action(2 + rnd_keys())
                    
                    movementFunctions.Orbit(barrier.id, radius)
                except:
                    pass
            
            return
        
        if ship.followId != ball.id and ball.surfaceDist > dist and not self.pen('aproach'):
            slim = bp.GetInvItem(ball.id)
            
            if slim:
                if slim.categoryID in [const.categoryAsteroid]:
                    name = evetypes.GetEnglishName(slim.typeID)
                else:
                    name = slim.name
            else:
                name = ball.id
            
            self.info('Приближаемся к объекту {}'.format(name), self.role)
            try:
                do_action(2 + rnd_keys())
                
                sm.GetService('menu').Approach(ball.id)
                self.set_pen('aproach', 2000)
            except:
                pass
        
        elif ship.followId and ball.surfaceDist <= dist and not self.pen('stop'):
            self.info('Останавливаемся', self.role)
            
            do_action(1 + rnd_keys())
            
            uicore.cmd.CmdStopShip()
            
            self.set_pen('stop', 2000)
    
    def get_shield(self, is_full=True):
        godma = sm.GetService('godma')
        
        if is_full:
            return godma.GetItem(session.shipid).shieldCapacity
        else:
            return godma.GetItem(session.shipid).shieldCharge
    
    def get_armor(self, is_full=True):
        godma = sm.GetService('godma')
        
        if is_full:
            return godma.GetItem(session.shipid).armorHP
        else:
            return godma.GetItem(session.shipid).armorDamage
    
    def get_rapair_place(self):
        sta = self.get_station()
        
        if sta:
            return sta
        
        pos = self.get_place_by_bm(_bm.get_bookmark('POS'))
        
        if pos:
            return pos
        
        return
    
    # Ремонтируем текущий корабль и модули
    def repair(self):
        if self.in_repair:
            return
        
        self.in_repair = True
        
        if session.stationid2:
            self.repair_ship()
            
            self.del_flag('damaged')
            
            if 'init' in self.actions:
                self.add_flag('init')
            
            self.run_action()
        
        else:
            self.wait()
        
        self.in_repair = False
    
    # Ремонтируем корабль
    def repair_ship(self):
        if not session.stationid2:
            return
        
        pause()
        
        if eve.stationItem.serviceMask & const.stationServiceRepairFacilities == const.stationServiceRepairFacilities:
            
            if sm.GetService('cmd').HasServiceAccess('repairshop'):
                
                repairSvc = util.Moniker('repairSvc', session.stationid2)
                invCache = sm.GetService('invCache')
                
                itemID = util.GetActiveShip()
                
                damageReports = repairSvc.GetDamageReports([itemID])
                
                total_cost = 0
                total_damage = 0
                
                itemIDs = []
                
                try:
                    for each in damageReports[itemID].quote:
                        damage = math.ceil(each.damage)
                        
                        if damage > 0.0:
                            if invCache.IsItemLocked(each.itemID):
                                raise UserError('ItemLocked', {'item': evetypes.GetEnglishName(each.typeID)})
                            if not invCache.TryLockItem(each.itemID, 'lockUnassemblingItem', {}, 1):
                                raise UserError('ItemLocked', {'item': evetypes.GetEnglishName(each.typeID)})
                            
                            total_damage += damage
                            total_cost += damage * each.costToRepairOneUnitOfDamage
                            
                            itemIDs.append(each.itemID)
                    
                    if itemIDs:
                        _m = (total_damage, total_cost)
                        self.info('Ремонтируем корабль, повреждений: {}, на сумму: {}'.format(*_m), self.role)
                        
                        do_action(7 + rnd_keys())
                        
                        repairSvc.RepairItems(itemIDs, total_cost)
                
                finally:
                    for itemID in itemIDs:
                        invCache.UnlockItem(itemID)
            
            else:
                self.warn('На станции отсутствуют службы ремонта', self.role)
            
            pause(2000)
    
    def change_fit(self):
        if not session.stationid:
            return
        
        fitSvc = sm.GetService('fittingSvc')
        
        cur_fit = util.KeyVal()
        cur_fit.shipTypeID, cur_fit.fitData = fitSvc.GetFittingDictForActiveShip()
        
        fit = self.get_fit_by_name(self.fit_name)
        
        if not fit:
            return
        
        new_fit = util.KeyVal()
        new_fit.shipTypeID, new_fit.fitData = fit.shipTypeID, fit.fitData
        
        if cfg.evelocations.Get(util.GetActiveShip()).name != fit.description:
            shipItem = self.get_ship_by_name(fit.description)
            
            if shipItem:
                self.info('Активируем корабль {}'.format(fit.description))
                
                do_action(5 + rnd_keys())
                
                sm.GetService('menu').ActivateShip(shipItem)
        
        if not self.equal_fit(new_fit, cur_fit):
            self.info('Устанавливаем фит {}'.format(self.fit_name))
            
            do_action(5 + rnd_keys())
            
            fitSvc.LoadFitting(session.charid, fit.fittingID)
        
        self.del_flag('change_fit')
    
    # Получить заданную или ближайшую станцию
    def get_station(self, stantion_id=None):
        if session.stationid2:
            sta = cfg.stations.Get(session.stationid)
            
            return StationPlace(session.stationid, sta.stationName, (sta.x, sta.y, sta.z))
        
        bp = sm.GetService('michelle').GetBallpark()
        res = []
        
        if bp:
            for ball_id, ball in bp.balls.items():
                slim = bp.GetInvItem(ball_id)
                
                if slim and slim.groupID == 15:
                    if stantion_id and ball_id == stantion_id:
                        return StationPlace(ball_id, slim.name, (ball.x, ball.y, ball.z))
                    
                    res.append((ball.surfaceDist, ball_id, slim.name, (ball.x, ball.y, ball.z)))
            
            if res:
                res.sort()
                
                return StationPlace(res[0][1], res[0][2], res[0][3])
        
        return
    
    # Пришло уведомление
    def j_notification(self, login, data):
        if not self.is_ready: return
        
        Macros.j_notification(self, login, data)
        
        if data['func'] == 'gopos':
            self.info('Прекращаем работу, перемещаемся на POS - команда gopos', self.role)
            self.add_flag('topos')
            self.run_action()
        
        elif data['func'] == 'gohome':
            self.info('Прекращаем работу, перемещаемся на станцию - команда gohome', self.role)
            self.add_flag('wait')
            self.run_action()
    
    # Пришло уведомление
    def notification(self, _from, func, *args):
        if not self.is_ready: return
        
        Macros.notification(self, _from, func, *args)
        
        if func == 'gopos':
            self.info('Прекращаем работу, перемещаемся на POS - команда gopos', self.role)
            self.add_flag('topos')
            self.run_action()
        
        elif func == 'gohome':
            self.info('Прекращаем работу, перемещаемся на станцию - команда gohome', self.role)
            self.add_flag('wait')
            self.run_action()
    
    # Ждем оканчания кулдауна клоки
    def wait_cooldown(self):
        cloaks = self.get_modules(const.groupCloakingDevice)
        
        if cloaks:
            cloak = cloaks[0]
            
            cooldownTimes = cloak.stateManager.GetCooldownTimes(cloak.moduleinfo.itemID)
            if cooldownTimes:
                startTime, duration = cooldownTimes
                
                startTime = util.BlueToDate(startTime)
                
                while True:
                    now = util.BlueToDate(blue.os.GetWallclockTime())
                    
                    if now - startTime > datetime.timedelta(seconds=duration / 1000) or self.check_in_flags('break'):
                        break
                    
                    pause(100)
                
                pause(1000)
    
    # Ждем отключения послегейтовой клоки
    def wait_gate_cloak(self):
        while self.gate_cloak and not self.check_in_flags('break'):
            pause(100)
    
    # Если после старата варпа, варпа не произошло, запускаем действие снова
    def check_after_warp(self):
        pause(5000)
        
        if self.warp_stage == 0:
            self.warn('Переход в варп режим не выполнен, повторяем', self.role)
            
            self.run_action()
    
    def fly_to(self):
        
        if self.in_fly or self.do_fly or self.check_in_flags('break'): return
        
        self.in_fly = True
        self.do_fly = True
        
        try:
            if bool(sm.GetService('starmap').destinationPath[0]):
                if session.stationid2 or session.structureid:
                    self.undocking()
                    
                    self.do_fly = False
                    
                    return
                
                elif session.solarsystemid:
                    self.wait_cooldown()
                    
                    next_point = fly.get_next_point()
                    
                    if next_point:
                        pause(1000)
                        
                        self.info('Активируем следующий объект {}'.format(next_point), self.role)
                        
                        do_action(2 + rnd_keys())
                        
                        movementFunctions.DockOrJumpOrActivateGate(next_point)
                        
                        self.wait_gate_cloak()
                        
                        stackless.tasklet(self.check_after_warp)()
            
            else:
                self.in_fly = False
            
            if self.check_in_flags('break'):
                self.do_fly = False
                
                return
            
            # Влючение модулей, после варпа
            if bool(sm.GetService('starmap').destinationPath[0]):
                if session.solarsystemid and self.check_in_flags('fly'):
                    self.covert_cloak_on()
                    
                    if self.useMWD:
                        burner = self.get_modules(const.groupAfterBurner)
                        
                        if burner:
                            stackless.tasklet(self.modules_on)(burner)
                    
                    if self.useProtect:
                        stackless.tasklet(self.protect_mod_on)()
        
        finally:
            self.do_fly = False
    
    # Окно фиттинга, открываем если закрыто
    def get_fitting(self):
        if not form.FittingWindow.IsOpen():
            form.FittingWindow.Open(shipID=util.GetActiveShip())
        
        fitwnd = form.FittingWindow.GetIfOpen()
        
        if fitwnd.IsVisible():
            fitwnd.Hide()
        
        return wnd
    
    # Резисты корабля с учетом бонусов и модулей
    # TODO: Обработать ситуацию когда есть только капсула
    def get_ship_res(self):
        res = {}
        
        for t in ('shield', 'armor', 'structure'):
            row = uiutil.FindChild(wnd, 'row_%s' % t)
            dmg = uiutil.FindChild(row, 'DamageGaugeContainerFitting')
            
            for i, n in enumerate(('em', 'th', 'kn', 'ex')):
                if t not in res:
                    res[t] = {'sum': 0}
                
                res[t][n] = int(dmg.children[i].children[1].value * 100)
                res[t]['sum'] += res[t][n]
        
        return res
    
    # Список дронов в космосе
    def get_drones_in_space(self, _type=None):
        bp = sm.GetService('michelle').GetBallpark()
        
        if not bp:
            return []
        
        res = []
        
        drones = sm.GetService('michelle').GetDrones()
        
        for droneID in drones:
            if droneID in bp.slimItems and \
                    (drones[droneID].ownerID == session.charid or drones[droneID].controllerID == session.shipid):
                
                if _type:
                    if drones[droneID].typeID == _type:
                        res.append(drones[droneID])
                else:
                    res.append(drones[droneID])
        
        return res
    
    # Список дронов на корабле
    def get_drones_in_bay(self, _type=None):
        invCache = sm.GetService('invCache')
        
        drones = invCache.GetInventoryFromId(util.GetActiveShip()).ListDroneBay()
        
        if not _type:
            return drones
        
        res = []
        
        for drone in drones:
            if _type:
                if drone.typeID == _type:
                    res.append(drone)
            else:
                res.append(drone)
        
        return res
    
    # Возвращаем дронов на корабль
    def drones_return(self, drones=None, _wait=True):
        if not _wait and self.in_drone_ret or self.pen('drone_ret'):
            return
        
        self.in_drone_ret = True
        
        if not drones:
            drones = self.get_drones_in_space()
        
        droneIDs = [x.droneID for x in drones]
        
        if droneIDs:
            if not _wait and not self.act_is_ready('drones_ret'):
                self.in_drone_ret = False
                
                return
            
            self.info('Возвращаем дронов на корабль ({} шт.)'.format(len(droneIDs)), self.role)
            
            try:
                do_action(2 + rnd_keys(), 2 + rnd_keys())
                
                self.send_action_info('drones_ret')
                
                sm.GetService('menu').ReturnToDroneBay(droneIDs)
                
                self.set_pen('drone_ret', 3000)
            except:
                pass
            
            while _wait and len(self.get_drones_in_space()) > 0 and self.grid_is_safety() \
                    and not self.check_in_flags('break'):
                
                drones = self.get_drones_in_space()
                
                droneIDs = []
                
                for drone in drones:
                    if drone.activityState not in [const.entityDeparting, const.entityPursuit]:
                        droneIDs.append(drone.droneID)
                
                if droneIDs and not self.pen('drone_ret'):
                    do_action(2 + rnd_keys(), 2 + rnd_keys())
                    
                    self.send_action_info('drones_ret')
                    
                    sm.GetService('menu').ReturnToDroneBay(droneIDs)
                    
                    self.set_pen('drone_ret', 3000)
                
                pause(500)
            
            if not self.get_drones_in_space():
                self.info('Все дроны возвращены на корабль', self.role)
            else:
                self.info('В космосе остались дроны', self.role)
        
        else:
            self.info('Дроны в космосе не обнаружены', self.role)
        
        self.in_drone_ret = False
    
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
            
            self.in_fly = False
            
            self.run_action()
    
    # Приварп
    def OnWarpFinished(self, *args):
        self.warp_stage = 0
        
        if not self.is_ready: return
        
        self.info('Приварп', self.role)
        
        self.run_action()
    
    # Сообщение вернуться на домашнюю станцию и ожидать команд
    def OnGoHome(self):
        if not self.is_ready: return
        
        if not self.check_in_flags('wait'):
            self.info('Прекращаем работу, перемещаемся на станцию - команда GoHome', self.role)
            
            self.add_flag('wait')
            
            self.run_action()
    
    # Сообщение вернуться на пос и ожидать команд
    def OnGoPos(self):
        
        if not self.is_ready: return
        
        if not self.check_in_flags(['wait', 'panic', 'topos']):
            if self.check_scrambler():
                self.warn('Не удается отварпать, корабль на дизе', self.role)
            else:
                self.info('Прекращаем работу, перемещаемся на POS - команда GoPos', self.role)
            
            if self.warp_stage == 1:
                if uicore.layer.shipui.isopen:
                    uicore.layer.shipui.StopShip()
                    pause(500)
            
            self.add_flag('topos')
            
            self.run_action()
    
    # Сообщение продолжить выполение инстукций
    def OnGoWork(self):
        if not self.is_ready: return
        
        if self.check_in_flags(['wait', 'panic', 'topos', 'enemy']):
            self.info('Продолжаем работать - команда GoWork', self.role)
            
            self.del_flag('wait')
            self.del_flag('panic')
            self.del_flag('topos')
            self.del_flag('enemy')
        
        self.run_action()
    
    # Смена корабля в космосе, используем для определения момента перехода в капсулу
    def ProcessActiveShipChanged(self, shipID, oldShipID):
        if not self.is_ready: return
        
        if session.solarsystemid:
            pause()
            
            bp = sm.GetService('michelle').GetBallpark(True)
            
            slim = bp.GetInvItem(shipID)
            
            if slim and slim.groupID == const.groupCapsule:
                self.warn('Корабль уничтожен, капсула катапультирована', self.role)
                
                if 'wait' not in self.flags:
                    self.add_flag('wait')
                
                self.run_action()
    
    # Капсула уничтожена
    def OnPlayerPodDeath(self):
        if not self.is_ready: return
        
        self.warn('Ну все, здравствуй клонилка', self.role)
        self.OnScriptBreak()
    
    # Применяются системы РЭБ
    def OnJamStart(self, sourceBallID, moduleID, targetBallID, jammingType, startTime, duration):
        if not self.is_ready: return
        
        if targetBallID == session.shipid and 'jam' not in self.ewar and jammingType == 'electronic':
            self.info('Применяются системы глушения лока ({})'.format(sourceBallID), self.role)
            
            self.ewar.append('jam')
    
    # Системы РЭБ отключены
    def OnJamEnd(self, sourceBallID, moduleID, targetBallID, jammingType):
        if not self.is_ready: return
        
        if targetBallID == session.shipid and 'jam' in self.ewar and jammingType == 'electronic':
            self.info('Системы глушения лока отключены ({})'.format(sourceBallID), self.role)
            
            self.ewar.remove('jam')
    
    def OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args):
        if not self.is_ready or sm.StartService('map').GetSecurityStatus(session.solarsystemid2) > 0.0: return
        
        if isinstance(channelID, tuple) and channelID[0][0] == 'solarsystemid2':
            
            if method == 'JoinChannel':
                safetyLevel = self.get_min_safety_level()
                
                if safetyLevel <= 0 and 'enemy' not in self.flags:
                    self.warn('Враги в локале', self.role)
                    
                    self.add_flag('enemy')
                    self.add_flag('topos')
                    
                    if session.solarsystemid:
                        self.run_action()
            
            elif method == 'LeaveChannel':
                safetyLevel = self.get_min_safety_level()
                
                if safetyLevel > 0 and 'enemy' in self.flags:
                    self.flags.remove('enemy')
                    self.warn('В локале безопасно', self.role)
        
        elif isinstance(channelID, types.IntType):
            if channelID in [-XXXXXXXX] and method == 'SendMessage':
                res = verify_text(args[0])
                
                if res == 0 and self.role == 'eyes':
                    self.warn('Паника в секьюре', self.role)
                    
                    # if res == 0 and session.solarsystemid and 'panic' not in self.flags:
                    #     self.add_flag('panic')
                    #
                    #     self.run_action()
    
    def WindowClose(self, wnd):
        
        pause(500)
        
        wnd.CloseByUser()
        
        pause(500)
        
        if wnd:
            wnd.Close()
    
    # Событие открытия нового окна
    def OnWindowOpened(self, wnd):
        
        # Окно появляется при варпе на гравик
        if wnd.__guid__ == 'form.Telecom':
            pause()
            
            self.info('Закрываем окно телекома')
            wnd.Close()
        
        elif wnd.__guid__ == 'form.MessageBox':
            pause()
            
            caption = wnd.FindChild('EveCaptionLarge').text.encode('utf-8')
            
            # Окно появляется за 60, 15 и 5 минут до ДТ
            if caption == 'Идет выключение':
                self.info('Закрываем окно ДТ')
                
                stackless.tasklet(self.WindowClose)(wnd)
                
                sm.ScatterEvent('OnDownTime')
            
            elif caption == 'Не хватает места':
                self.warn('Не хватает места')
                
                wnd.Close()
            
            elif caption == 'Информация':
                self.warn('Информация')
            
            elif caption == 'Потеряно соединение':
                self.warn('Потеряно соединение')
                
                wnd.Close()
            
            elif caption == 'Заблокирована группа вызовов':
                self.warn('Заблокирована группа вызовов')
                
                wnd.Close()
            
            elif caption in ['Действительно создать контракт?', 'Присоединиться к флоту?']:
                pass
            
            else:
                self.warn('Не обработанный MessageBox: {}'.format(caption))
        
        # Окно запроса присоединения к чату, не появляется если собеседник находится в списке
        elif wnd.__guid__ == 'form.ChatInviteWnd':
            rand_pause(5000, 10000)
            
            wnd.FindChild('OK_Btn').Confirm()
    
    def DoDestinyUpdate(self, state, waitForBubble, dogmaMessages=[], doDump=True):
        if not self.is_ready: return
        
        for action in state:
            if action[1][0] == 'UncloakBall' and action[1][1][0] == session.shipid:
                self.gate_cloak = False
                
                break
            
            elif action[1][0] == 'OnSpecialFX' \
                    and action[1][1][0] == session.shipid \
                    and action[1][1][5] == 'effects.JumpOut':
                
                self.gate_opened = True
                self.gate_cloak = True
    
    # Если гейт не прогрузился, повторяем попытку
    def _CheckGateOpened(self):
        pause(2000)
        
        if not self.gate_opened:
            self.in_fly = False
            
            self.run_action()
    
    # Начало прохода в гейт
    def OnSessionMutated(self, isremote, sess, change):
        if not self.is_ready or not self.check_in_flags('fly'): return
        
        if isinstance(sess, tuple):
            if len(sess) == 3 and sess[2] == session.shipid:
                self.gate_opened = False
                
                stackless.tasklet(self._CheckGateOpened)()
    
    def _OnWarpStarted2(self):
        pause(3000)
        
        self.covert_cloak_on()
    
    def OnWarpStarted(self):
        self.warp_stage = 1
    
    def OnWarpStarted2(self):
        self.warp_stage = 2
        
        if not self.is_ready or not self.check_in_flags('fly'): return
        
        stackless.tasklet(self._OnWarpStarted2)()
        
        # endregion
