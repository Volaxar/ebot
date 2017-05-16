import math

import ibot.utils.profiler as profiler


class Progress():
    def __init__(self):
        self.all = None
        self.sep = None
        self.c = None
        self.csep = None
        
        self.p = profiler.Profiler()
    
    def start(self, _all, sep):
        self.all = _all
        self.sep = sep
        
        self.c = 0
        self.csep = 1
        
        self.p.update()
    
    def tick(self):
        if self.all < 100:
            return
        
        if self.c == self.all - 1:
            self.p.show('100% ')
            return
        elif self.c == int(math.ceil((float(self.all) / 100) * self.sep) * self.csep):
            self.p.show(str(self.sep * self.csep) + '% ')
            self.csep += 1
        
        self.c += 1
