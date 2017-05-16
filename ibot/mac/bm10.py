import invCtrl
import log
import util
from eve.client.script.ui.services.menuSvcExtras import movementFunctions

import ibot.utils.bms as _bm
from ibot.mac.template.oldspace import Space
from ibot.utils import *


def run():
    if not bot.macros:
        bot.macros = Bm10()


class Bm10(Space):
    __notifyevents__ = [
        'OnDamageStateChange'
    ]
    
    # Инициализация класса
    def __init__(self):
        
        self.actions = {
            'init': {
                'co': [
                    lambda: self.check_in_flags('init'),
                ],
                'do': self.init,
                'pr': 40
            },
            'work': {
                'co': [
                    lambda: self.check_empty_flags()
                ],
                'do': self.work
            }
        }
        
        self.in_work_flag = False
        self.enemy_flag = False
        
        self.exp = {}
        
        self.sta_sys = None  # Система со станкой на которой будет оставлена бука
        
        self.in_panic = False
        self.last_panic = util.BlueToDate(blue.os.GetWallclockTime())
        self.current_shield = None
        
        Space.__init__(self, 'bm10')
        
        self.check_pass_limit = 2
        
        self.clean_exp()
        
        self.add_flag('init')
        
        self.is_ready = True
        
        self.run_action()
    
    def init(self):
        pos = self.get_place_by_bm(_bm.get_bookmark('POS'))
        
        if pos and pos.is_achived():
            ship = sm.GetService('godma').GetItem(session.shipid)
            
            # Если текущий корабль не яхта, пересаживаемся
            if ship and ship.typeID != 34590:
                yacht = self.get_yacht_ship()
                
                stackless.tasklet(self.protect_mod_off)()
                
                pause(3000)
                
                if yacht:
                    if yacht.surfaceDist > 6000:
                        do_action(2 + rnd_keys())
                        
                        sm.GetService('menu').Approach(yacht.id)
                    
                    while yacht.surfaceDist > 6000:
                        pause(200)
                    
                    do_action(2 + rnd_keys())
                    
                    self.info('Пересаживаемся на яхту', self.role)
                    sm.GetService('menu').Board(yacht.id)
                
                else:
                    self.warn('Яхта под полем не обнаружена', self.role)
                    
                    return
        
        self.update_exp()
        
        if self.exp and self.exp['status'] == 0:
            self.set_exp_status(1)
            
            _bm.del_bookmark('RetPlace')
            _bm.set_bookmark('RetPlace')
        
        self.del_flag('init')
        
        self.do_pass()
        
        self.run_action()
    
    def work(self):
        if self.in_work_flag or self.in_fly or self.do_fly: return
        
        self.in_work_flag = True
        
        if self.exp and self.exp['status'] != 4:
            
            if self.exp['status'] == 1:  # 10ка еще не забукана
                
                # Система с 10кой еще не достигнута
                if session.solarsystemid != self.exp['system_id']:
                    self.info('Устанавливаем маршрут до 10ки', self.role)
                    self.set_route(self.exp['system_id'])
                    
                    self.add_flag('fly')
                    
                    self.run_action()
                
                # Находимся в системе с 10кой
                else:
                    journal = sm.GetService('journal')
                    exp_id = self.exp['exp_id']
                    
                    gate = self.get_exp_gate()
                    
                    if exp_id in journal.pathPlexPositionByInstanceID:
                        resp = journal.pathPlexPositionByInstanceID[exp_id]
                    else:
                        resp = sm.RemoteSvc('keeper').CanWarpToPathPlex(exp_id)
                    
                    # Варпаем на врата ускорения
                    if resp is True:
                        self.info('Варпаем на врата ускорения', self.role)
                        
                        self.warp_to_exp()
                    
                    # Если врата в гриде делаем закладку
                    elif gate:
                        self.info('Создаем закладку на 10ку', self.role)
                        
                        self.make_exp_bm(gate)
                        self.set_exp_status(2)
                        
                        self.set_sta_system()
                        
                        bp = sm.GetService('michelle').GetBallpark()
                        
                        if bp:
                            ball = bp.GetBallById(gate.itemID)
                            
                            if ball:
                                
                                mwd = self.get_modules(const.groupAfterBurner)
                                
                                if mwd:
                                    stackless.tasklet(self.modules_on)(mwd)
                                
                                do_action(3 + rnd_keys())
                                
                                movementFunctions.KeepAtRange(gate.itemID, 10000)
                                
                                pause(500)
                                
                                if mwd:
                                    stackless.tasklet(self.modules_off)(mwd)
                                
                                while ball.surfaceDist < 5000 and self.check_in_flags('break'):
                                    pause(100)
                        
                        self.run_action()
            
            elif self.exp['status'] == 2:  # 10ка забукана
                if session.stationid:
                    hangar = invCtrl.StationItems()
                    
                    bms = _bm.get_bookmarks('10/10', True)
                    
                    bmIDs = [x.bookmarkID for x in bms if x.locationID == self.exp['system_id']]
                    
                    if bmIDs:
                        self.info('Переносим буку на станку', self.role)
                        
                        do_action(3 + rnd_keys())
                        
                        hangar.AddBookmarks(bmIDs)
                    
                    self.set_exp_status(3)
                    
                    self.run_action()
                
                elif self.exp['sta_system'] != session.solarsystemid:
                    self.info('Устанавливаем маршрут до станки', self.role)
                    self.set_route(self.exp['sta_system'])
                    
                    self.add_flag('fly')
                    
                    self.run_action()
                
                else:
                    sta = self.get_station()
                    
                    if sta:
                        if sta.surfaceDist() > const.minWarpDistance:
                            self.wait_cooldown()
                            
                            self.info('Варпаем к станке', self.role)
                            sta.warp()
                            
                            self.wait_gate_cloak()
                            self.covert_cloak_on()
                        
                        else:
                            self.info('Докаемся', self.role)
                            self.go(sta)
            
            elif self.exp['status'] == 3:  # 10ка оставлена на ближайшей станке
                self.info('Создаем контракт на буку', self.role)
                
                pause(5000)
                
                if session.stationid:
                    if self.create_contract():
                        self.info('Контракт создан', self.role)
                        
                        self.set_exp_status(4)
                        
                        self.run_action()
                    
                    else:
                        self.warn('Не удалось создать контракт', self.role)
        
        else:
            ret_place = _bm.get_bookmark('RetPlace', ignoreLocation=True)
            
            if ret_place:
                if session.solarsystemid2 != ret_place.locationID:
                    self.info('Устанавливаем маршрут до дома', self.role)
                    
                    self.set_route(ret_place.locationID)
                    
                    self.add_flag('fly')
                    
                    self.run_action()
                
                else:
                    place = self.get_place_by_bm(ret_place)
                    
                    if place.surfaceDist() > const.minWarpDistance:
                        self.wait_cooldown()
                        
                        self.info('Варпаем на ПОС', self.role)
                        
                        place.warp()
                        
                        self.wait_gate_cloak()
                        self.covert_cloak_on()
                    
                    elif place.is_achived():
                        _bm.del_bookmark('RetPlace')
                        
                        ship = self.get_old_ship()
                        
                        if ship:
                            if ship.surfaceDist > 6000:
                                do_action(3 + rnd_keys())
                                
                                sm.GetService('menu').Approach(ship.id)
                            
                            while ship.surfaceDist > 6000:
                                pause(200)
                            
                            self.info('Пересаживаемся на крабский корабль', self.role)
                            
                            do_action(3 + rnd_keys())
                            
                            sm.GetService('menu').Board(ship.id)
                            
                            self.set_yacht_free()
                            
                            # bot.change_args = {}
                            
                            self.warn('Работа с 10ками звершена', self.role)
                            
                            bot.change_role('crub')
                        
                        else:
                            self.warn('Корабль угнан или занят', self.role)
                            
                            ship = sm.StartService('gameui').GetShipAccess()
                            if ship:
                                log.LogNotice('Ejecting from ship', session.shipid)
                                sm.ScatterEvent('OnBeforeActiveShipChanged', None, util.GetActiveShip())
                                sm.StartService('sessionMgr').PerformSessionChange('eject', ship.Eject)
                            
                            self.set_yacht_free()
                            
                            sm.ScatterEvent('OnScriptBreak')
                    
                    else:
                        self.go(place)
        
        self.in_work_flag = False
    
    # Создаем контракт на 10ку
    def create_contract(self):
        
        self.do_pass()
        
        items = []
        
        hangar = invCtrl.StationItems()
        
        for item in hangar.GetItems():
            if item.typeID == const.typeBookmark:
                items.append([item.itemID, 1])
        
        contractID = None
        
        if items:
            args = (
                const.conTypeItemExchange,  # type
                True,  # avail
                XXXXXXXXX,  # assigneeID
                1440,  # expiretime
                0,  # duration
                long(session.stationid),  # startStationID
                None,  # endStationID
                0,  # price
                0,  # reward
                0,  # collateral
                self.get_label(),  # title
                '',  # description
                items,  # itemList
                4,  # flag
                [],  # requestItemTypeList
                False  # forCorp
            )
            
            try:
                do_action(15 + rnd_keys(), 24 + rnd_keys(3, 15))
                
                contractID = sm.GetService('contracts').CreateContract(*args)
            except UserError as e:
                self.warn('Ошибка создания контракта: {}'.format(e.msg), self.role)
        
        return contractID
    
    # Задаем маршрут
    def set_route(self, point):
        if sm.GetService('starmap').destinationPath[-1] != point:
            do_action(3 + rnd_keys())
            
            sm.GetService('starmap').SetWaypoint(point, True)
    
    # Варпаем на врата ускорения 10ки
    def warp_to_exp(self):
        bp = sm.StartService('michelle').GetRemotePark()
        if bp:
            self.wait_cooldown()
            
            if self.check_in_flags('break'):
                return
            
            do_action(3 + rnd_keys())
            
            bp.CmdWarpToStuff('epinstance', self.exp['exp_id'])
            
            self.wait_gate_cloak()
            self.covert_cloak_on()
    
    # Создаем буку 10ки
    def make_exp_bm(self, gate):
        self.do_pass()
        
        bmsvc = sm.GetService('bookmarkSvc')
        
        label = self.get_label()
        note = ''
        
        do_action(2 + rnd_keys(), 5 + rnd_keys())
        
        bmsvc.BookmarkLocation(gate.itemID, session.charid, label, note, gate.typeID,
                               session.solarsystemid, folderID=_bm.get_folder_id('10/10'))
    
    def get_label(self):
        now = self.exp['s_time']
        
        label = '10/10 '
        label += cfg.evelocations.Get(self.exp['system_id']).name[:-1]
        label += ' {:0>2}.{:0>2} {:0>2}:{:0>2}'.format(now.day, now.month, now.hour, now.minute)
        
        return label
    
    # Получить врата ускорения
    def get_exp_gate(self):
        bp = sm.GetService('michelle').GetBallpark()
        
        if bp:
            for ball_id, ball in bp.balls.items():
                slim = bp.GetInvItem(ball_id)
                
                if slim and slim.groupID == 366:
                    return slim
        
        return None
    
    def set_exp_status(self, status):
        if self.exp:
            query = 'UPDATE eve_exp SET status = %s '
            query += 'WHERE exp_id = %s'
            
            db_query(query, (status, self.exp['exp_id']))
            
            self.exp['status'] = status
    
    def set_sta_system(self):
        if not self.exp['sta_system']:
            
            if self.get_station():
                sta_system = session.solarsystemid
            else:
                sta_system = self.get_near_sta()
            
            if sta_system:
                query = 'UPDATE eve_exp SET sta_system = %s '
                query += 'WHERE exp_id = %s'
                
                db_query(query, (sta_system, self.exp['exp_id']))
                
                self.exp['sta_system'] = sta_system
    
    def get_yacht_ship(self):
        bp = sm.GetService('michelle').GetBallpark()
        
        if not bp:
            return None
        
        for ball_id, ball in bp.balls.items():
            
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.typeID == 34590 and slim.name == 'Ship Name' and slim.charID is None:
                return ball
        
        return None
    
    def get_old_ship(self):
        bp = sm.GetService('michelle').GetBallpark()
        
        if bp and 'ship_id' in bot.change_args:
            ball = bp.GetBallById(bot.change_args['ship_id'])
            slim = bp.GetInvItem(bot.change_args['ship_id'])
            
            if ball and slim and slim.charID is None:
                return ball
        
        return None
    
    def clean_exp(self):
        query = "DELETE FROM eve_exp WHERE e_time < %s AND char_id = %s"
        db_query(query, (util.BlueToDate(blue.os.GetWallclockTime()), session.charid))
    
    def update_exp(self):
        query = 'SELECT exp_id, s_time, e_time, system_id, status, sta_system FROM eve_exp '
        query += 'WHERE char_id = %s AND status < 4 '
        query += 'ORDER BY status LIMIT 1'
        
        ans = db_select(query, (session.charid,))
        
        if ans:
            ans = ans[0]
            
            self.exp = {
                'exp_id': ans[0],
                's_time': ans[1],
                'e_time': ans[2],
                'system_id': ans[3],
                'status': ans[4],
                'sta_system': ans[5]
            }
    
    def fly_to(self):
        if self.in_fly or self.do_fly: return
        
        Space.fly_to(self)
        
        if not self.check_in_flags('break'):
            if not bool(sm.GetService('starmap').destinationPath[0]):
                sysname = cfg.evelocations.Get(session.solarsystemid2).name
                self.info('Конечная точка маршрута достигнута {}'.format(sysname), self.role)
                
                self.del_flag('fly')
                
                self.run_action()
    
    # Получить ближайшую систему со станкой
    def get_near_sta(self):
        sys_name = cfg.evelocations.Get(session.solarsystemid).name[:-1]
        
        query = 'SELECT to_sys FROM eve_sys_link '
        query += 'WHERE from_sys LIKE %s'
        
        ret = db_select(query, ("%" + sys_name + "%",))
        
        if ret:
            ret = ret[0][0]
        
        return ret
    
    def set_yacht_free(self):
        rec = {'type': 'set_yacht_free'}
        
        j_send_far('ruller', rec)
    
    def OnWarpStarted2(self):
        if not self.is_ready: return
        
        self.do_pass()
        
        if self.check_enemy_in_local():
            cloaks = self.get_modules(const.groupCloakingDevice)
            stackless.tasklet(self.modules_off)(cloaks)
        
        else:
            Space.OnWarpStarted2(self)
    
    def panic_attack(self):
        if self.in_panic:
            return
        
        self.in_panic = True
        
        full = self.get_shield()
        curr = self.get_shield(False)
        
        if self.current_shield is None:
            self.current_shield = full - curr
        
        if full - curr < full * 0.95:
            now = util.BlueToDate(blue.os.GetWallclockTime())
            
            if now - self.last_panic > datetime.timedelta(seconds=10) and self.current_shield > full - curr:
                self.warn('Корабль атакуют, сваливаем!', self.role)
                self.last_panic = now
        
        self.current_shield = full - curr
        
        self.in_panic = False
    
    def OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args):
        if not self.is_ready: return
        
        if isinstance(channelID, tuple) and channelID[0][0] == 'solarsystemid2':
            
            if method == 'JoinChannel':
                safetyLevel = self.get_min_safety_level()
                
                if safetyLevel <= 0 and not self.enemy_flag:
                    self.enemy_flag = True
                    
                    sys_name = cfg.evelocations.Get(session.solarsystemid2).name[:-1]
                    self.warn('Враги в системе {}'.format(sys_name), self.role)
            
            elif method == 'LeaveChannel':
                safetyLevel = self.get_min_safety_level()
                
                if safetyLevel > 0 and self.enemy_flag:
                    self.enemy_flag = False
                    
                    sys_name = cfg.evelocations.Get(session.solarsystemid2).name[:-1]
                    self.warn('В системе {} чисто'.format(sys_name), self.role)
    
    def DoDestinyUpdate(self, state, waitForBubble, dogmaMessages=[], doDump=True):
        if not self.is_ready: return
        
        Space.DoDestinyUpdate(self, state, waitForBubble, dogmaMessages, doDump)
        
        for action in state:
            if action[1][0] == 'OnSpecialFX' \
                    and action[1][1][0] == session.shipid \
                    and action[1][1][5] == 'effects.JumpOut':
                self.enemy_flag = False
    
    def OnDamageStateChange(self, shipID, damageState):
        if not self.is_ready: return
        
        if session.shipid == shipID:
            # Ремонтируем щит или броню
            stackless.tasklet(self.panic_attack)()
