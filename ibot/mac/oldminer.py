import copy
from datetime import datetime as dt

import evetypes
import invCtrl
import stackless
import util
from eve.client.script.ui.services.menuSvcExtras import invItemFunctions

import ibot.utils.bms as _bm
import ibot.utils.note as _note
import ibot.utils.repl as repl
from ibot.mac.template.mine import Mine
from ibot.utils import pickle
from ibot.utils.places import *


def run():
    if not bot.macros:
        bot.macros = Miner()


class Miner(Mine):
    __notifyevents__ = [
        'OnEveMessage',
        'DoBallsAdded',
        'DoBallRemove',
        'DoBallsRemove',
        'OnDamageStateChange',
        'UnlockTarget'
    ]

    # TODO: Ловить окно, когда руда не входит в конт
    # TODO: Выкидывать конт с задержкой
    # TODO:

    # TODO: Автоповтор модулей

    # TODO: Использовать группы
    # TODO: Предусмотреть реакцию на разрыв соединения
    # TODO: Перефичивать корабли в зависимости от цели майнинга
    # TODO: Если нейтрал заджамил натравливать на него EM-300 дронов
    # TODO: Запретить одновременное подключение одним логином, контроль джа
    # TODO: Добавить функционал say_role, для трансляции команд ботам
    # TODO: Отключать автоматическую перезарядку кристалов
    # TODO: Перехватывать Say и писать в лог
    # TODO: Подумать как вылетать из облака меркоцита

    # Инициализация класса
    def __init__(self, _run=True):
        self.actions = {
            'dig': {
                'co': [
                    lambda: self.check_empty_flags(),
                    lambda: not self.check_enemy_in_local()
                ],
                'po': self.get_dig_place,
                'go': self.go,
                'do': self.dig,
                'tm': None,
                'iv': 1000,
                'ed': self.end_dig
            },
            'need_crystall': {
                'co': [
                    lambda: self.check_in_flags('need_crystall')
                ],
                'po': lambda: self.get_place_by_bm(_bm.get_bookmark('POS')),
                'go': self.go,
                'do': self.load_crystals,
                'pr': 10
            },
            'unload_res': {
                'co': [
                    lambda: self.check_in_flags('full_cargo')
                ],
                'po': self.get_home,
                'go': self.go,
                'do': self.unload_res
            }

        }

        bot.log.info('Запускаем макрос')

        Mine.__init__(self, 'miner')

        self.actions['wait']['co'] += [lambda: not self.get_drones_in_space() or not self.grid_is_safety()]
        self.actions['hide']['co'] += [lambda: not self.get_drones_in_space() or not self.grid_is_safety()]

        self.add_flag('init')

        # Список ресурсов для добычи
        self.res = self.unpack_groups(load_set_list(self.s.ga('ResourcesList', None)))

        if not self.res:
            self.warn('Не задан список ресурсов', self.role)

            self.OnScriptBreak()

            return

        # Настройки
        self.oreConsistent = bool(self.s.ga('OreConsistent', False))
        self.unloadToCargo = bool(self.s.ga('UnloadToCargo', True))
        self.arrayName = self.s.ga('ArrayName', '')
        self.divName = self.s.ga('DivName', '')
        self.divNameS = self.s.ga('DivNameS', '')
        self.mineBusy = bool(self.s.ga('MineBusy', False))

        # fits = {
        # 'ore': 'Hulk Ore Dig',
        # 'ice': 'Hulk Ice Dig'
        # }

        # self.fit_name = fits.get(self.get_type_resource())

        self.in_do_flag = False
        self.first_dig = True
        self.guard_jets = False
        self.in_jet_flag = False
        self.shield_flag = False
        self.in_ren_jet = False

        self.apr_ball = None

        self.prim_target = None

        self.last_view_col = dt.now()

        self.npc = []

        self.bot_actions = {}
        self.bot_order = {}

        self.skip_belts = []
        self.only_belts = []

        self.load_so_list('SkipBelts', self.skip_belts)
        self.load_so_list('OnlyBelts', self.only_belts)

        self.is_ready = True

        self.info('Макрос запущен', self.role)

        # Складываем необходимые кристалы
        if session.stationid:
            self.split_drones()
            self.repair_ship()

            # self.check_fit()

        self.OnDownTime()

        pause(1000)

        if not self.check_in_flags('downtime'):
            self.run_action()

            set_bot_params('role', self.role)

    # region Функции

    # Распаковка групп ресурсов в их типы
    def unpack_groups(self, res_list):

        if not isinstance(res_list, list):
            res_list = [res_list]

        res = []

        gs = cnt.groupsOre + cnt.groupsMercoxit
        ts = cnt.typesOre + cnt.typesMercoxit + cnt.typesIce

        for r in res_list:
            if r in gs:
                for oid in ts:
                    if evetypes.GetGroupID(oid) == r:
                        res.append(oid)

            elif r in ts:
                res.append(r)

        return res

    # Упаковка типов ресурсов в группы
    def pack_groups(self, res_list):

        if not isinstance(res_list, list):
            res_list = [res_list]

        res = []

        gs = cnt.groupsOre + cnt.groupsMercoxit
        ts = cnt.typesOre + cnt.typesMercoxit + cnt.typesIce

        for r in res_list:
            if r in ts:
                if evetypes.GetGroupID(r) not in res:
                    res.append(evetypes.GetGroupID(r))

            elif r in gs:
                if r not in res:
                    res.append(r)
        return res

    # Получить тип добываемого ресурса
    def get_type_resource(self):
        if self.res:

            if self.res[0] in cnt.allOre:
                return 'ore'
            elif self.res[0] in cnt.allIce:
                return 'ice'

        return None

    # Получить место для копки
    def get_dig_place(self):
        res_type = self.get_type_resource()

        # if dt.now() - get_last_dt() < datetime.timedelta(hours=12) or res_type == 'ice':
        if res_type == 'ore':
            groups = cnt.groupGravics
        else:
            groups = cnt.groupIce

        for group in groups:
            for place in cnt.places.values():
                if self.only_belts:
                    if place.name in self.only_belts and not self.place_is_empty(place.name):
                        return place

                    continue

                if place.name in self.skip_belts:
                    continue

                if place.type == 'anomaly' and place.dungeonNameID == group and not self.place_is_empty(place.name):
                    return place

        if res_type != 'ore':
            return None

        current = Place.get_current()

        belts = []

        for place in cnt.places.values():
            if self.only_belts:
                if place.name in self.only_belts and not self.place_is_empty(place.name):
                    return place

                continue

            if place.name in self.skip_belts:
                continue

            if place.type == 'belt' and not self.place_is_empty(place.name):
                if current and current.id == place.id:
                    return place
                else:
                    belts.append((place.name, place))

        if belts:
            belts.sort()

            return belts[0][1]

        return None

    # Проверяем есть ли в указаном месте руда и не занято ли оно, возвращает False если копать можно
    def place_is_empty(self, name):

        do_action(5 + rnd_keys())

        note = _note.get_note_by_name(name, 'Places')

        if note:
            all_lines = self.get_res_string().split('<br>')

            text = note.text.split('<br>')

            for line in all_lines:
                if line not in text:
                    return False
        else:
            return False

        return True

    # Преобразовываем типы и группы в имена русурсов
    def get_res_string(self):
        res = []

        for r in self.res:
            res.append(evetypes.GetName(r))

        return '<br>'.join(res)

    # Выбираем астероиды, in_lock - включать залоченные, in_target - включать уже добываемые
    def get_point_aster(self, in_lock=True, in_target=True):
        bp = sm.GetService('michelle').GetBallpark(True)
        targetSvc = sm.GetService('target')

        if not bp:
            return None

        if self.oreConsistent:
            asters = {}
        else:
            asters = []

        if self.mineBusy:
            busy = []
        else:
            busy = self.get_busy_asters()

        targetIDs = [self.get_target_id(x) for x in self.get_modules(cnt.groupMiningLasers)]

        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)

            if slim and slim.typeID in self.res and slim.itemID not in busy:

                if not in_lock:
                    # Пропускаем, если астероид уже залочен или лочится
                    if targetSvc.IsTarget(ball_id) or ball_id in targetSvc.GetTargeting():
                        continue

                if not in_target:
                    # Пропускаем, если астероид уже добывается
                    if ball_id in targetIDs:
                        continue

                primary = None

                if not self.i_am_is_primary():
                    primary = self.get_primary_ship(True)

                if primary:
                    dist = bp.GetSurfaceDist(primary.id, ball_id)
                else:
                    dist = ball.surfaceDist

                if self.oreConsistent:
                    if slim.typeID not in asters:
                        asters[slim.typeID] = []

                    asters[slim.typeID].append((dist, ball))
                else:
                    asters.append((dist, ball))

        # Последовательная добыча, т.е. пока не выкапается один тип руды к другой не преступать
        if self.oreConsistent:
            for r in self.res:
                if r in asters:
                    asters[r].sort()

                    return asters[r][0][1]

        # Параллельная добыча, добывается ближайший тип руды
        elif asters:
            asters.sort()

            return asters[0][1]

        return None

    # Список астероидов копаемых другими игроками
    def get_busy_asters(self):
        bp = sm.GetService('michelle').GetBallpark()
        targetSvc = sm.GetService('target')

        busy = []
        botIDs = []

        if not bp:
            return busy

        for v in bot.bots.values():
            botIDs.append(v['id'])

        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)

            if slim and slim.categoryID == 6 and slim.itemID != session.shipid and slim.ownerID not in botIDs:
                for k, v in ball.modules.items():
                    target = bp.GetInvItem(v.targetID)

                    if target and target.typeID in self.res and v.IsShooting():
                        if not targetSvc.IsTarget(v.targetID) and v.targetID not in targetSvc.GetTargeting():
                            busy.append(v.targetID)

        return busy

    # Получаем количество залоченых или лочащихся астероидов
    def get_locking_asters(self):
        bp = sm.GetService('michelle').GetBallpark(True)
        targetSvc = sm.GetService('target')

        t_count = 0

        # Считаем количетсво залоченых или лочащихся астероидов
        for targetID in targetSvc.targetsByID.keys() + targetSvc.targeting.keys():
            slim = bp.GetInvItem(targetID)

            if slim and slim.categoryID == const.categoryAsteroid:
                t_count += 1

        return t_count

    # Количество лазеров добывающих указанный астероид
    def get_laser_on_aster(self, lasers, aid):
        return len([x for x in lasers if self.get_target_id(x) == aid])

    # Получить тип руды для установленного кристала
    def get_crystal_ore(self, item):
        if item.groupID in [482, 663]:  # Mining Crystal
            return int(get_type_attr(item.typeID, const.attributeSpecialisationAsteroidGroup))

        return None

    # Список дронов в космосе
    def get_drones_in_space(self, _type=None):
        bp = sm.GetService('michelle').GetBallpark(True)

        if not bp:
            return []

        res = []

        drones = sm.GetService('michelle').GetDrones()

        for droneID in drones:
            if droneID in bp.slimItems and \
                    (drones[droneID].ownerID == session.charid or drones[droneID].controllerID == session.shipid):

                if _type:
                    if drones[droneID].typeID in cnt.typesDrone[_type]:
                        res.append(drones[droneID])
                else:
                    res.append(drones[droneID])

        return res

    # Список дронов в дронбее
    def get_drones_in_bay(self, _type=None):
        invCache = sm.GetService('invCache')

        drones = invCache.GetInventoryFromId(util.GetActiveShip()).ListDroneBay()

        if not _type:
            return drones

        res = []

        for drone in drones:
            if drone.typeID in cnt.typesDrone[_type]:
                res.append(drone)

        return res

    # Количество доступных дронов для запуска и свободная полоса управления дронами
    def get_free_drone(self):
        drones = self.get_drones_in_space()

        bandwith = 0

        for drone in drones:
            bandwith += int(get_type_attr(drone.typeID, const.attributeDroneBandwidthUsed))

        godma = sm.GetService('godma')

        max_drones = int(godma.GetItem(session.charid).maxActiveDrones)
        max_bandwidth = int(godma.GetItem(session.shipid).droneBandwidth)

        return max_drones - len(drones), max_bandwidth - bandwith

    # Получить самый дальний корабль бота, если он дальше 7500 км
    def get_primary_ship(self, always=False):
        bp = sm.GetService('michelle').GetBallpark(True)

        if not bp:
            return

        primary = self.get_primary()

        if primary:
            for ball_id, ball in bp.balls.items():
                slim = bp.GetInvItem(ball_id)

                if slim and slim.categoryID == 6 and slim.ownerID == primary['id']:
                    if always:
                        return ball

                    if ball.surfaceDist > 7500:
                        return ball

                    return

        return

    # Если боты в гриде с работающими модулями
    def work_in_space(self):
        bp = sm.GetService('michelle').GetBallpark()

        if not bp:
            return False

        botIDs = [x['id'] for x in bot.bots.values()]

        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)

            if slim and slim.categoryID == 6 and slim.ownerID in botIDs:
                for k, v in ball.modules.items():
                    target = bp.GetInvItem(v.targetID)

                    if target and target.typeID in self.res and v.IsShooting():
                        return True

        return False

    # Есть ли дроны возвращающиеся на корабль, если есть то в космос дроны запускаться не будут
    def is_departing(self, drones):
        for drone in drones:
            if drone.activityState == const.entityDeparting:
                return True

        return False

    # Размер сигнатуры дронов, которую непись будет игнорировать
    def get_min_sig(self):
        minSig = None
        bp = sm.GetService('michelle').GetBallpark(True)

        if not bp:
            return 0

        for npc in self.get_npc():
            slim = bp.GetInvItem(npc.id)

            sig = get_type_attr(slim.typeID, 1855)  # AI_IgnoreDronesBelowSignatureRadius

            if not minSig or minSig > sig:
                minSig = sig

        return minSig

    def load_so_list(self, list_name, _list):
        tmp_list = self.s.ga(list_name, None)

        if tmp_list:
            tmp_list = tmp_list.split(',')

            for item in tmp_list:
                self.add_item_list(_list, item)

    def add_item_list(self, _list, _item):
        if _item not in _list:
            _list.append(_item)

    def del_item_list(self, _list, _item):
        if _item in _list:
            _list.remove(_item)

    # endregion

    # region Методы

    # Метод добычи астероидов
    def dig(self):
        if self.in_do_flag or self.flags:
            return

        # Если варпнул руками
        if sm.GetService('autoPilot').InWarp():
            self.main_action = None
            self.actions['dig']['tm'] = None

            return

        self.in_do_flag = True
        # skip_aproach = False

        if self.first_dig:
            self.first_dig = False
            self.guard_jets = False

            # skip_aproach = True

        stackless.tasklet(self.protect_mod_on)()
        stackless.tasklet(self.repair_shield)()

        collectors = self.get_bots_by_role('collector')

        # Если коллектор отсутствует более 5 минут в онлайне, варпаем на пос
        if collectors:
            for col in collectors:
                if sm.GetService('onlineStatus').GetOnlineStatus(col['id'], True):
                    self.last_view_col = dt.now()
                    break

        elif dt.now() - self.last_view_col > datetime.timedelta(minutes=5):
            self.add_flag('topos')

            self.warn('Коллектор не обранужен, варпаем на ПОС', self.role)

            self.run_action()

            return

        # Ближайший астероид
        aster = self.get_point_aster()

        # Если астероиды в текущем месте закончились
        if not aster:
            # Охраняем контейнеры
            if self.jets_in_space() or self.work_in_space():
                self.drones_work()

                if not self.guard_jets:
                    self.info('Охраняем джеты', self.role)

                    rec = {'type': 'notification', 'func': 'collect'}
                    send_to_role('?{}'.format(pickle.dumps(rec)), 'collector')

                    self.guard_jets = True

                self.in_do_flag = False
                return

            else:
                if self.pen('jet_guard'):
                    self.in_do_flag = False
                    return

                place = Place.get_current()

                self.info('Астероиды в текущем месте не обнаружены', self.role)

                if place:
                    self.info('Помечаем {} как пустой'.format(place.name), self.role)

                    _s = '<br>'.join([str(dt.now().replace(microsecond=0)), self.get_res_string()])
                    _note.add_note(place.name, _s, 'Places')

                else:
                    self.info('Не удалось получить текущее место', self.role)

                if not self.get_dig_place():
                    self.warn('Выбранная руда в системе закончилась', self.role)

                    self.add_flag('topos')

                self.run_action()

                return

        place = Place.get_current()

        if not place:
            self.warn('Не удалось определить текущее положение, варпаем на пос', self.role)

            self.add_flag('topos')
            self.run_action()

            return

        # Основные действия --------------------------------------------------------------------------------------------

        bp = sm.GetService('michelle').GetBallpark()
        if not bp:
            self.in_do_flag = False
            return

        ship = bp.GetBallById(util.GetActiveShip())

        chk_primary = False

        if self.i_am_is_primary('miner'):
            chk_primary = True

        else:
            primary_ship = self.get_primary_ship(True)

            if primary_ship:
                chk_primary = True

                if primary_ship.id != ship.followId and primary_ship.surfaceDist > 7500:
                    self.aproach_to(primary_ship, 7500)
                    self.apr_ball = None

                elif primary_ship.id == ship.followId and primary_ship.surfaceDist <= 7500:
                    self.aproach_to(primary_ship, 7500)

        if chk_primary:
            if self.i_am_is_primary('miner') or not self.get_primary_ship():

                targetSvc = sm.GetService('target')
                godma = sm.GetService('godma')

                lasers = self.get_modules(cnt.groupMiningLasers)

                max_targets = min([len(lasers), self.get_max_target() - 1])
                cur_targets = 0

                # Считаем количество залоченных или лочащихся астероидов
                for targetID in targetSvc.targetsByID.keys() + targetSvc.targeting.keys():
                    _slim = bp.GetInvItem(targetID)

                    if _slim and _slim.categoryID == const.categoryAsteroid:
                        cur_targets += 1

                # Максимальня дистанция действия лазеров
                max_range = min([int(godma.GetItem(x.sr.moduleInfo.itemID).maxRange) for x in lasers]) * 0.9
                aproach_range = int(max_range)

                slim = bp.GetInvItem(aster.id)

                # Если копаем лед или меркоцит дистанция максимальная иначе берем из настроек
                # if slim and slim.typeID not in cnt.typesIce + self.unpack_groups(cnt.groupsMercoxit) and self.apr_ball:
                #     aproach_range = int(self.s.ga('OreDistRange', max_range))

                # Лочим астероиды, если залоченых и лочащихся астероидов меньше максимального количества целей
                if cur_targets < max_targets and not self.pen('lock_aster'):

                    # Выбираем еще не залоченный, ближайший астероид
                    lock = self.get_point_aster(False)

                    # Если астероид находится в пределах действия лазеров, лочим его
                    if lock and lock.surfaceDist < max_range:
                        try:
                            self.info('Лочим астероид - {} ({})'.format(self.get_raw_name(lock.id), lock.id), self.role)

                            do_action(2 + rnd_keys())

                            sm.GetService('target').TryLockTarget(lock.id)
                        except:
                            self.info('Ошибка лока астероида - {} ({})'.format(self.get_raw_name(lock.id), lock.id),
                                      self.role)

                capacitor = godma.GetItem(session.shipid)

                # Активируем лазеры на залоченных астероидах
                if targetSvc.targetsByID \
                        and self.get_shield(False) > self.get_shield() * 0.7 \
                        and capacitor.charge > capacitor.capacitorCapacity * 0.5\
                        and not ship.followId:

                    self.activate_lasers(max_range)

                if ship.followId != aster.id and aster.surfaceDist > aproach_range:
                    if self.apr_ball and not self.pen('jet_lag') and self.act_is_ready('aproach_aster'):
                        self.aproach_to(aster, aproach_range)
                        self.send_action_info('aproach_aster')

                else:
                    self.aproach_to(aster, aproach_range)

                if aster.surfaceDist > max_range and self.apr_ball != aster.id:
                    self.apr_ball = aster.id

                elif aster.surfaceDist <= aproach_range:
                    self.apr_ball = None

        elif ship.followId and not self.pen('stop'):
            self.apr_ball = None

            self.info('Останавливаемся, примари покинул грид', self.role)
            do_action(1 + rnd_keys())
            uicore.cmd.CmdStopShip()
            self.set_pen('stop', 2000)

        self.drones_work()

        # Выгружаем руду в контейнер
        if self.unloadToCargo:
            stackless.tasklet(self.jettison)()
            stackless.tasklet(self.rename_jettison)()

        self.asteroid_empty()

        self.in_do_flag = False

    # Метод выхода из режима добычи
    def end_dig(self):

        current = Place.get_current()
        if current:
            bm_in = _bm.get_bookmark(current.name, 'Places')
            bm_ou = _bm.get_bookmark(current.name)

            if bm_ou and not bm_in:
                _bm.del_bookmark(current.name)
            elif bm_in:
                _bm.del_bookmark(current.name, 'Places')

            _bm.set_bookmark(current.name, folder='Places')

        place = self.get_align_place()

        if not place:
            place = self.get_safe_place(self.get_dig_place())

            if not current or place and place.id == current.id:
                place = None

        if place:
            self.align(place)

        self.modules_off(self.get_modules(cnt.groupMiningLasers))

        if not self.check_enemy_in_local():
            self.rename_jettison()

        self.drones_return()

        self.flag_do_action = False
        self.in_do_flag = False

        self.first_dig = True

        self.run_action()

    # Выгружаем ресурсы на станции
    def unload_res(self):
        cargo = self.get_ore_cargo()

        items = self.get_cargo_items(cargo, const.categoryAsteroid)

        if items:
            self.info('Перемещаем ресурсы из трюма в ангар', self.role)

            do_action(5 + rnd_keys())

            if session.stationid:
                hangar = invCtrl.StationItems()
            else:
                hangar = self.get_pos_hungar(self.arrayName, self.divNameS)

            if hangar:
                hangar.AddItems(items)

        if self.check_in_flags('full_cargo'):
            self.del_flag('full_cargo')

            self.run_action()

    # Активация лазеров на астероидах
    def activate_lasers(self, max_range):
        if self.pen('laser'):
            return

        lasers = self.get_modules(cnt.groupMiningLasers)

        bp = sm.GetService('michelle').GetBallpark(True)
        targetSvc = sm.GetService('target')
        targetsByID = copy.copy(targetSvc.targetsByID)

        # Лазеров на астероид
        lpa = len(lasers) - self.get_locking_asters() + 1

        # Отключаем лишнии лазеры
        for targetID in targetsByID:
            slim = bp.GetInvItem(targetID)

            if slim and slim.categoryID == const.categoryAsteroid:
                if self.get_laser_on_aster(lasers, targetID) > lpa:
                    if self.laser_off(lasers, targetID):
                        self.set_pen('laser', 1500)

                        return

        # Активируем лазеры
        for targetID in targetsByID:
            slim = bp.GetInvItem(targetID)

            if slim and slim.categoryID == const.categoryAsteroid:
                ball = bp.GetBallById(targetID)

                if ball and ball.surfaceDist < max_range and self.get_laser_on_aster(lasers, targetID) < lpa:
                    if self.laser_on(lasers, targetID):
                        self.set_pen('laser', 1500)

                        return

                elif ball and ball.surfaceDist > max_range:
                    try:
                        do_action(2 + rnd_keys())

                        targetSvc.UnlockTarget(targetID)
                    finally:
                        return

    # Активация лазеров на астероидах
    def laser_on(self, lasers, targetID):
        bp = sm.GetService('michelle').GetBallpark(True)
        targetSvc = sm.GetService('target')

        for laser in lasers:
            if not self.get_target_id(laser) and not self.pen('change_lock') and not self.pen('laser_on'):
                if self.module_state(laser) == 'off' and self.act_is_ready('laser_on'):
                    slim = bp.GetInvItem(targetID)

                    if not slim or not targetSvc.IsTarget(targetID):
                        continue

                    # Устанавливаем в лазер кристал соответствующий добываемой руде
                    if slim.groupID in cnt.groupsOre + cnt.groupsMercoxit:
                        if not self.reload_crystall(laser, slim.groupID):
                            return True

                    # Делаем выбранный астероид активным
                    if targetID != targetSvc.GetActiveTargetID():
                        targetSvc._SetSelected(targetID)

                    self.set_pen('change_lock', 500)

                    self.modules_on(laser)

                    self.send_action_info('laser_on')

                    self.set_pen('laser_on', 3000)

                    return True

        return False

    # Выключение лазера
    def laser_off(self, lasers, targetID):
        for laser in lasers:
            if self.get_target_id(laser) == targetID:
                if self.module_state(laser) == 'on' and self.act_is_ready('laser_off'):
                    self.modules_off(laser)

                    self.send_action_info('laser_off')

                    return True

        return False

    # Перезагружаем кристал, если необходимо
    def reload_crystall(self, laser, ore):

        if cfg.IsChargeCompatible(laser.sr.moduleInfo):
            if laser.charge:
                for_ore = self.get_crystal_ore(laser.charge)

                if for_ore and for_ore != ore:

                    do_action(2 + rnd_keys())

                    laser.UnloadToCargo(laser.charge.itemID)
                    _m = evetypes.GetGroupNameByGroup(for_ore), for_ore
                    self.info('Вынимаем кристалл для {} ({})'.format(*_m), self.role)

                    while laser.charge:
                        pause()

            if not laser.charge:
                cargo = invCtrl.ShipCargo()
                charge = None

                for item in cargo.GetItems():
                    for_ore = self.get_crystal_ore(item)

                    if for_ore and for_ore == ore:

                        if sm.GetService('skills').IsSkillRequirementMet(item.typeID):
                            charge = item
                            break

                if charge:
                    _m = evetypes.GetGroupNameByGroup(ore), ore
                    self.info('Устанавливаем кристалл для {} ({})'.format(*_m), self.role)

                    laser.changingAmmo = 1

                    try:
                        do_action(2 + rnd_keys())

                        laser.dogmaLocation.LoadChargeToModule(laser.sr.moduleInfo.itemID, charge.typeID)
                    finally:
                        if laser and not laser.destroyed:
                            laser.changingAmmo = 0

                    while not laser.charge:
                        pause()

                else:
                    if 'need_crystall' not in self.flags:
                        self.add_flag('need_crystall')

                        _m = evetypes.GetGroupNameByGroup(ore), ore
                        self.info('Закончились кристаллы для {} ({}), летим на станцию'.format(*_m), self.role)

                        self.run_action()

                    return False

        return True

    # Восстановление щита, модулями или отварпов на станцию
    def repair_shield(self):

        if self.shield_flag:
            return

        self.shield_flag = True

        godma = sm.GetService('godma')

        full = self.get_shield()
        charge_shield = self.get_shield(False)

        if charge_shield < full * 0.3 and not self.check_in_flags('damaged'):
            self.info('Критический заряд щита, варпаем на подзарядку', 'miner  ')
            self.add_flag('damaged')

            self.run_action()

        lasers = self.get_modules(cnt.groupMiningLasers)

        info = None

        if lasers:
            info = lasers[0].sr.moduleInfo

        if charge_shield < full * 0.7 \
                or info and godma.GetItem(session.shipid).charge < godma.GetItem(info.itemID).capacitorNeed * 1.5:

            self.set_pen('laser_on', 10000)
            self.modules_off(lasers)

        shield_boosters = self.get_modules(const.groupShieldBooster)

        if shield_boosters:
            # home = self.get_home()

            if charge_shield >= full * 0.99:  # or home and home.surfaceDist < cnt.gridDistance:
                self.modules_off(shield_boosters)

                self.set_pen('repair_shield', 2000)

            elif not self.pen('repair_shield'):
                self.modules_on(shield_boosters)

                self.set_pen('repair_shield', 2000)

        self.shield_flag = False

    # Обработчик дронов: запуск, атака цели, возвращение на корабль
    def drones_work(self):
        bp = sm.GetService('michelle').GetBallpark()

        if not bp:
            return

        drones = self.get_drones_in_space()

        # Если непись в локале отсутствует
        if not self.npc_in_space():
            if drones:
                self.ret_drones('mining', drones)

            if not self.get_drones_in_bay('mining'):
                return

            targetSvc = sm.GetService('target')

            targets = targetSvc.targetsByID.keys()

            if targets:
                for targetID in targets:
                    slim = bp.GetInvItem(targetID)

                    if slim and slim.groupID not in cnt.groupsOre:
                        return
            else:
                return

            _count, _bandwith = self.get_free_drone()

            # Если дроны в космосе отсутствуют, запускаем шахтерские дроны
            if _count > 0 and _bandwith > 0:
                if self.get_point_aster(True) and not self.is_departing(drones):
                    self.run_drones('mining', _count, _bandwith)

                    return

            # Копаем дронами
            drones = self.get_drones_in_space('mining')

            if drones and not self.pen('drone_mine') and not self.pen('change_lock'):
                mineDrones = []

                for drone in drones:
                    # Если шахтерсие дроны находятся в режиме ожидания
                    if drone.activityState == const.entityIdle:
                        mineDrones += [drone.droneID]

                if mineDrones and self.act_is_ready('drones_mine'):
                    point = self.get_point_aster(True)

                    if point and targetSvc.IsTarget(point.id):
                        if point.id != targetSvc.GetActiveTargetID():
                            do_action(2 + rnd_keys())

                            targetSvc._SetSelected(point.id)

                            self.set_pen('change_lock', 500)

                        self.info('Копаем астероиды дронами ({} шт.)'.format(len(mineDrones)), self.role)

                        do_action(4 + rnd_keys())

                        sm.GetService('menu').MineRepeatedly(mineDrones)
                        self.send_action_info('drones_mine')

                        self.set_pen('drone_mine', 3000)

        # Если непись в локале
        else:

            self.damaged_drones()

            if self.pen('drone_engage'):
                return

            _type = None

            drone_types = {}

            for t in ['medium', 'light']:
                drone_types[t] = {
                    's': self.get_drones_in_space(t),
                    'b': self.get_drones_in_bay(t)
                }

                drone_types[t]['a'] = drone_types[t]['s'] + drone_types[t]['b']

            max_target_range = sm.GetService('godma').GetItem(session.shipid).maxTargetRange

            if min([x.surfaceDist for x in self.get_npc()]) > max_target_range and self.get_drones_in_space():
                return

            if self.get_min_sig() > 50 and len(drone_types['medium']['a']) > 0:
                _type = 'medium'
            elif len(drone_types['light']['a']) > 0:
                _type = 'light'

            # Возвращаем всех дронов не соответствующих типов
            if drones:
                self.ret_drones(_type, drones)

            _count, _bandwith = self.get_free_drone()

            # Если есть возможность, запускаем дронов
            if _type and _count > 0 and _bandwith > 0:
                if not self.is_departing(drones):
                    self.run_drones(_type, _count, _bandwith)
                    self.set_pen('drone_engage', 2000)

            if _type and drone_types[_type]['s']:
                if len(drone_types[_type]['s']) > 0:
                    self.npc_atack(drone_types[_type]['s'])
                    self.set_pen('drone_engage', 2000)

    # Готовим список дронов для возврата на корабль
    def ret_drones(self, _type, drones):

        # if not self.check_enemy_in_local():
        #     return

        ret = []

        # Составляем список дронов для возвращения на корабль
        for drone in drones:
            if not _type or drone.typeID not in cnt.typesDrone[_type]:
                if drone.activityState not in [const.entityDeparting]:  # Состояние при возврате дронов
                    ret += [drone]

        if ret:
            self.drones_return(ret, False)

    # Готовим список дронов для запуска и запускаем
    def run_drones(self, _type, _count, _bandwidth):
        drones = self.get_drones_in_bay(_type)

        if drones:
            _c = _b = 0
            _run = []

            for drone in drones:
                if _c == _count or _b == _bandwidth:
                    break

                _run.append(drone)

                _c += 1
                _b += int(get_type_attr(drone.typeID, const.attributeDroneBandwidthUsed))

            if _run and self.act_is_ready('drones_run'):
                self.info('Запускаем {} дронов ({} шт.)'.format(_type, len(_run)), self.role)

                do_action(5 + rnd_keys())

                try:
                    sm.GetService('menu').LaunchDrones(_run)
                    self.send_action_info('drones_run')
                except:
                    pass

    # Если дроны залочены неписью, возвращать их на корабль для сброса лока
    def damaged_drones(self):
        bp = sm.GetService('michelle').GetBallpark(True)

        drones_in_space = self.get_drones_in_space()

        if not drones_in_space:
            return

        dronesIDs = [x.droneID for x in drones_in_space]

        drones = []

        for npc in self.get_npc():
            for k, v in npc.modules.items():
                target = bp.GetInvItem(v.targetID)

                if target and target.itemID in dronesIDs:
                    drones.append(v.targetID)

        dronelist = []

        for drone in drones_in_space:
            if drone.droneID in drones and drone.activityState != const.entityDeparting and drone not in dronelist:
                dronelist.append(drone)

        if dronelist:
            self.drones_return(dronelist, False)

    # Получаем залоченую или лочищаюся непись
    def get_locked_npc(self, in_locked=False):
        bp = sm.GetService('michelle').GetBallpark(True)
        targetSvc = sm.GetService('target')

        npcs = self.get_npc()
        npcIDs = [x.id for x in npcs]

        result = None

        for targetID in targetSvc.targetsByID:
            if targetID in npcIDs:
                result = targetID

                break

        if in_locked and not result:
            for targetID in targetSvc.targeting:
                if targetID in npcIDs:
                    result = targetID

                    break

        if result:
            return bp.GetInvItem(result)

        return None

    # Выбираем цель для лока
    def get_npc_target(self):
        npcs = self.get_npc()

        if not npcs:
            return None

        bp = sm.GetService('michelle').GetBallpark(True)
        godma = sm.GetService('godma')

        max_target_range = godma.GetItem(session.shipid).maxTargetRange
        max_drone_range = godma.GetItem(session.charid).droneControlDistance

        max_range = min(max_target_range, max_drone_range)

        if not self.i_am_is_primary() and self.prim_target:
            prim_ball = bp.GetBallById(self.prim_target)

            if prim_ball and prim_ball.surfaceDist < max_range:
                return bp.GetInvItem(self.prim_target)

        npc_list = {}

        min_sr = -1

        # Выбираем из неписи с самой маленькой сигнатурой, ближайшую
        for npc in npcs:

            if npc and npc.surfaceDist < max_range:
                slim = bp.GetInvItem(npc.id)
                ball = bp.GetBallById(npc.id)

                sr = get_type_attr(slim.typeID, 552)  # signatureRadius

                if min_sr > sr or min_sr == -1:
                    min_sr = sr

                if sr not in npc_list:
                    npc_list[sr] = []

                npc_list[sr].append((ball.surfaceDist, slim))

        in_lock = self.get_locked_npc()

        if npc_list:
            npc_list = npc_list[min_sr]

            npc_list.sort()

            if not in_lock or get_type_attr(in_lock.typeID, 552) != min_sr:
                return npc_list[0][1]
            else:
                return in_lock

        return None

    # Лочим и атакуем непись
    def npc_atack(self, drones):
        if self.get_max_target() == 0 or 'jam' in self.ewar:
            return

        targetSvc = sm.GetService('target')

        target = self.get_npc_target()
        in_lock = self.get_locked_npc()

        if in_lock:

            # Если сигнатуры залоченной и новой неписы различаются, сбрасываем лок
            if target and in_lock.itemID != target.itemID:
                self.info('Сбрасываем лок с {} ({})'.format(self.get_raw_name(in_lock.itemID), in_lock.itemID),
                          self.role)

                try:
                    do_action(2 + rnd_keys())

                    targetSvc.UnlockTarget(in_lock.itemID)
                finally:
                    return

            drone_ids = []

            for drone in drones:
                if drone.targetID != in_lock.itemID:
                    drone_ids.append(drone.droneID)

            if drone_ids and not self.pen('change_lock') and self.act_is_ready('drones_engage'):
                if in_lock.itemID != targetSvc.GetActiveTargetID():
                    do_action(2 + rnd_keys())

                    targetSvc._SetSelected(in_lock.itemID)

                    self.set_pen('change_lock', 500)

                self.info('Дроны атакует {} ({})'.format(self.get_raw_name(in_lock.itemID), in_lock.itemID), self.role)

                try:
                    do_action(2 + rnd_keys(), 2 + rnd_keys())

                    sm.GetService('menu').EngageTarget(drone_ids)
                    self.send_action_info('drones_engage')
                except:
                    self.info('Ошибка атаки {} ({})'.format(self.get_raw_name(in_lock.itemID), in_lock.itemID),
                              self.role)

            return

        if target and not self.pen('npc_lock') and not self.get_locked_npc(True):
            self.info('Лочим {} ({})'.format(self.get_raw_name(target.itemID), target.itemID), self.role)

            try:
                targetSvc.TryLockTarget(target.itemID)
                if self.i_am_is_primary():
                    rec = {'type': 'notification', 'func': 'up_prim_target', 'target_id': target.itemID}
                    send_to_role('?{}'.format(pickle.dumps(rec)))

            except:
                self.info('Ошибка лока {} ({})'.format(self.get_raw_name(target.itemID), target.itemID), self.role)

    def split_drones(self):
        if bool(get_attr(util.GetActiveShip(), const.attributeDroneCapacity)):
            dronbay = invCtrl.ShipDroneBay(util.GetActiveShip())

            while True:
                _break = True

                for item in dronbay.GetItems():
                    if item.quantity > 1:
                        _break = False

                        do_action(2 + rnd_keys())

                        repl.move_items(dronbay, item, 1)
                        pause(100)

                if _break:
                    break

    # Выгрузка руды в контейнер
    def jettison(self):
        if self.in_jet_flag or self.pen('jettison'):
            return

        try:
            self.in_jet_flag = True

            cargo = self.get_ore_cargo()

            if not cargo:
                self.in_jet_flag = False
                return

            vol = cargo.GetCapacity()

            vol_per_cicle = 0

            for miner in self.get_modules(cnt.groupMiningLasers):
                amount = get_attr(miner.sr.moduleInfo.itemID, const.attributeMiningAmount)

                if miner.charge:
                    multiplier = get_attr(miner.charge.itemID, const.attributeSpecialisationAsteroidYieldMultiplier)
                    amount = multiplier * amount

                vol_per_cicle += amount

            # Если следующий цикл перегрузит карго, выгружаем руду в джет
            if vol.capacity - vol.used < vol_per_cicle * 1.1:
                pause(200)

                items = self.get_cargo_items(cargo, const.categoryAsteroid)

                if not items:
                    self.in_jet_flag = False
                    return

                volume = 0

                pause()

                # for i in range(0, len(items)):
                #     if items[i].locationID != util.GetActiveShip():
                #         del items[i]

                for item in items:
                    volume += (evetypes.GetVolume(item.typeID) * item.stacksize)

                jet = self.get_jettison()

                # Если не входит, переносить частями
                if jet:
                    if not self.jet_is_busy(jet.itemID):
                        try:
                            vol_jet = jet.GetCapacity()

                            used = vol_jet.used

                            if volume + vol_jet.used < vol_jet.capacity:
                                self.info('Переносим {} кубов руды в контейнер ({})'.format(volume, jet.itemID), self.role)

                                do_action(5 + rnd_keys())

                                pause(200)

                                jet.AddItems(items)

                                self.set_pen('jettison', 5000)

                                used += volume

                                volume = 0

                            else:
                                free = vol_jet.capacity - vol_jet.used

                                for item in items:
                                    item_vol = evetypes.GetVolume(item.typeID)

                                    max_count = int(free / item_vol)
                                    count = min([max_count, item.stacksize])

                                    if count <= 0:
                                        break

                                    self.info('Переносим {} кубов руды в контейнер ({})'.format(item_vol * count,
                                                                                                jet.itemID), self.role)

                                    do_action(5 + rnd_keys())

                                    pause(200)

                                    repl.move_items(jet, item, count)

                                    self.set_pen('jettison', 5000)

                                    free -= item_vol * count
                                    volume -= item_vol * count

                                    used += item_vol * count

                            query = 'UPDATE miner_jet SET volume = %s '
                            query += 'WHERE jet_id = %s'

                            db_query(query, (used, jet.itemID))

                        finally:
                            self.jet_free(jet.itemID)
                    else:
                        self.info('Джет {} занят'.format(jet.itemID), self.role)

                        self.in_jet_flag = False
                        return

                if (not jet or volume > 0) and not self.pen('jet_lag') and self.act_is_ready('jettison'):

                    ship = sm.StartService('gameui').GetShipAccess()
                    items = self.get_cargo_items(cargo, const.categoryAsteroid)

                    if ship:
                        do_action(3 + rnd_keys())

                        self.set_pen('jet_lag', 90000)

                        invItemFunctions.Jettison(items)
                        self.send_action_info('jettison')

                        self.info('Выгружаем {} кубов руды в новый контейнер'.format(volume), self.role)
        finally:
            self.in_jet_flag = False

    def get_collector_ship(self):
        bp = sm.GetService('michelle').GetBallpark()

        if not bp:
            return None

        for v in bot.bots.values():
            if v['role'] == 'collector' and sm.GetService('onlineStatus').GetOnlineStatus(v['id'], True):
                for ball_id, ball in bp.balls.items():

                    slim = bp.GetInvItem(ball_id)

                    if slim and slim.ownerID == v['id']:
                        return ball

        return None

    # Получаем ближайший контейнер
    def get_jettison(self):
        bp = sm.GetService('michelle').GetBallpark(True)

        js = []

        collector = self.get_collector_ship()

        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)

            if slim and slim.typeID == const.typeCargoContainer \
                    and (slim.ownerID == session.charid or slim.ownerID in [x['id'] for x in bot.bots.values()]) \
                    and ball.surfaceDist < const.maxCargoContainerTransferDistance \
                    and not self.jet_is_busy(slim.itemID, False):

                skip = False

                if collector:
                    for k, v in collector.modules.items():
                        if v.targetID == slim.itemID and v.IsShooting():
                            skip = True

                            break

                if skip:
                    continue

                cont = invCtrl.ItemFloatingCargo(slim.itemID)

                try:
                    js += [(cont.GetCapacity().used, cont)]
                except:
                    pass

        if js:
            js.sort()
            return js[0][1]

        return None

    # Переименовываем джет
    def rename_jettison(self):
        if self.in_ren_jet or self.pen('jet_rename'):
            return

        self.in_ren_jet = True

        bp = sm.GetService('michelle').GetBallpark()

        if not bp:
            self.in_ren_jet = False
            return

        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)

            if slim and slim.typeID == const.typeCargoContainer and \
                            slim.ownerID == session.charid and \
                            ball.surfaceDist < const.maxCargoContainerTransferDistance:
                name = cfg.evelocations.Get(slim.itemID).name

                if not name:

                    invCache = sm.GetService('invCache')

                    if not self.jet_is_busy(slim.itemID) and invCache.TryLockItem(slim.itemID):
                        try:
                            rand_pause(3000, 6000)

                            cfg.evelocations.Prime([slim.itemID])

                            new_name = 'D74'

                            self.info('Переименовываем контейнер ({}) - {}'.format(slim.itemID, new_name), self.role)

                            do_action(5 + rnd_keys(), 5 + rnd_keys())
                            invCache.GetInventoryMgr().SetLabel(slim.itemID, new_name)

                            sm.ScatterEvent('OnItemNameChange')
                        finally:
                            invCache.UnlockItem(slim.itemID)

                            self.jet_free(slim.itemID)

                            jet = invCtrl.ItemFloatingCargo(slim.itemID)

                            query = 'INSERT INTO miner_jet '
                            query += '(jet_id, place_id, owner_id, volume, jettison) '
                            query += 'VALUES(%s, %s, %s, %s, %s)'

                            place = Place.get_current()
                            if place:
                                db_query(query, (slim.itemID, place.id, session.charid, jet.GetCapacity().used,
                                                     datetime.datetime.now()))

                                self.set_pen('jet_rename', 2000)
                            else:
                                self.warn('Джет не будет занесен в БД, место не определено', self.role)

                            break

        self.in_ren_jet = False

    def load_crystals(self):
        hangar = None

        if session.stationid:
            hangar = invCtrl.StationItems()
        else:
            pos = self.get_place_by_bm(_bm.get_bookmark('POS'))

            if pos and pos.is_achived():
                hangar = self.get_pos_hungar(self.arrayName, self.divName)

        if hangar:
            if not self.jet_is_busy(hangar.itemID):
                try:
                    do_action(5 + rnd_keys())

                    self.move_crystal_to_cargo(hangar)
                finally:
                    self.jet_free(hangar.itemID)

            self.run_action()
        else:
            self.warn('Ангар с кристалами не обнаружен', self.role)

    # В трюме всегда должен быть x запасных кристаллов для лазеров, где x кол-во лазеров
    def move_crystal_to_cargo(self, hangar):

        cargo = invCtrl.ShipCargo()

        # laser_count = get_attr(util.GetActiveShip(), const.attributeHiSlots)

        lasers = self.get_modules(cnt.groupMiningLasers)
        laser_count = 0

        for laser in lasers:
            if cfg.IsChargeCompatible(laser.sr.moduleInfo):
                laser_count += 1

        if laser_count == 0:
            self.del_flag('need_crystall')

            return

        add_ore = {}

        for item in self.pack_groups(self.res):
            add_ore[item] = laser_count

        # Разряжаем лазеры
        for laser in lasers:
            if laser.charge:

                do_action(2 + rnd_keys())

                laser.UnloadToCargo(laser.charge.itemID)
                pause(50)

        # Проверяем наличие необходимых кристаллов в трюме, лишние переносим в ангар
        for item in cargo.GetItems():
            for_ore = self.get_crystal_ore(item)

            if for_ore:
                _c = 0

                if for_ore in add_ore.keys():
                    if item.stacksize <= add_ore[for_ore]:
                        add_ore[for_ore] -= int(item.stacksize)
                    else:
                        # Переносим лишние кристаллы в ангар
                        _c = int(item.stacksize - add_ore[for_ore])
                        add_ore[for_ore] = 0
                else:
                    _c = int(item.stacksize)

                if _c > 0:
                    do_action(4 + rnd_keys())

                    repl.move_items(hangar, item, _c)

                    pause(50)

                    _m = evetypes.GetGroupNameByGroup(for_ore)
                    self.info('Перемещаем кристаллы ({} шт.) для {} из трюма в ангар'.format(_c, _m), self.role)

        if self.get_type_resource() != 'ore':
            self.del_flag('need_crystall')
            return

        # Если кристаллов не хватает, переносим из ангара в трюм недастающие
        prms = [(2, True), (2, False), (1, True), (1, False)]

        for l, s in prms:
            if self._crystal_is_need(add_ore):
                add_ore = self._move_crystal_to_cargo(hangar, add_ore, l, s)

        if self._crystal_is_need(add_ore):
            for key, val in add_ore.iteritems():
                if val > 0:
                    _m = evetypes.GetGroupNameByGroup(key)
                    self.warn('Заканчиваются кристаллы для {} ({}), не хватает {} шт.'.format(_m, key, val), self.role)
                    self.add_flag('topos')

        self.del_flag('need_crystall')

    def _move_crystal_to_cargo(self, hangar, add_ore, level=None, singleton=None):
        cargo = invCtrl.ShipCargo()

        for item in hangar.GetItems():
            for_ore = self.get_crystal_ore(item)

            if for_ore:

                if level and level != int(get_type_attr(item.typeID, const.attributeTechLevel)):
                    continue

                if singleton and not item.singleton:
                    continue

                if not sm.GetService('skills').IsSkillRequirementMet(item.typeID):
                    continue

                _c = 0

                if for_ore in add_ore.keys() and add_ore[for_ore] > 0:
                    if item.stacksize >= add_ore[for_ore]:
                        _c = int(add_ore[for_ore])
                        add_ore[for_ore] = 0
                    else:
                        _c = int(item.stacksize)
                        add_ore[for_ore] -= int(item.stacksize)

                if _c > 0:
                    do_action(5 + rnd_keys())

                    repl.move_items(cargo, item, _c)

                    pause(50)

                    _m = evetypes.GetGroupNameByGroup(for_ore)
                    self.info('Перемещаем кристаллы ({} шт.) для {} из ангара в трюм'.format(_c, _m), self.role)

        return add_ore

    def _crystal_is_need(self, add_ore):
        for val in add_ore.values():
            if val > 0:
                return True

        return False

    # Пришло уведомление
    def j_notification(self, login, data):
        if not self.is_ready: return

        Mine.j_notification(self, login, data)

        if data['func'] == 'up_prim_target':
            self.prim_target = data['target_id']

        elif data['func'] == 'skip_list':
            act = data['action']
            blt = data['belt']

            if act == 'add':
                self.add_item_list(self.skip_belts, blt)
            elif act == 'del':
                self.del_item_list(self.skip_belts, blt)

        elif data['func'] == 'only_list':
            act = data['action']
            blt = data['belt']

            if act == 'add':
                self.add_item_list(self.only_belts, blt)
            elif act == 'del':
                self.del_item_list(self.only_belts, blt)

    # endregion

    # Отключение лазеров для которых пропали астероиды
    def asteroid_empty(self):
        bp = sm.GetService('michelle').GetBallpark()

        if not bp:
            return

        items = []

        for laser in self.get_modules(cnt.groupMiningLasers):
            targetID = self.get_target_id(laser)

            if targetID and not bp.GetBallById(targetID):
                items.append(laser)

        if items:
            self.modules_off(items)
            self.set_pen('laser', 500)

    def wait(self):
        if self.check_in_inflight():
            pos = self.get_place_by_bm(_bm.get_bookmark('POS'))

            if pos and pos.is_achived():
                self.unload_res()

        Mine.wait(self)

    def OnEveMessage(self, msgkey):
        if not self.is_ready: return

        if msgkey == 'MiningDronesDeactivatedAsteroidEmpty':
            self.info('Астероид превратился в пыль', self.role)

            self.set_pen('jet_guard', 10000)

        # Трюм заполнен
        elif msgkey == 'MiningDronesDeactivatedCargoHoldNowFull':
            if not self.unloadToCargo:
                self.info('Трюм заполнен', self.role)

                self.add_flag('full_cargo')

                self.run_action()
            else:
                self.warn('Трюм заполнен', self.role)

                # uthread.new(self.jettison)
                # stackless.tasklet(self.jettison)()

    def DoBallsAdded(self, balls_slimItems, *args, **kw):
        if not self.is_ready: return

        for ball, slimItem in balls_slimItems:
            if slimItem.categoryID == const.categoryEntity:
                if slimItem.groupID in self.get_npc_pirates():
                    if not self.npc:
                        place = Place.get_current()

                        if place:
                            rec = {'type': 'notification', 'func': 'npc_in_place', 'place_id': place.id}
                            send_to_role('?{}'.format(pickle.dumps(rec)), 'collector')

                    name = evetypes.GetName(slimItem.typeID)
                    self.info('NPC появился {} ({})'.format(name, ball.id), self.role)
                    self.npc.append(ball.id)

    def DoBallRemove(self, ball, slimItem, terminal):
        if not self.is_ready: return

        if hasattr(self, 'prim_target'):
            if ball.id == self.prim_target:
                self.prim_target = None

        if ball.id in self.npc:
            name = evetypes.GetName(slimItem.typeID)

            self.info('NPC исчез {} ({})'.format(name, ball.id), self.role)

            self.npc.remove(ball.id)

            self.set_pen('npc_lock', 500)

            if not self.npc:
                place = Place.get_current()

                if place:
                    rec = {'type': 'notification', 'func': 'place_is_clear', 'place_id': place.id}
                    send_to_role('?{}'.format(pickle.dumps(rec)), 'collector')

        if slimItem.categoryID == const.categoryAsteroid:
            self.set_pen('lock_aster', 1000)

    def DoBallsRemove(self, pythonBalls, isRelease):
        if not self.is_ready: return

        for ball, slimItem, terminal in pythonBalls:
            self.DoBallRemove(ball, slimItem, terminal)

    def OnDamageStateChange(self, shipID, damageState):
        if not self.is_ready: return

        if session.shipid == shipID:
            stackless.tasklet(self.repair_shield)()

    def UnlockTarget(self, tid):
        if not self.is_ready: return

        self.set_pen('lock_aster', 1000)
        self.set_pen('npc_lock', 500)
