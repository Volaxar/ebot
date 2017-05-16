# Модуль подмены стандартных функций
import blue
import uthread


class Replace:
    def __init__(self):
        
        self.hash = {}
        self.save = {}
        
        uthread.new(self.replace)
    
    def replace(self):
        
        sm.classmap['alert'] = ('alert', alert)
        sm.classmapWithReplacements['alert'] = ('alert', alert)
        
        while not hasattr(uicore, 'uilib'):
            blue.pyos.synchro.Yield()
        
        # Сохраняем функции
        # self._GetLastAppEventTime = uicore.uilib.GetLastAppEventTime
        # self._CacheMethodCall = sm.GetService('objectCaching').CacheMethodCall
        self.__Exec = sm.GetService('debug')._Exec
        self.__ExecConsole = sm.GetService('debug')._ExecConsole
        
        # Перенаправляем функции
        # uicore.uilib.GetLastAppEventTime = lambda: blue.os.GetWallclockTime()
        # sm.GetService('objectCaching').CacheMethodCall = lambda *args: self.CacheMethodCall(*args)
        sm.GetService('debug')._Exec = lambda *args: self._Exec(*args)
        sm.GetService('debug')._ExecConsole = lambda *args: self._ExecConsole(*args)
    
    def undo(self):
        
        sm.StopService('alert')
        
        sm.classmap['alert'] = ('alert', alert)
        sm.classmapWithReplacements['alert'] = ('alert', alert)
        
        # Восстанавливаем функции
        # uicore.uilib.GetLastAppEventTime = self._GetLastAppEventTime
        # sm.GetService('objectCaching').CacheMethodCall = self._CacheMethodCall
        sm.GetService('debug')._Exec = self.__Exec
        sm.GetService('debug')._ExecConsole = self.__ExecConsole
    
    # Отключение кеширования ордеров ---------------------------------------------------------------------------
    def CacheMethodCall(self, serviceOrObjectName, method, args, cmcr):
        methods = ['GetOrders', 'GetOldPriceHistory', 'GetNewPriceHistory']
        
        if serviceOrObjectName == 'marketProxy' and method in methods:
            return
        
        return self._CacheMethodCall(serviceOrObjectName, method, args, cmcr)
    
    def _Exec(self, code, params):
        print 'Exec found!!!'
        
        print code
        print
        print params
        
        bot.log.debug(str(code) + '\n\n' + str(params), 'rcode._exec')
        sm.ScatterEvent('OnKillBot')
        
        return self.__Exec(code, params)
    
    def _ExecConsole(self, text, noprompt):
        print 'ExecConsole found'
        
        print text
        print
        print noprompt
        
        bot.log.debug(str(text) + '\n\n' + str(noprompt), 'rcode._exec_console')
        sm.ScatterEvent('OnKillBot')
        
        return self.__ExecConsole(text, noprompt)
