import datetime


class Profiler():
    def __init__(self):
        self.timeline = None
    
    def update(self):
        self.timeline = datetime.datetime.now()
    
    def show(self, before, after=''):
        _now = datetime.datetime.now()
        
        _str = before + ' | ' + str(_now - self.timeline) + ' : ' + after
        
        # if bot and bot.log:
        #     bot.log.info(_str, 'progress in:')
        # else:
        print 'progress in: {}'.format(_str)
        
        self.timeline = _now
