# Скрипт выгрузки истории в текущем регионе

import util
import uthread
import datetime

from ibot.utils import *
from ibot.utils import progress
from ibot.mac import Macros


def run():
    if not hasattr(sm.bot, 'export_history'):
        sm.bot.export_history = ExportHistory()


class ExportHistory(Macros):

    __notifyevents__ = [
    ]

    # Инициализация класса
    def __init__(self):
        Macros.__init__(self)

        self.info = sm.bot.log.info
        self.info('Запуск export_history', 'export_history')

        self.all_items = 0
        self.count_items = 0

        uthread.new(self.__action)

    # Уничтожение класса
    def __deinit__(self):
        self.info('Остановка export_history', 'export_history')

        Macros.__deinit__(self)

        del sm.bot.export_history

    # Основной метод скрипта
    def __action(self):
        p = progress.Progress()

        type_ids = sm.bot.trade.get_type_ids()

        self.all_items = len(type_ids)
        self.count_items = len(type_ids)

        p.start(len(type_ids), 10)

        query = "select max(history_date) from trade_histories where type_id = %s"
        date = datetime.datetime.now()

        c = 0

        try:
            for _id in type_ids:
                p.tick()

                self.count_items -= 1

                c += 1

                if c == 100:
                    c = 0
                    print str(self.all_items) + ' / ' + str(self.count_items)

                params = [_id]

                last_date = sm.bot.db.select(query, params)

                if not last_date[0][0] is None:
                    if (last_date[0][0] - date) < datetime.timedelta(days=1):
                        continue

                if poe(self):
                    return

                rand_pause()

                self._export_history_by_type(_id)
        except Exception as e:
            print 'export_history.__action: ' + str(e)
            print _id

        sm.ScatterEvent('OnExportHistoryFinished')

        self.__deinit__()

    # Выгружаем историю указанного товара в текущем регионе за последние deep дней
    @staticmethod
    def _export_history_by_type(type_id, deep=31):

        history = sm.GetService('marketQuote').GetPriceHistory(type_id)

        if abs(deep) > len(history) - 1:
            deep = 0
        elif deep > 0:
            deep *= -1

        history = history[deep:-1]

        history = [list(x) for x in history]

        for h in history:

            h[0] = util.FmtDate(h[0])

            h.insert(0, eve.session.regionid)
            h.insert(1, type_id)

        # Очищаем историю для текущего региона и товара
        query = "DELETE FROM trade_histories WHERE region_id = %s AND type_id = %s"
        sm.bot.db.query(query, (eve.session.regionid, type_id))

        history = [tuple(x) for x in history]

        # Сохраняем историю для текущего региона и товра
        query = "INSERT INTO trade_histories " \
                "(region_id, type_id, history_date, low_price, high_price, avg_price, volume, orders) " \
                "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)"
        sm.bot.db.query(query, history)