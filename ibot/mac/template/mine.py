from datetime import datetime as dt

import invCtrl
import stackless
import util
from sensorsuite.overlay.sitetype import *

import ibot.utils.bms as _bm
import ibot.utils.note as _note
from ibot.mac.template.oldspace import Space
from ibot.utils.places import *


class Mine(Space):
    __notifyevents__ = [
        'OnDownTime'
    ]
    
    def __init__(self, _role=None):
        actions = {
            'init': {
                'co': [
                    lambda: self.check_in_flags('init'),
                    lambda: not self.check_enemy_in_local()
                ],
                'do': self.init_places,
                'pr': 40
            },
            'downtime': {
                'co': [
                    lambda: self.check_in_flags('downtime')
                ],
                'po': lambda: self.get_place_by_bm(_bm.get_bookmark('POS')),
                'go': self.go,
                'do': self.downtime,
                'pr': 100
            },
            'buble': {
                'co': [
                    lambda: self.check_in_flags('buble')
                ],
                'do': self.buble_out,
                'tm': None,
                'iv': 200,
                'pr': 200
            }
        }
        
        self.actions = dict(actions, **self.actions)  # Настройки действий
        
        Mine.add_notify(Mine)
        
        Space.__init__(self, _role)
        
        notepad = _note.get_notepad()
        
        # Если в блокноте нет папки Places, создаем
        if not notepad.AlreadyExists('F', 'Places'):
            notepad.AddNote(0, 'F', 'Places')
        
        self.in_init_place_flag = False
        
        self.busy_jets = {}
        self.busy_owner = {}
    
    # region Функции
    
    # Получить места копки
    def get_mine_places(self):
        if not self.check_in_inflight():
            return False
        
        bp = sm.GetService('michelle').GetBallpark()
        
        if not bp:
            return False
        
        sensorSuite = sm.GetService('sensorSuite')
        handler = sensorSuite.siteController.GetSiteHandler(ANOMALY)
        
        # Добавляем гравики
        for k, v in handler.GetSites().items():
            if v.scanStrengthAttribute == const.attributeScanGravimetricStrength:
                if not Place.get_place_by_id(v.siteID):
                    if v.dungeonNameID in cnt.groupIce:
                        _type = 'ice'
                    elif v.dungeonNameID in cnt.groupGravics:
                        _type = 'ore'
                    else:
                        _type = None
                    
                    if _type:
                        Place.add_place(AnomalePlace(v.siteID, v.GetName(), v.position, _type, v))
        
        # Добавляем белты
        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.groupID == const.groupAsteroidBelt and not Place.get_place_by_id(ball_id):
                Place.add_place(BeltPlace(ball.id, slim.name, (ball.x, ball.y, ball.z)))
        
        return True
    
    # Получить трюм для руды, если нет то простой трюм
    def get_ore_cargo(self):
        if bool(get_attr(util.GetActiveShip(), const.attributeSpecialOreHoldCapacity)):
            return invCtrl.ShipOreHold(util.GetActiveShip())
        else:
            return invCtrl.ShipCargo()
    
    # Получить личный ангар на посе
    def get_pos_hungar(self, name, div):
        bp = sm.GetService('michelle').GetBallpark(True)
        
        for ball_id, ball in bp.balls.items():
            
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.categoryID == 23 and slim.name == name:
                for x in range(7):
                    worker = invCtrl.POSCorpHangar(slim.itemID, x)
                    
                    if worker and worker.GetName() == div and worker.CheckCanQuery() and worker.CheckCanTake():
                        return worker
        
        return None
    
    def jets_in_space(self):
        bp = sm.GetService('michelle').GetBallpark()
        
        if not bp:
            return True
        
        j_owns = [x['id'] for x in bot.bots.values()]
        
        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.typeID == const.typeCargoContainer and slim.ownerID in j_owns:
                return True
        
        return False
    
    # Выбираем контейнер в космосе, in_lock - включать залоченные, in_target - включать по которым работают бимы
    def get_jet_in_space(self, in_lock=True, in_target=True):
        bp = sm.GetService('michelle').GetBallpark(True)
        
        j_owns = [x['id'] for x in bot.bots.values()]
        
        jsa = []  # Все контейнеры
        
        if self.role == 'collector':
            jetIDs = {}
            
            for jet in self.jets:
                jetIDs[jet['jet_id']] = jet['date']
        
        for ball_id, ball in bp.balls.items():
            slim = bp.GetInvItem(ball_id)
            
            if slim and slim.typeID == const.typeCargoContainer and slim.ownerID in j_owns:
                
                if not in_lock:
                    target = sm.GetService('target')
                    
                    # Пропускаем, если джет уже залочен или лочится
                    if target.IsTarget(ball_id) or ball_id in target.GetTargeting():
                        continue
                
                if not in_target:
                    tractors = self.get_modules(const.groupTractorBeam)
                    in_targets = [self.get_target_id(x) for x in tractors]
                    
                    if ball_id in in_targets:
                        continue
                
                if self.role == 'collector':
                    if ball_id in jetIDs:
                        if self.check_in_flags('collect') or dt.now() - jetIDs[ball_id] >= datetime.timedelta(
                                minutes=3):
                            jsa += [(jetIDs[ball_id], ball)]
                    
                    elif self.check_in_flags('collect'):
                        # self.warn('Неучтенный контейнер {}'.format(ball_id), self.role)
                        
                        jsa += [(dt.now(), ball)]
                
                else:
                    jsa += [(ball.surfaceDist, ball)]
        
        if jsa:
            jsa.sort()
            return jsa[0][1]
        
        return None
    
    def jet_is_busy(self, jetID, lock=True, owner=None):
        
        rec = {'type': 'jet_status', 'jet_id': jetID, 'lock': lock}
        ans = j_get_far('ruller', rec)
        
        if ans != 'error':
            return ans == 'busy'
        
        return False
    
    def jet_free(self, jetID):
        
        rec = {'type': 'jet_free', 'jet_id': jetID}
        j_send_far('ruller', rec)
    
    # endregion
    
    # region Методы
    
    # Заполнение гравиков и белтов
    def init_places(self):
        pause(500)
        
        if self.in_init_place_flag:
            return
        
        self.info('Инициализация мест добычи ресурсов', self.role)
        
        if self.check_in_station():
            self.in_init_place_flag = True
            
            self.undocking()
        
        if self.check_in_inflight():
            self.in_init_place_flag = True
            
            self.get_mine_places()
            self.info('Получили список гравиков и белтов', self.role)
            
            # Очищаем устаревшие заметки о местах добычи
            notes = _note.get_notes('Places')
            
            places = []
            
            for place in cnt.places.values():
                if place.type == 'anomaly':
                    places.append(place.name)
            
            for note in notes:
                if 'Belt' in note.label:
                    lines = note.text.split('<br>')
                    
                    if lines:
                        date = dt.strptime(str(lines[0]), '%Y-%m-%d %H:%M:%S')
                        
                        if date < get_last_dt():
                            _note.del_note(note.label, 'Places')
                else:
                    if note.label not in places:
                        _note.del_note(note.label, 'Places')
            
            # Очищаем устаревшие закладки
            bms = _bm.get_bookmarks('Places')
            
            for bm in bms:
                if 'Belt' in bm.memo:
                    if util.BlueToDate(bm.created) < get_last_dt():
                        _bm.del_bookmark(bm.memo.strip(), 'Places')
                else:
                    if not bm.memo.strip() in places:
                        _bm.del_bookmark(bm.memo.strip(), 'Places')
            
            self.del_flag('init')
            
            if self.role == 'miner':
                current = Place.get_current()
                
                if not current or current.type not in ['anomaly', 'belt']:
                    self.add_flag('need_crystall')
            
            self.in_init_place_flag = False
            
            self.run_action()
    
    # Вытапливание из бубля
    def buble_out(self):
        buble = self.in_bubble()
        
        if buble:
            bp = sm.GetService('michelle').GetBallpark(True)
            
            if bp.GetBallById(util.GetActiveShip()).followId != buble.id:
                
                slim = bp.GetInvItem(buble.id)
                
                if slim:
                    radius = get_type_attr(slim.typeID, const.attributeWarpScrambleRange) + 1000
                    
                    self.info('Вытапливаем из бубля {}'.format(slim.itemID), self.role)
                    
                    do_action(3 + rnd_keys())
                    
                    movementFunctions.Orbit(buble.id, radius)
        else:
            if self.check_in_flags('buble'):
                self.info('Вытопили из бубля', self.role)
                
                self.del_flag('buble')
                
                self.run_action()
    
    # Выход из игры, если пришло время downtime
    def downtime(self):
        if session.stationid:
            do_action(2 + rnd_keys())
            
            stackless.tasklet(bot.quit.run)()
    
    # endregion
    
    # Появилось окно ДТ, проверяем время и если необходимо выставляем флаг downtime
    def OnDownTime(self):
        if not self.is_ready: return
        
        if is_downtime() and not self.check_in_flags('downtime'):
            self.add_flag('downtime')
            
            self.run_action()
    
    # Приварп
    def OnWarpFinished(self, *args):
        if not self.is_ready: return
        
        if self.check_in_buble():
            self.add_flag('buble')
        
        current = Place.get_current()
        
        if not current or current.type not in ['anomaly', 'belt']:
            # uthread.new(self.protect_mod_off)
            stackless.tasklet(self.protect_mod_off)()
        
        Space.OnWarpFinished(self, *args)
    
    def OnViewStateChanged(self, old_state, new_state):
        if not self.is_ready: return
        
        if old_state == 'hangar' and new_state == 'inflight':
            self.in_init_place_flag = False
        
        Space.OnViewStateChanged(self, old_state, new_state)
    
    def OnWindowOpened(self, wnd):
        Space.OnWindowOpened(self, wnd)
        
        if wnd.__guid__ == 'form.HybridWindow':
            msg = wnd.name.encode('utf-8')
            
            self.warn('Открыто окно: {}'.format(msg), self.role)
            
            if msg == 'Задать количество':
                wnd.Close()
