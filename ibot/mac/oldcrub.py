import re
import types

import evetypes
import localization
import stackless
import util
from sensorsuite.overlay.sitetype import *

import ibot.utils.bms as _bm
from ibot.mac.template.oldspace import Oldspace
from ibot.utils.places import *


def run():
    if not bot.macros:
        bot.macros = Crub()


# TODO: Удалять старые буки в Places
# TODO: При получении команды гопос, если корабль в режиме разгона остановиться, а потом варпать на ПОС

class Oldcrub(Oldspace):
    __notifyevents__ = [
        'DoBallsAdded',
        'DoBallRemove',
        'DoBallsRemove',
        'OnEwarEndFromTactical',
        'OnSignalTrackerAnomalyUpdate',
        'OnDamageStateChange'
    ]
    
    # Инициализация класса
    def __init__(self, _run=True):
        
        self.actions = {
            'init': {
                'co': [
                    lambda: self.check_in_flags('init'),
                    lambda: not self.check_enemy_in_local()
                ],
                'do': self.init,
                'pr': 40
            },
            'fight': {
                'co': [
                    lambda: bool(self.place),
                    lambda: self.check_empty_flags() or self.check_scrambler(),
                    lambda: not self.check_enemy_in_local() or self.check_scrambler()
                ],
                'po': lambda: self.place,
                'go': self.go,
                'do': self.fight,
                'tm': None,
                'iv': 1000,
                'ed': self.end_fight
            },
            'bm10': {
                'co': [
                    lambda: self.check_in_flags(['bm10'])
                ],
                'po': lambda: self.get_place_by_bm(_bm.get_bookmark('POS')),
                'go': self.go,
                'do': self.bm10
            },
        }
        
        Oldspace.__init__(self, 'crub')
        
        self.in_do_flag = False
        self.in_target_work = False
        self.in_drones_work_flag = False
        self.in_drones_lockout_flag = False
        self.in_update_crub_place = False
        self.in_drones_run = False
        
        self.only_first = True
        self.full_wreck_flag = False
        self.need_up_queue_flag = True
        self.import_npc_flag = True
        self.last_flag = False
        self.other_ship = False
        self.current_repair_flag = False
        
        self.queue = []
        self.locked_drones = {}
        self.drones_dps = {}
        
        self.place = None
        self.status = self.s.ga('DefaultStatus', 'busy')
        self.busy_only_first = self.s.ga('OnlyFirst', True)
        self.primaryDamage = self.s.ga('PrimaryDamage', 'Em')
        self.add_time = int(self.s.ga('AddTime', 110000))
        self.min_sig = int(self.s.ga('HeavyMinSig', 50))
        self.tank_type = self.s.ga('TankType', 'shield')
        self.align_to_pos_flag = bool(self.s.ga('AlignToPos', False))
        self.align_to_pre_flag = bool(self.s.ga('AlignToPre', False))
        
        self.anomalyType = self.s.ga('AnomalyType', None)
        
        self.grl = self.s.ga('GrLogic', self.role)  # Группа, для разделения крабов по аномалькам
        
        chList = self.s.ga('CrubChList', None)
        self.chList = {}
        
        self.last_set_coord = datetime.datetime.now()
        
        if chList:
            for ch in chList.split(';'):
                c = ch.split(':')
                
                self.chList[int(c[0])] = int(c[1])
        
        if self.s.gan('SendToChannel', False) and session.solarsystemid in self.chList:
            if self.chList[session.solarsystemid] not in sm.GetService('LSC').channels:
                self.warn('Не открыт краб-канал, запуск макроса не возможен', self.role)
                
                sm.ScatterEvent('OnScriptBreak')
                
                return
        
        # Тип и количество дронов для крабинга
        drones = self.s.ga('DroneList', '').split(';')
        
        self.drones = {}
        
        for d in drones:
            ds = d.split(':')
            
            if ds:
                self.drones[int(ds[0])] = int(ds[1])
        
        self.info('Макрос запущен', self.role)
        
        if 'flags' in bot.change_args and bot.change_args['flags']:
            self.flags = bot.change_args['flags']
        
        if self.flags:
            self.del_flag('break')
            self.info('Установленные флаги {}'.format(self.flags), self.role)
        
        bot.change_args = {}
        
        self.is_ready = True
        
        set_bot_params('role', self.role)
        set_bot_params('group', self.grl)
        
        pause(1000)
        
        if Place.get_current():
            self.import_npc_flag = False
        
        else:
            Place.clear_places()
        
        self.clean_exp()
        
        stackless.tasklet(self.update_crub_places)()
        
        if self.check_empty_flags():
            self.add_flag('init')
        
        self.run_action()
    
    def init(self):
        if self.last_flag:
            self.add_flag('topos')
        
        if not self.check_drones_count():
            self.warn('Недостаточно дронов, перемещаюсь на ПОС', self.role)
            self.add_flag('topos')
        
        if self.flag('topos'):
            self.del_flag('init')
            
            self.run_action()
            
            return
        
        self.do_pass()
        
        if self.i_am_is_primary(group=self.grl):
            _add_time = 0
            
            if self.s.gan('SendToChannel', True):
                _add_time = self.add_time + get_random(1000, 20000)
            
            if not self.act_is_ready('send_num_anomaly', add_time=_add_time, gr=self.grl, lock=True):
                pause(1000)
                stackless.tasklet(self.wait_free_anomaly)()
                return
            
            else:
                res = self.get_crub_place(True)
        
        else:
            res = self.get_crub_place()
        
        self.locked_drones = {}
        self.drones_dps = {}
        self.only_first = True
        
        if res[0]:
            place = res[0]
            status = res[1]
            
            if self.i_am_is_primary(group=self.grl) or \
                            not self.i_am_is_primary(group=self.grl) and status in ['marked', 'begined']:
                
                if status in ['free', 'pre'] and not self.get_send_status(place.id):
                    flag = self.s.gan('SendToChannel', False)
                    
                    if flag:
                        if session.solarsystemid in self.chList:
                            wnd = sm.GetService('LSC').GetChannelWindow(self.chList[session.solarsystemid])
                            
                            if wnd:
                                do_action(3 + rnd_keys(), 5 + rnd_keys())
                                
                                wnd.input.SetValue(place.name[-3:])
                                
                                pause(100)
                                
                                wnd.InputKeyUp()
                        else:
                            self.warn('Краб-канал системы не задан', self.role)
                    
                    self.warn('Отправили в краб-канал номер аномальки: {}'.format(place.name[-3:]), self.role)
                
                self.del_flag('init')
                
                self.place = place
            
            pause(1000)
            
            if not self.check_in_flags('init') and self.get_anomaly_status(place.id, self.grl) == 'busy':
                self.add_flag('init')
            
            self.run_action()
        
        else:
            self.unlock_action('send_num_anomaly', gr=self.grl)
            
            pos = self.get_place_by_bm(_bm.get_bookmark('POS'))
            
            if not pos.is_achived():
                pos.warp()
            
            stackless.tasklet(self.wait_free_anomaly)()
    
    def fight(self):
        if self.in_do_flag or (self.flags and not self.check_scrambler()):
            return
        
        self.in_do_flag = True
        
        current = Place.get_current()
        
        if not current:
            self.warn('Не удалось получить текущее место, варпаем на ПОС', self.role)
            
            self.add_flag('topos')
            
            self.run_action()
            
            self.in_do_flag = False
            
            return
        
        if self.only_first:
            self.only_first = False
            self.full_wreck_flag = False
            self.need_up_queue_flag = True
            self.drones_dps = {}
            
            if self.anomaly_is_busy() or self.get_anomaly_status(current.id, self.grl) == 'busy':
                self.warn('Аномаль уже занята: {}'.format(current.name), self.role)
                
                self.set_anomaly_status(current.id, 'busy')
                
                self.add_flag('init')
                
                self.run_action()
                
                return
            
            status = self.get_anomaly_status(current.id, self.grl)
            
            if status in ['free', 'marked']:
                if self.i_am_is_primary(group=self.grl):
                    self.set_anomaly_status(current.id, 'begined', self.grl)
            
            self.drones_return()
            
            dogmaLocation = sm.GetService('clientDogmaIM').GetDogmaLocation()
            shipDogmaItem = dogmaLocation.dogmaItems[session.shipid]
            
            drones = dogmaLocation.GatherDroneInfo(shipDogmaItem)
            
            if not drones:
                self.warn('Дроны потеряны, варпаю на ПОС', self.role)
                
                self.add_flag('topos')
                
                self.run_action()
                
                return
            
            # Включаем DCU
            self.modules_on(self.get_modules(407))
            
            # Включаем ECM
            self.modules_on(self.get_modules(const.groupElectronicCounterMeasureBurst))
            
            # Включаем трекинг линки
            self.modules_on(self.get_modules(646))
            
            pause(1000)
            
            for k, v in drones.items():
                for type_id, bw, qty, dps in drones[k]:
                    self.drones_dps[type_id] = int(dps * 1000)
            
            self.del_place_bms(current.name)
            _bm.set_bookmark(current.name, folder='Places')
            
            while not self.act_is_ready('drones_run', self.grl) and not self.flags:
                pause(1000)
            
            self.drones_run()
            
            # Встаем в разгон на ПОС
            if self.align_to_pos_flag:
                pos = self.get_place_by_bm(_bm.get_bookmark('POS'))
                
                self.align(pos, False)
                
                stackless.tasklet(self.set_speed)(0.76)
            
            elif self.align_to_pre_flag and self.check_empty_flags() and not self.last_flag:
                self.align_to_pre(0.76)
            
            set_bot_params('place', current.id)
            
            self.update_npc_queue()
            
            empty_list = []
            
            bp = sm.GetService('michelle').GetBallpark()
            
            if bp:
                for npc_id, drone_list, bot_list in self.queue:
                    ball = bp.GetBallById(npc_id)
                    
                    if not ball:
                        empty_list.append(npc_id)
                
                if empty_list:
                    self._del_npcs(current.id, empty_list)
                    
                    self.set_pen('npc_lock', 1000)  # 2
            
            self.in_do_flag = False
            
            return
        
        if session.shipid and not self.pen('protect_on'):
            capacitor = sm.GetService('godma').GetItem(session.shipid)
            
            if capacitor.charge > capacitor.capacitorCapacity * 0.1:
                self.protect_mod_on()
                
                self.set_pen('protect_on', 3000)
        
        # Если включаем скрипт находясь в аномали, добавляем непсь руками
        if not self.import_npc_flag:
            
            bp = sm.GetService('michelle').GetBallpark()
            
            if bp:
                npc_list = []
                
                for ball_id in bp.balls.keys():
                    slim = bp.GetInvItem(ball_id)
                    
                    if slim:
                        if slim.groupID in self.get_npc_pirates() or slim.groupID == const.groupDestructibleSentryGun:
                            npc_list.append(slim)
                
                if npc_list:
                    self.add_to_space(npc_list)
        
        # --------------------------------------------------------------------------------------------------------------
        
        if self.need_up_queue_flag:
            self.update_npc_queue()
        
        if self.need_repair():
            return
        
        if self.other_ship:
            bp = sm.GetService('michelle').GetBallpark()
            
            j_owns = [x['id'] for x in bot.bots.values()] + [session.charid]
            
            flag = False
            
            if bp:
                for ball_id in bp.balls.keys():
                    slim = bp.GetInvItem(ball_id)
                    
                    if slim and slim.categoryID == 6 and slim.ownerID not in j_owns:
                        flag = True
                        break
                
                self.other_ship = flag
        # --------------------------------------------------------------------------------------------------------------
        
        if self.anomaly_is_ended():
            if self.wreck_in_space() and not bool(self.s.gan('SkipWreck', True)):
                if not self.full_wreck_flag:
                    self.do_pass()
                    
                    self.drones_return(_wait=False)
                    
                    if self.i_am_is_primary(group=self.grl):
                        self.warn('В гриде обнаружен полный врек', self.role)
                    else:
                        self.info('В гриде обнаружен полный врек', self.role)
                    
                    self.full_wreck_flag = True
            
            else:
                if self.align_to_pre_flag and self.check_empty_flags() and not self.last_flag:
                    self.align_to_pre(1.0)
                
                self.info('Выполнение аномали завершено: {}'.format(current.name), self.role)
                
                self.set_anomaly_status(current.id, 'ended', self.grl)
                
                self.place = None
                
                self.run_action()
                
                return
        
        else:
            stackless.tasklet(self.drones_lockout)()
            stackless.tasklet(self.drones_work)()
            
            stackless.tasklet(self.target_work)()
        
        self.in_do_flag = False
    
    def end_fight(self):
        current = Place.get_current()
        
        if current:
            self.del_place_bms(current.name)
            
            status = self.get_anomaly_status(current.id, self.grl)
            
            if status == 'begined':
                _bm.set_bookmark(current.name, folder='Places')
        
        self.do_pass()
        
        self.drones_return()
        
        if not self.check_drones_count():
            self.warn('Недостаточно дронов, возможна потеря', self.role)
            
            if not self.check_enemy_in_local():
                pause(10000)
        
        if self.grid_is_safety() and not self.check_enemy_in_local():
            pause(1000)
        
        set_bot_params('place', None)
        
        if self.s.gan('FlyExp') and self.get_exp_count() > 0 and self.get_yacht_free(True):
            self.warn('Летим букать 10ку', self.role)
            self.add_flag('bm10')
        
        if self.check_empty_flags():
            self.add_flag('init')
        
        self.only_first = True
        
        self.flag_do_action = False
        self.in_do_flag = False
        
        self.run_action()
    
    # Проверяем количество дронов
    def check_drones_count(self):
        drones = self.get_drones_in_bay()
        
        drones_list = {}
        
        for x in drones:
            if x.typeID in drones_list:
                drones_list[x.typeID] += x.stacksize
            else:
                drones_list[x.typeID] = x.stacksize
        
        for x in self.drones.keys():
            if x not in drones_list or self.drones[x] > drones_list[x]:
                return False
        
        return True
    
    # Устанавливаем скорость
    def set_speed(self, speed, ps=5000, mwd=True):
        pause(ps)
        
        park = sm.GetService('michelle').GetRemotePark()
        if park:
            park.CmdSetSpeedFraction(speed)
            
            shipui = uicore.layer.shipui
            
            if shipui.isopen:
                shipui.SetSpeed(speed)
                self.info('Устанавливаем максимальную скорость в {}'.format(speed), self.role)
            
            pause(3000)
        
        if mwd:
            _mwd = self.get_modules(const.groupAfterBurner)
            
            if _mwd:
                self.modules_on(_mwd)
    
    # Атака дронами
    def drones_work(self):
        if self.need_up_queue_flag or self.in_drones_work_flag or self.pen('npc_lock'):
            return
        
        targetSvc = sm.GetService('target')
        
        self.in_drones_work_flag = True
        
        drones = {}
        
        for drone in self.get_drones_in_space():
            drones[drone.droneID] = drone.targetID
        
        if not drones:
            self.in_drones_work_flag = False
            
            return
        
        drones_to_npc = {}
        
        # Исключаем залоченных дронов
        for drone_id in self.locked_drones:
            if drone_id in drones:
                del drones[drone_id]
        
        for npc_id, drone_list, bot_list in self.queue:
            if not drones:
                break
            
            if not targetSvc.IsTarget(npc_id):
                continue
            
            del_list = []
            
            for k, v in drones.items():
                if k not in drone_list:
                    continue
                
                if v == npc_id:
                    del_list.append(k)
                    
                    continue
                
                if npc_id not in drones_to_npc:
                    drones_to_npc[npc_id] = []
                
                drones_to_npc[npc_id].append(k)
                
                del_list.append(k)
            
            for k in del_list:
                del drones[k]
        
        for k, v in drones_to_npc.items():
            if not targetSvc.IsTarget(k):
                continue
            
            if k != targetSvc.GetActiveTargetID():
                do_action(2 + rnd_keys())
                
                targetSvc._SetSelected(k)
            
            self.info('Дроны атакуют {} - {}L'.format(self.get_raw_name(k), k), self.role)
            
            try:
                do_action(2 + rnd_keys(), 2 + rnd_keys())
                
                sm.GetService('menu').EngageTarget(v)
                
                self.do_pass()
                
                self.set_pen('npc_lock', 2000)
            
            except Exception as e:
                self.info('Ошибка атаки {} - {}L: {}'.format(self.get_raw_name(k), k, e), self.role)
            
            pause(500)
        
        self.in_drones_work_flag = False
    
    # Запуск дронов
    def drones_run(self):
        if self.in_drones_run:
            return
        
        self.in_drones_run = True
        
        self.send_action_info('drones_run', self.grl)
        
        drone_list = self.drones.copy()
        
        to_run = []
        
        # Количество дронов в космосе
        for k, v in self.drones.items():
            drone_list[k] -= len(self.get_drones_in_space(k))
            
            if drone_list[k] <= 0:
                del drone_list[k]
        
        # Если не все запускаем остальных
        for k, v in drone_list.items():
            drones = self.get_drones_in_bay(k)
            
            c = v
            for drone in drones:
                if c == 0:
                    break
                
                # Исключаем залоченных дронов
                if drone.itemID in self.locked_drones:
                    continue
                
                to_run.append(drone)
                c -= 1
        
        if to_run:
            do_action(5 + rnd_keys())
            
            try:
                current = Place.get_current()
                
                if current:
                    dIDs = []
                    
                    for x in to_run:
                        min_sig = 0
                        
                        if evetypes.GetVolume(x.typeID) >= 25:
                            min_sig = self.min_sig
                        
                        dIDs.append((x.itemID, (self.drones_dps[x.typeID], min_sig)))
                    
                    j_send_far('ruller', {'type': 'add_drones_space', 'site_id': current.id, 'drones': dIDs})
                    
                    sm.GetService('menu').LaunchDrones(to_run)
            except Exception as e:
                self.info('Ошибка запуска дронов: {}'.format(e), self.role)
        
        self.in_drones_run = False
    
    # Список дронов залоченых неписью
    def get_locket_drones(self, dronesIDs):
        drones = []
        
        bp = sm.GetService('michelle').GetBallpark()
        
        if bp:
            for _npc in self.get_npc():
                for k, v in _npc.modules.items():
                    target = bp.GetInvItem(v.targetID)
                    
                    if target and target.itemID in dronesIDs:
                        drones.append(v.targetID)
        
        return drones
    
    # Если дроны залочены неписью, возвращать их на корабль для сброса лока
    def drones_lockout(self):
        if self.in_drones_lockout_flag:
            return
        
        self.in_drones_lockout_flag = True
        
        # Убираем дронов из списка залоченных через 30 сек после возврата на корабль
        if self.locked_drones:
            drones_in_bay = self.get_drones_in_bay()
            
            dIDs = [(x.itemID, x) for x in drones_in_bay if x.itemID in self.locked_drones]
            
            for drone_id, drone in dIDs:
                if not self.locked_drones[drone_id]:
                    self.locked_drones[drone_id] = datetime.datetime.now()
                
                elif datetime.datetime.now() - self.locked_drones[drone_id] > datetime.timedelta(seconds=30):
                    
                    del self.locked_drones[drone_id]
        
        # Если есть залоченные дроны добавляем их в список и возвращаем на корабль
        bp = sm.GetService('michelle').GetBallpark()
        
        drones_in_space = self.get_drones_in_space()
        
        if not drones_in_space or not bp:
            self.in_drones_lockout_flag = False
            
            return
        
        dronesIDs = [x.droneID for x in drones_in_space]
        
        drones = self.get_locket_drones(dronesIDs)
        
        dronelist = []
        
        for drone in drones_in_space:
            if drone.droneID in drones and drone.activityState != const.entityDeparting and drone not in dronelist:
                dronelist.append(drone)
                self.locked_drones[drone.droneID] = None
                
                self.info('Дрон захвачен в лок, возвращаем на корабль: {}L'.format(drone.droneID), self.role)
        
        if dronelist:
            self.drones_return(dronelist, False)
        
        # Проверяем, если в космосе не достаточно дронов запускаем свежих
        max_drones = 0
        
        for v in self.drones.values():
            max_drones += v
        
        if max_drones > len(dronesIDs):
            self.drones_run()
        
        self.in_drones_lockout_flag = False
    
    # Работа с целями
    def target_work(self):
        if self.in_target_work:
            return
        
        self.in_target_work = True
        
        targetSvc = sm.GetService('target')
        
        bp = sm.GetService('michelle').GetBallpark()
        
        if not bp:
            self.in_target_work = False
            
            return
        
        godma = sm.GetService('godma')
        
        if not self.pen('npc_lock'):
            
            max_target = self.get_max_target()
            
            max_target_range = int(godma.GetItem(session.shipid).maxTargetRange)
            max_drone_distance = int(godma.GetItem(session.charid).droneControlDistance)
            
            lock_dist = min([max_target_range, max_drone_distance])
            
            queue = []
            count = 0
            
            # Строим персональную очередь
            for npc_id, drone_list, bot_list in self.queue:
                if count == max_target:
                    break
                
                if bot.login.lower() in bot_list:
                    queue.append(npc_id)
                    
                    count += 1
            
            # Сбрасываем лок с лишней неписи
            for targetID in targetSvc.targetsByID.keys():
                if targetID not in queue:
                    try:
                        do_action(2 + rnd_keys())
                        
                        self.info('Сбрасываем лок с {} - {}L'.format(self.get_raw_name(targetID), targetID), self.role)
                        targetSvc.UnlockTarget(targetID)
                        
                        pause(250)
                    except:
                        self.info('Ошибка сброса лока с {}'.format(targetID), self.role)
                        print 'Ошибка сброса лока с {}'.format(targetID)
            
            target_count = len(targetSvc.targetsByID) + len(targetSvc.targeting)
            
            # Лочим непись
            for targetID in queue:
                if target_count >= max_target:
                    break
                
                ball = bp.GetBallById(targetID)
                slim = bp.GetInvItem(targetID)
                
                if not ball or not slim or ball.surfaceDist > lock_dist:
                    continue
                
                if not targetSvc.IsTarget(targetID) and targetID not in targetSvc.targeting:
                    try:
                        do_action(2 + rnd_keys())
                        
                        self.info('Захватываем в лок {} - {}L'.format(self.get_raw_name(targetID), targetID), self.role)
                        
                        stackless.tasklet(targetSvc.TryLockTarget)(targetID)
                        
                        pause(250)
                        
                        target_count += 1
                    except:
                        self.info('Ошибка лока {}'.format(targetID), self.role)
                        print 'Ошибка лока {}'.format(targetID)
        
        self.in_target_work = False
    
    # Получаем список аномалек для крабинга
    def update_crub_places(self):
        if not self.check_in_inflight():
            return
        
        while self.in_update_crub_place and bot.macros and not self.check_in_flags('break'):
            pause(100)
        
        if not bot.macros or self.check_in_flags('break'):
            return
        
        self.in_update_crub_place = True
        
        bp = sm.GetService('michelle').GetBallpark()
        
        if bp:
            
            sensorSuite = sm.GetService('sensorSuite')
            handler = sensorSuite.siteController.GetSiteHandler(ANOMALY)
            
            sites = handler.GetSites()
            
            # Добавляем гравики
            for v in sites.values():
                if v.scanStrengthAttribute == const.attributeScanAllStrength:
                    if not Place.get_place_by_id(v.siteID):
                        if self.anomalyType in localization.GetByMessageID(v.dungeonNameID):
                            Place.add_place(CrubPlace(v.siteID, v.GetName(), v.position, v))
                            
                            if self.i_am_is_primary():
                                self.set_anomaly_status(v.siteID, self.status, name=v.GetName(), nf=True,
                                                        pos=v.position)
            
            to_del = []
            
            for k, v in cnt.places.items():
                if v.type == 'anomaly' and k not in sites:
                    to_del.append((k, v))
            
            current = Place.get_current()
            
            for k, v in to_del:
                if v.status not in ['busy', 'ended'] or current and current.id == k:
                    continue
                
                # Place.del_place(k)
                
                if self.i_am_is_primary(group=self.grl):
                    self.set_anomaly_status(k, 'deleted')
            
            bms = _bm.get_bookmarks('Places')
            names = [x.name for x in cnt.places.values()]
            
            for bm in bms:
                if bm.memo.strip() not in names:
                    _bm.del_bookmark(bm.memo.strip(), 'Places')
            
            if self.busy_only_first:
                self.status = 'free'
        
        self.in_update_crub_place = False
    
    # Получаем текущую или следующую аномальку
    def get_crub_place(self, lock=False):
        res = self.get_free_anomaly(self.grl, lock)
        
        if res != 'error' and res['site_id']:
            site_id = res['site_id']
            status = res['status']
            
            place = Place.get_place_by_id(site_id)
            
            if place:
                return place, status
            
            else:
                self.set_anomaly_status(site_id, 'deleted')
        
        return None, None
    
    # Ожидание свободной аномали
    def wait_free_anomaly(self):
        
        while bot.macros and self.check_in_flags('init'):
            
            if self.check_in_flags(['gopos', 'enemy', 'panic', 'wait', 'break']):
                self.del_flag('init')
                
                break
            
            if sm.GetService('autoPilot').InWarp():
                pause(1000)
                continue
            
            r = get_random(1000, 20000)
            
            if not self.act_is_ready('send_num_anomaly', add_time=self.add_time + r, gr=self.grl):
                pause(1500)
                continue
            
            place, status = self.get_crub_place()
            
            if place and status:
                self.run_action()
                
                break
            
            pause(15000)
    
    # Получить статус аномали
    def get_anomaly_status(self, siteID, who=None):
        
        rec = {'type': 'get_anomaly_status', 'site_id': siteID, 'who': who}
        
        status = j_get_far('ruller', rec)
        
        place = Place.get_place_by_id(siteID)
        
        if place and status != 'error':
            place.status = status
        
        return status
    
    # Установить статус аномали
    def set_anomaly_status(self, siteID, status='busy', who=None, name=None, nf=False, pos=(0, 0, 0)):
        
        place = Place.get_place_by_id(siteID)
        
        if place:
            place.status = status
        
        rec = {'type': 'set_anomaly_status',
               'site_id': siteID,
               'status': status,
               'who': who,
               'name': name,
               'nf': nf,
               'pos': pos}
        
        j_send_far('ruller', rec)
    
    def get_free_anomaly(self, who=None, lock=False, pre=False):
        bp = sm.GetService('michelle').GetBallpark()
        
        pos = None
        
        if bp:
            ship = bp.GetBallById(util.GetActiveShip())
            
            if ship:
                pos = (ship.x, ship.y, ship.z)
        
        rec = {'type': 'get_free_anomaly', 'who': who, 'lock': lock, 'pre': pre, 'pos': pos}
        
        return j_get_far('ruller', rec)
    
    def set_send_status(self, siteID):
        
        j_send_far('ruller', {'type': 'set_send_status', 'site_id': siteID})
    
    def get_send_status(self, siteID):
        
        return bool(j_get_far('ruller', {'type': 'get_send_status', 'site_id': siteID}))
    
    # Демаг наносимый активными дронами
    def get_drones_dmg(self):
        dogmaLocation = sm.GetService('clientDogmaIM').GetDogmaLocation()
        
        return dogmaLocation.GetOptimalDroneDamage(util.GetActiveShip())[0]
    
    # По прилету на аномаль проверяем не занята ли она
    def anomaly_is_busy(self):
        current = Place.get_current()
        
        if current:
            bp = sm.GetService('michelle').GetBallpark()
            
            if not bp:
                return False
            
            j_owns = [x['id'] for x in bot.bots.values()] + [session.charid]
            
            for ball_id, ball in bp.balls.items():
                
                slim = bp.GetInvItem(ball_id)
                
                if slim:
                    # if slim.categoryID == 6 or slim.groupID in const.containerGroupIDs:
                    if slim.categoryID == 6:
                        if slim.ownerID not in j_owns:
                            self.info('Чужой элемент {}: {}'.format(evetypes.GetName(slim.typeID),
                                                                    slim.itemID), self.role)
                            
                            return True
        
        return False
    
    # Проверяем закончено ли выполнение аномали
    def anomaly_is_ended(self):
        current = Place.get_current()
        
        is_ended = True
        
        if current:
            bp = sm.GetService('michelle').GetBallpark()
            
            if not bp:
                return
            
            sensorSuite = sm.GetService('sensorSuite')
            handler = sensorSuite.siteController.GetSiteHandler(ANOMALY)
            
            for v in handler.GetSites().values():
                if v.scanStrengthAttribute == const.attributeScanAllStrength:
                    if self.anomalyType in localization.GetByMessageID(v.dungeonNameID):
                        if v.GetName() == current.name:
                            is_ended = False
                            break
            
            pirates = self.get_npc_pirates()
            
            if is_ended:
                for ball_id, ball in bp.balls.items():
                    
                    slim = bp.GetInvItem(ball_id)
                    
                    if slim and slim.groupID in pirates:
                        is_ended = False
                        break
        
        return is_ended
    
    def wait(self):
        self.pause_pass()
        
        stackless.tasklet(self.protect_mod_off)()
        
        self.modules_off(self.get_modules(407))
        self.modules_off(self.get_modules(const.groupElectronicCounterMeasureBurst))
        self.modules_off(self.get_modules(646))
        
        Oldspace.wait(self)
    
    def set_ball_pos(self, site_id):
        if datetime.datetime.now() - self.last_set_coord < datetime.timedelta(seconds=1):
            return
        
        self.last_set_coord = datetime.datetime.now()
        
        bp = sm.GetService('michelle').GetBallpark()
        
        if not bp:
            return
        
        npc_list = {}
        drone_list = {}
        
        j_owns = [x['id'] for x in bot.bots.values()] + [session.charid]
        
        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)
            
            if slim:
                if slim.groupID in self.get_npc_pirates() or slim.groupID == const.groupDestructibleSentryGun:
                    npc_list[ball_id] = (ball.x, ball.y, ball.z)
                
                elif slim.groupID == 100 and slim.ownerID in j_owns:
                    drone_list[ball_id] = (ball.x, ball.y, ball.z)
        
        if npc_list or drone_list:
            rec = {'type': 'set_ball_pos', 'site_id': site_id, 'npc': npc_list, 'drone': drone_list}
            
            j_send_far('ruller', rec)
    
    def add_to_space(self, slims):
        current = Place.get_current()
        
        if not current:
            return
        
        self.set_pen('npc_lock', 1000)  # 2
        
        npc_list = []
        drone_list = []
        j_owns = [x['id'] for x in bot.bots.values()] + [session.charid]
        
        for slim in slims:
            # Непись
            if slim.groupID in self.get_npc_pirates() or slim.groupID == const.groupDestructibleSentryGun:
                npc_info = self.get_npc_info(slim.typeID, slim.groupID)
                
                npc_name = evetypes.GetName(slim.typeID)
                self.info('Добавляем нпц {} - {}L'.format(npc_name, slim.itemID), self.role)
                
                npc_list.append((slim.itemID, npc_info))
            
            # Дроны
            elif slim.groupID in [100, 549] and slim.ownerID == session.charid:
                drone_name = evetypes.GetName(slim.typeID)
                self.info('Запустили дрона {} - {}L'.format(drone_name, slim.itemID), self.role)
                
                min_sig = 0
                
                if evetypes.GetVolume(slim.typeID) >= 25:
                    min_sig = self.min_sig
                
                drone_list.append((slim.itemID, (self.drones_dps[slim.typeID], min_sig)))
            
            # Чужие корабли
            elif slim.categoryID == 6 and slim.ownerID not in j_owns:
                if not self.other_ship:
                    self.other_ship = True
                    
                    self.warn('Чужой корабль в гриде', self.role)
        
        if npc_list:
            rec = {'type': 'add_npc', 'site_id': current.id, 'npc_list': npc_list}
            
            j_send_far('ruller', rec)
        
        if drone_list:
            j_send_far('ruller', {'type': 'add_drones_space', 'site_id': current.id, 'drones': drone_list})
        
        # Отправляем координаты неписи и дронов
        # if npc_list or drone_list:
        #     if self.i_am_is_primary(group=self.grl, place=current.id):
        #         self.set_ball_pos(current.id)
        
        self.import_npc_flag = True
    
    def del_from_space(self, slims):
        if not sm.GetService('autoPilot').InWarp():
            current = Place.get_current()
            
            if not current:
                return
            
            npc_list = []
            drone_list = []
            
            for slim in slims:
                # Непись
                if slim.groupID in self.get_npc_pirates() or slim.groupID == const.groupDestructibleSentryGun:
                    npc_name = evetypes.GetName(slim.typeID)
                    self.info('Удаляем нпц {} - {}L'.format(npc_name, slim.itemID), self.role)
                    
                    npc_list.append(slim.itemID)
                
                # Дроны
                elif slim.groupID in [100, 549] and slim.ownerID == session.charid:
                    drone_name = evetypes.GetName(slim.typeID)
                    self.info('Вернули дрона {} - {}L'.format(drone_name, slim.itemID), self.role)
                    
                    drone_list.append(slim.itemID)
            
            if npc_list:
                self._del_npcs(current.id, npc_list)
                
                self.set_pen('npc_lock', 2000)
            
            if drone_list:
                j_send_far('ruller', {'type': 'del_drones_space', 'site_id': current.id, 'drones': drone_list})
                
                # Отправляем координаты неписи и дронов
                # if npc_list or drone_list:
                #     if self.i_am_is_primary(group=self.grl, place=current.id):
                #         self.set_ball_pos(current.id)
    
    def _del_npcs(self, site_id, npc_list):
        rec = {'type': 'del_npc', 'site_id': site_id, 'npc_list': npc_list}
        
        j_send_far('ruller', rec)
    
    def update_npc_queue(self):
        current = Place.get_current()
        bp = sm.GetService('michelle').GetBallpark()
        
        if current and bp:
            rec = {'type': 'get_npc_queue', 'site_id': current.id}
            
            queue = j_get_far('ruller', rec)
            
            if queue == 'error':
                self.queue = []
            else:
                self.queue = queue
            
            self.set_pen('npc_lock', 1000)
            
            self.need_up_queue_flag = False
    
    # Информация по неписи
    def get_npc_info(self, type_id, group_id):
        h = get_type_attr(type_id, const.attributeHp)  # Структура
        a = get_type_attr(type_id, const.attributeArmorHP)  # Броня
        s = get_type_attr(type_id, const.attributeShieldCapacity)  # Щит
        
        ra = 2 - get_type_attr(type_id, getattr(const, 'attributeArmor{}DamageResonance'.format(self.primaryDamage)))
        rs = 2 - get_type_attr(type_id, getattr(const, 'attributeShield{}DamageResonance'.format(self.primaryDamage)))
        
        ret = {'ehp': h + a * ra + s * rs}
        
        arr = {
            'scramble': 504, 'webfier': 512, 'jam': 930, 'disrupt': 933, 'nosferatu': 931, 'damper': 932,
            'sig': 552
        }
        
        sba = get_type_attr(type_id, const.attributeEntityShieldBoostAmount)
        
        if sba:
            ret['ehp'] *= 5
        
        for k, v in arr.items():
            ret[k] = get_type_attr(type_id, v)
        
        ret['sentry'] = group_id == const.groupDestructibleSentryGun
        ret['name'] = evetypes.GetName(type_id)
        
        return ret
    
    def wreck_in_space(self):
        bp = sm.GetService('michelle').GetBallpark()
        
        if not bp:
            return True
        
        for ball_id, ball in bp.balls.items():
            
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.groupID == const.groupWreck and not slim.isEmpty:
                return True
    
    def need_repair(self):
        if self.tank_type == 'shield':
            full = self.get_shield()
            curr = self.get_shield(False)
            
            delta = curr < full * 0.20
        
        else:
            full = self.get_armor()
            curr = self.get_armor(False)
            
            delta = full - curr < full * 0.20
        
        # TODO: Минимальный процент щита вынести в настройки
        if delta and not self.check_in_flags('damaged'):
            self.warn('Критический заряд, варпаем на ремонт', self.role)
            self.add_flag('damaged')
            
            self.run_action()
            
            return True
        
        return
    
    def current_repair(self):
        
        if self.current_repair_flag or self.pen('current_repair'):
            return
        
        self.current_repair_flag = True
        
        if self.tank_type == 'shield':
            shield_boosters = self.get_modules(const.groupShieldBooster)
            
            if shield_boosters:
                full = self.get_shield()
                curr = self.get_shield(False)
                
                if full - curr >= full * 0.99:  # or home and home.surfaceDist < cnt.gridDistance:
                    self.modules_off(shield_boosters)
                else:
                    self.modules_on(shield_boosters)
        
        elif self.tank_type == 'armor':
            armor_repairs = self.get_modules(const.groupArmorRepairUnit)
            
            if armor_repairs:
                full = self.get_armor()
                curr = self.get_armor(False)
                
                if full - curr >= full * 0.90:
                    self.modules_off(armor_repairs)
                else:
                    self.modules_on(armor_repairs)
        
        self.set_pen('current_repair', 2000)
        
        self.current_repair_flag = False
    
    def del_place_bms(self, place_name):
        bm_in = _bm.get_bookmark(place_name, 'Places')
        
        if bm_in:
            _bm.del_bookmark(place_name, 'Places')
    
    # Уведомление о необходимости обновить очередь неписи
    def j_notification(self, login, data):
        if not self.is_ready: return
        
        Oldspace.j_notification(self, login, data)
        
        if data['func'] == 'update_npc_queue':
            self.need_up_queue_flag = True
        
        elif data['func'] == 'change_pre':
            stackless.tasklet(self.change_pre)(data['args'])
    
    # Сменилась следующая потенциальная аномалька, перечитать
    def change_pre(self, grl):
        if self.align_to_pre_flag and grl == self.grl:
            if self.check_empty_flags() and not self.anomaly_is_ended():
                self.align_to_pre()
    
    def align_to_pre(self, speed=None):
        pre = self.get_free_anomaly(self.grl, pre=True)
        
        if pre != 'error' and pre['site_id']:
            place = Place.get_place_by_id(pre['site_id'])
            
            if place:
                self.info('Разгоняемся на потенциальную аномальку {}'.format(place.name), self.role)
                
                self.align(place, False)
                
                if speed:
                    stackless.tasklet(self.set_speed)(speed, 1000, False)
    
    def clean_exp(self):
        query = "DELETE FROM eve_exp WHERE e_time < %s AND char_id = %s"
        db_query(query, (util.BlueToDate(blue.os.GetWallclockTime()), session.charid))
    
    def bm10(self):
        self.del_flag('bm10')
        
        if self.last_flag:
            self.add_flag('topos')
        
        bot.change_args = {
            'ship_id': session.shipid,
            'flags': self.flags
        }
        
        bot.change_role('bm10')
    
    def update_exp(self):
        query = "SELECT exp_id FROM eve_exp WHERE char_id = %s"
        rec = db_select(query, (session.charid,))
        
        if rec:
            rec = [x[0] for x in rec]
        
        svc = sm.GetService('journal')
        
        exps = svc.GetExpeditions()
        
        allow_exp = self.s.gan('AllowExp', '')
        
        for exp in exps.lines:
            instanceID = exp[0]
            
            if instanceID in rec:
                continue
            
            dungeon = exp[1]
            destDungeon = exp[3]
            expiryTime = exp[5]
            
            sys_name = cfg.evelocations.Get(dungeon['solarSystemID']).name[:-1]
            
            if sys_name not in allow_exp:
                continue
            
            query = "INSERT INTO eve_exp"
            query += "(char_id, exp_id, s_time, e_time, system_id, status, archetype, dungeon, difficulty)"
            query += "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            
            db_query(query, (session.charid,
                             instanceID,
                             util.BlueToDate(dungeon['creationTime']),
                             util.BlueToDate(expiryTime),
                             dungeon['solarSystemID'],
                             0,
                             destDungeon['archetypeID'],
                             destDungeon['dungeonID'],
                             destDungeon['difficulty']))
    
    def get_yacht_free(self, lock=True):
        rec = {'type': 'get_yacht_status', 'lock': lock}
        
        status = j_get_far('ruller', rec)
        
        if status != 'error':
            return status
        
        return False
    
    def get_exp_count(self):
        query = 'SELECT COUNT(*) FROM eve_exp '
        query += 'WHERE char_id = %s AND status < 4'
        
        ans = db_select(query, (session.charid,))
        
        if ans and ans != 'error':
            return ans[0][0]
        
        return 0
    
    def _OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args):
        if not self.i_am_is_primary():
            return
        
        if session.solarsystemid in self.chList:
            if isinstance(channelID, types.IntType) and channelID == self.chList[session.solarsystemid2]:
                
                j_owns = [x['id'] for x in bot.bots.values()] + [session.charid]
                
                if method == 'SendMessage':
                    res = args[0]
                    
                    p = re.compile(r'(\d{3})')
                    res = p.findall(res)
                    
                    for r in res:
                        for site_id in Place.get_ids_by_sn(r):
                            
                            place = Place.get_place_by_id(site_id)
                            
                            if place:
                                if identityInfo[2][0] not in j_owns:
                                    status = self.get_anomaly_status(place.id)
                                    
                                    if status in ['free', 'pre', 'pre_alien']:
                                        self.set_anomaly_status(place.id, 'busy')
                                
                                elif self.i_am_is_primary(group=self.grl) and identityInfo[2][0] == session.charid:
                                    self.set_send_status(place.id)
    
    def OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args):
        Oldspace.OnLSC(self, channelID, estimatedMemberCount, method, identityInfo, args)
        
        if not self.is_ready: return
        
        stackless.tasklet(self._OnLSC)(channelID, estimatedMemberCount, method, identityInfo, args)
    
    def DoBallsAdded(self, balls_slimItems, *args, **kw):
        if not self.is_ready: return
        
        stackless.tasklet(self.add_to_space)([x[1] for x in balls_slimItems])
    
    def DoBallRemove(self, ball, slimItem, terminal):
        if not self.is_ready: return
        
        stackless.tasklet(self.del_from_space)([slimItem])
    
    def DoBallsRemove(self, pythonBalls, isRelease):
        if not self.is_ready: return
        
        stackless.tasklet(self.del_from_space)([x[1] for x in pythonBalls])
    
    def OnEwarEndFromTactical(self, doAnimate=True, *args):
        if not self.is_ready: return
        
        if (self.check_enemy_in_local() or self.flags) and not self.check_scrambler():
            self.run_action()
    
    def OnWindowOpened(self, wnd):
        if wnd.__guid__ == 'form.Telecom':
            caption = wnd.FindChild('EveCaptionMedium').text.encode('utf-8')
            
            if 'Развивающийся улей восставших дронов' in caption:
                self.warn('Выпала 10ка', self.role)
                
                self.update_exp()
        
        Oldspace.OnWindowOpened(self, wnd)
    
    def OnGoWork(self):
        if not self.is_ready: return
        
        if self.last_flag:
            self.last_flag = False
        
        if not self.check_in_flags('init'):
            self.add_flag('init')
        
        Oldspace.OnGoWork(self)
    
    def OnSignalTrackerAnomalyUpdate(self, solarSystemID, addedAnomalies, removedAnomalies):
        if not self.is_ready: return
        
        stackless.tasklet(self.update_crub_places)()
    
    def OnDamageStateChange(self, shipID, damageState):
        if not self.is_ready: return
        
        if session.shipid == shipID:
            # Ремонтируем щит или броню
            stackless.tasklet(self.current_repair)()
