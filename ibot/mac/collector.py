from datetime import datetime as dt

import evetypes
import invCtrl
import stackless
import util

import ibot.utils.bms as _bm
from ibot.mac.template.mine import Mine
from ibot.utils import cnt
from ibot.utils import repl
from ibot.utils.places import *


def run():
    if not bot.macros:
        bot.macros = Collector()


class Collector(Mine):
    __notifyevents__ = [
        'DoBallsAdded'
    ]

    # TODO: Зависает по прилету на аномальку

    # Инициализация класса
    def __init__(self, _run=True):

        self.actions = {
            'collect': {
                'co': [
                    lambda: self.collect_is_ready(),
                    lambda: not self.check_enemy_in_local(),
                    lambda: not self.check_in_flags('topos')
                ],
                'po': lambda: self.get_jet_place(self.get_jet()),
                'go': self.go,
                'do': self.collect,
                'tm': None,
                'iv': 1000,
                'ed': self.end_collect,
                'pr': -100
            },
            'zip': {
                'co': [
                    lambda: self.check_in_flags('zip')
                ],
                'po': lambda: self.get_place_by_bm(_bm.get_bookmark('ZIP')),
                'go': self.go,
                'do': self.ziping
            },
            'unload': {
                'co': [
                    lambda: self.check_in_flags('unload')
                ],
                'po': self.get_unload_place,
                'go': self.go,
                'do': self.unload
            },
            'wait_jet': {
                'co': [
                    lambda: not self.collect_is_ready()
                ],
                'po': lambda: self.get_place_by_bm(_bm.get_bookmark('POS')),
                'go': self.go,
                'do': self.wait,
                'pr': -50
            }
        }

        bot.log.info('Запускаем макрос')

        Mine.__init__(self, 'collector')

        # Настройки
        self.homeID = int(self.s.ga('HomeID', 0))
        self.unloadToPOS = bool(self.s.ga('UnloadToPOS', True))
        self.arrayName = self.s.ga('ArrayName', '')
        self.divName = self.s.ga('DivName', '')
        self.isZipping = bool(self.s.ga('IsZiping', False))
        self.unloadVolume = int(self.s.ga('UnloadVolume', 0))

        self.in_do_flag = False
        self.in_update = False

        self._up_jet = None

        self.npc = {}
        self.jets = []

        self.is_ready = True

        self.info('Макрос запущен', self.role)

        if session.stationid:
            self.repair_ship()

        self.OnDownTime()

        self.add_flag('init')

        pause(1000)

        if not self.check_in_flags('downtime'):
            self.update_jet_list()

            self.clear_old_jets()

            self._up_jet = base.AutoTimer(30000, self.update_jet_list, True)

            self.run_action()

            set_bot_params('role', self.role)

    def __deinit__(self):
        if hasattr(self, '_up_jet') and self._up_jet:
            self._up_jet.KillTimer()
            self._up_jet = None

        Mine.__deinit__(self)

    # region Функции

    # Очищаем список неписи
    def clean_npc(self):
        items = []
        for k, v in self.npc.items():
            if dt.now() - v > datetime.timedelta(minutes=5):
                items.append(k)

        for item in items:
            del self.npc[item]

    # Обновляем список джетов из БД
    def update_jet_list(self, inside=False):
        if self.in_update or session.stationid or not self._up_jet:
            return

        self.in_update = True

        query = 'SELECT * FROM miner_jet ORDER BY jettison'
        jets = db_select(query)

        if jets == 'error':
            self.in_update = False
            return

        self.jets = []

        for jet in jets:
            if jet:
                self.jets.append(
                    {
                        'jet_id': int(jet[1]),
                        'place_id': int(jet[2]),
                        'owner_id': int(jet[3]),
                        'volume': float(jet[4]),
                        'date': jet[5]
                    }
                )

        self.in_update = False

        if inside:
            place = self.get_place_by_bm(_bm.get_bookmark('POS'))

            if self.collect_is_ready() and place and place.is_achived():
                self.run_action()

    # Проверяем готовность джетов к сбору
    def collect_is_ready(self):

        if session.solarsystemid:
            current = Place.get_current()

            if current:
                if not self.get_npc() and self.get_jet_in_space():
                    return True

        jets = self.get_jets()

        if jets:
            volume = 0

            for jet in jets:

                if jet['place_id'] in self.npc or dt.now() - jet['date'] < datetime.timedelta(minutes=3):
                    continue

                volume += jet['volume']

            if volume >= self.unloadVolume:
                return True

            if self.check_in_flags('collect'):
                for jet in jets:
                    if jet['place_id'] in self.npc:
                        continue

                    return True

        else:
            self.del_flag('collect')

        return False

    # Получить джет для сбора
    def get_jet(self):
        jets = self.get_jets()

        if jets:
            for jet in jets:
                if jet['place_id'] in self.npc:
                    continue

                elif not self.check_in_flags('collect') and dt.now() - jet['date'] < datetime.timedelta(minutes=3):
                    continue

                elif jet:
                    return jet

        return None

    # Удалить джет
    def del_jet(self, jet_id):
        query = 'DELETE FROM miner_jet WHERE jet_id = %s'

        db_query(query, (jet_id, ))

    # Список джетов накопаных и не собранных ботами
    def get_jets(self):
        while self.in_update:
            pause()

        return self.jets

    # Получить место с контейнером
    def get_jet_place(self, jet):
        if jet:
            for k, v in cnt.places.items():
                if k == jet['place_id']:
                    return v

        return None

    # Получить место выгрузки руды
    def get_unload_place(self):
        if self.unloadToPOS:
            return self.get_place_by_bm(_bm.get_bookmark('POS'))
        else:
            return self.get_home()

    # endregion

    # region Методы

    # Удаляем старые ссылки на контейнеры
    def clear_old_jets(self):
        now = dt.now()

        jets = self.get_jets()

        if jets:

            to_clear = []

            for jet in jets:
                if now - jet['date'] > datetime.timedelta(hours=2):
                    to_clear.append((jet['jet_id'], ))

            if to_clear:
                query = 'DELETE FROM miner_jet WHERE jet_id = %s'

                db_query(query, to_clear)

            self.update_jet_list()

    # Переносим руду из джета в трюм
    def get_jet_items(self, jet):

        carg = self.get_ore_cargo()  # Трюм
        cont = invCtrl.ItemFloatingCargo(jet.id)  # Джет

        if not carg or not cont or jet.surfaceDist > const.maxCargoContainerTransferDistance * 0.8:
            return

        vol = carg.GetCapacity()  # Объем трюма

        free = vol.capacity - vol.used  # Свободно в трюме
        items = self.get_cargo_items(cont)  # Все элементы в джете

        vol_jet = cont.GetCapacity().used

        if not items:
            return

        do_action(2 + rnd_keys())

        jet_free = True

        if not self.jet_is_busy(jet.id):
            try:
                for item in items:
                    item_vol = evetypes.GetVolume(item.typeID)  # Объем единици руды

                    max_count = int(free / item_vol)  # Максимальное количество руды помещающееся в трюме
                    count = min([max_count, item.stacksize])  # Количество руды для переноса

                    if count == 0:
                        break

                    self.info('Переносим {} кубов {} в контейнер ({})'.format(item_vol * count, evetypes.GetName(item.typeID),
                                                                              jet.id), self.role)

                    do_action(1 + rnd_keys())

                    repl.move_items(carg, item, count)  # Переносим руду из джета в трюм

                    free -= item_vol * count
                    vol_jet -= item_vol * count
            except:
                self.info('Ошибка при переносе руды из джета {}'.format(jet.id), self.role)
        else:
            return

        bp = sm.GetService('michelle').GetBallpark()

        pause(1000)

        ball = bp.GetBallById(jet.id)

        if not ball or int(vol_jet) == 0:
            jet_free = False

            self.del_jet(jet.id)

            self.info('Удаляем джет {} из БД'.format(jet.id), self.role)

        else:
            vol = cont.GetCapacity()

            query = 'UPDATE miner_jet SET volume = %s '
            query += 'WHERE jet_id = %s'

            db_query(query, (vol.used, jet.id))

            self.info('Меняем объем джета {} в БД - {}'.format(jet.id, vol.used))

        if jet_free:
            self.jet_free(jet.id)

        self.update_jet_list()

    def collect(self):
        if self.in_do_flag or self.flags and not self.check_in_flags('collect'):
            return

        self.in_do_flag = True

        if bool(self.get_npc()):
            stackless.tasklet(self.protect_mod_on)()
        else:
            stackless.tasklet(self.protect_mod_off)()

        godma = sm.GetService('godma')

        full = godma.GetItem(session.shipid).shieldCapacity
        charge_shield = godma.GetItem(session.shipid).shieldCharge

        if charge_shield < full * 0.2:
            self.warn('Критический заряд щита, варпаем на подзарядку', 'miner  ')
            self.add_flag('damaged')

            self.in_do_flag = False

            self.run_action()

            return

        if bool(self.get_npc()):
            current = Place.get_current()

            if current:
                self.npc[current.id] = dt.now()

            self.info('Непись в белте, отварпываем', self.role)

            if not self.collect_is_ready():
                self.del_flag('collect')

            self.in_do_flag = False

            self.run_action()

            return

        jet = self.get_jet_in_space()

        vol = self.get_ore_cargo().GetCapacity()

        # if not jet:
        #     jets = self.get_jets()
        #     current = Place.get_current()
        #
        #     if jets and current:
        #         for j in jets:
        #             if j['place_id'] == current.id:
        #                 self.warn('Неудаленный джет {}'.format(j['jet_id']), self.role)

        # Если в гриде больше нет джетов или трюм заполнен
        if not jet or vol.used > vol.capacity * 0.9:

            if self.isZipping:
                self.add_flag('zip')
            else:
                self.add_flag('unload')

            self.in_do_flag = False

            self.run_action()

            return

        # Переносим руду из джета в трюм
        if jet.surfaceDist < const.maxCargoContainerTransferDistance * 0.8 and not self.jet_is_busy(jet.id, False):
            self.get_jet_items(jet)

            self.in_do_flag = False
            return

        # Приближаемся к выбранному джету
        lock = self.get_jet_in_space(True, False)
        if lock:
            jet = lock
        else:
            lock = self.get_jet_in_space(False)

            if lock:
                jet = lock

        self.aproach_to(jet)

        target = sm.GetService('target')
        tractors = self.get_modules(const.groupTractorBeam)

        # Максимальня дистанция действия тракторов
        max_range = min([int(godma.GetItem(x.sr.moduleInfo.itemID).maxRange) for x in tractors])

        if jet.surfaceDist > max_range and not self.pen('burn'):
            burners = self.get_modules(const.groupAfterBurner)

            self.modules_on(burners)

            self.set_pen('burn', 2000)

        # Активируем тракторы на залоченных джетах
        if target.targetsByID:
            self.tractor_on(tractors, max_range)

        max_targets = min([len(tractors), self.get_max_target()])

        # Лочим джеты, если залоченых и лочащихся джетов меньше максимального количества целей
        if len(target.targetsByID) + len(target.targeting) < max_targets:
            # Выбираем еще не залоченный, ближайший или просроченный джет
            jet = self.get_jet_in_space(False)

            # Если джет находится в пределах лока, лочим его
            if jet and get_attr(util.GetActiveShip(), const.attributeMaxTargetRange) > jet.surfaceDist > \
                    const.maxCargoContainerTransferDistance * 0.8:
                try:
                    if not self.pen('trylock'):
                        self.info('Лочим джет - {}'.format(jet.id), self.role)

                        do_action(2 + rnd_keys())

                        # uthread.new(sm.GetService('target').TryLockTarget, jet.id)
                        stackless.tasklet(sm.GetService('target').TryLockTarget)(jet.id)

                        self.set_pen('trylock', 1000)
                except:
                    self.info('Ошибка лока джета - {}'.format(jet.id), self.role)

        self.in_do_flag = False

    def end_collect(self):
        self.modules_off(self.get_modules(const.groupTractorBeam))

        current = Place.get_current()

        if current:
            _bm.del_bookmark(current.name, 'Places')
            _bm.set_bookmark(current.name, folder='Places')

        self.flag_do_action = False

        self.run_action()

    # Активируем тракторы на залоченных джетах
    def tractor_on(self, tractors, max_range):
        if self.pen('beam'):
            return

        bp = sm.GetService('michelle').GetBallpark(True)
        target = sm.GetService('target')

        # Список джетов по которым работают тракторы
        targetIDs = [self.get_target_id(x) for x in tractors]

        try:
            for tjet in target.targetsByID:
                # Если дистанция до джета больше минимальной или джет уже притягивается трактором
                if bp.GetBallById(tjet).surfaceDist > max_range or tjet in targetIDs or self.jet_is_busy(tjet, False):
                    continue

                for tractor in tractors:
                    # Если трактор отключен
                    if not self.get_target_id(tractor):

                        # Если джет не является текущей целью
                        if tjet != target.GetActiveTargetID():
                            target._SetSelected(tjet)

                        self.modules_on(tractor)

                        self.set_pen('beam', 1500)

                        return
        except:
            return

    # Сжатие руды на ПОСе
    def ziping(self):
        bp = sm.GetService('michelle').GetBallpark(True)

        _zip = None
        _car = None
        _slm = None

        # Ищем обжималку
        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)

            if slim and slim.typeID == const.typeCompressionArray:
                _zip = ball
                _car = invCtrl.POSCompression(slim.itemID)
                _slm = slim

                break

        # Если нашли
        if _zip and _car:
            wnd = form.ActiveItem.GetIfOpen()

            if wnd:
                wnd.OnMultiSelect([_zip.id])

            do_action(3 + rnd_keys(), 1 + rnd_keys())

            flag = False

            # Подлетаем к обжималке
            if not _car.IsInRange():
                flag = True

                do_action(2 + rnd_keys())

                sm.GetService('menu').Approach(_zip.id)

            while not _car.IsInRange():
                pause()

            if flag:
                do_action(1 + rnd_keys())

                uicore.cmd.CmdStopShip()

            cargo = self.get_ore_cargo()

            if not cargo:
                return

            t = datetime.datetime.now()

            # Ждем пока освободится обжималка
            while _car.GetCapacity().used != 0.0:
                pause()

                if dt.now() - t > datetime.timedelta(minutes=1):
                    break

            # Собираем руду в стопки
            do_action(4 + rnd_keys())

            cargo.StackAll()

            pause(1000)

            # Выбираем руду в трюме
            all_items = self.get_cargo_items(cargo, _types=cnt.typesNotCompress)

            items = []

            for item in all_items:
                if item.stacksize >= 100:
                    items.append(item)

            # Переносим в обжималку и жмем
            if items:
                do_action(3 + rnd_keys())

                _car.AddItems(items)

                rand_pause()

                # Сжимаем
                all_items = self.get_cargo_items(_car, _types=cnt.typesNotCompress)

                items = []
                templ = []

                for item in all_items:
                    if item.stacksize >= 100:
                        items.append(item)

                        count = int(item.stacksize / 100)

                        templ.append((item.groupID, count))  # Сжатой руды
                        templ.append((item.groupID, item.stacksize - count * 100))  # Остаток

                if items:
                    for item in items:
                        do_action(5 + rnd_keys())

                        sm.GetService('menu').CompressItem(item, _slm)

                    rand_pause()

            # Переносим из обжималки в трюм
            all_items = self.get_cargo_items(_car)

            items = []

            for item in all_items:
                tpl = (item.groupID, item.stacksize)

                if tpl in templ:
                    items.append(item)

                    del templ[templ.index(tpl)]

            # Список ресурсов в обжималке которые необходимо перенести в трюим или на пос
            if items:
                if self.unloadToPOS:
                    poshungar = self.get_pos_hungar(self.arrayName, self.divName)

                    if poshungar and poshungar.IsInRange():

                        do_action(4 + rnd_keys())

                        poshungar.AddItems(items)

                else:
                    do_action(4 + rnd_keys())

                    cargo.AddItems(items)

                    items = self.get_cargo_items(cargo, _types=cnt.typesCompress)

                    # Если в трюме есть сжатая руда, разгружаем
                    if items:
                        self.add_flag('unload')

            if self.check_in_flags('zip'):
                self.del_flag('zip')

                self.run_action()

    # Разгрузка ресурсов
    def unload(self):
        if self.unloadToPOS:
            hangar = self.get_pos_hungar(self.arrayName, self.divName)
        else:
            if not session.stationid:
                self.warn('Не могу выгрузить ресурсы, необходимо находиться на станции', self.role)
                return

            hangar = invCtrl.StationItems()

        if not hangar:
            self.warn('Не могу получить доступ к ангару', self.role)
            return

        cargo = self.get_ore_cargo()

        do_action(4 + rnd_keys())

        cargo.StackAll()

        pause(1000)

        # Перемещаем ресурсы из трюма в ангар
        all_items = self.get_cargo_items(cargo)

        pause(1000)

        items = []

        if self.isZipping:
            _type = cnt.typesCompress
        else:
            _type = cnt.typesNotCompress

        for item in all_items:
            if item.typeID in _type:
                items.append(item)

        if items:
            while self.jet_is_busy(hangar.itemID):
                pause(500)

            bot.log.info('Перемещаем ресурсы из трюма в ангар', self.role)

            do_action(5 + rnd_keys())

            hangar.AddItems(items)

            self.jet_free(hangar.itemID)

        if self.check_in_flags('unload'):
            self.del_flag('unload')

            self.run_action()

    # endregion

    # region Связь ботов

    # Уведомления приходящие от других ботов
    def j_notification(self, login, data):
        if not self.is_ready: return

        Mine.j_notification(self, login, data)

        if data['func'] == 'npc_in_place':
            place_id = data['place_id']

            self.npc[place_id] = dt.now()

        elif data['func'] == 'place_is_clear':
            place_id = data['place_id']

            if place_id in self.npc:
                del self.npc[place_id]

        elif data['func'] == 'collect':
            if self.check_in_flags('collect'):
                return

            self.clean_npc()

            self.update_jet_list()

            self.add_flag('collect')

            self.run_action()

    # Уведомления приходящие от других ботов
    def notification(self, who, func, *args):
        if not self.is_ready: return

        Mine.notification(self, who, func, *args)

        if func == 'collect':
            if self.check_in_flags('collect'):
                return

            self.clean_npc()

            self.update_jet_list()

            self.add_flag('collect')

            self.run_action()

    def DoBallsAdded(self, balls_slimItems, *args, **kw):
        if not self.is_ready: return

        if not self.pen('protect_on') and self.get_npc():
            stackless.tasklet(self.protect_mod_on)()

            self.set_pen('protect_on', 1000)

    # endregion