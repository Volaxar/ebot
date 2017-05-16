import __builtin__
import os
import sys
from datetime import datetime as dt

import base


def run():
    if not getattr(__builtin__, 'altout', None):
        setattr(__builtin__, 'altout', AltOut())


class AltOut:
    def __init__(self):
        self.std_file = None
        self.old_std = sys.stdout
        
        self.timer = base.AutoTimer(1000, self.flush)
    
    def set_out(self):
        try:
            if self.std_file is None:
                file_dir = 'd:\\temp\\eveout\\'
                
                char_name = None
                
                if eve.session.charid:
                    char_name = cfg.eveowners.Get(eve.session.charid).name
                
                subfolder = 'general'
                
                if char_name:
                    char_name = char_name.replace(' ', '_')
                    
                    subfolder = char_name
                
                day = dt.date(dt.now())
                
                if not os.path.exists(os.path.join(file_dir, subfolder)):
                    os.makedirs(os.path.join(file_dir, subfolder))
                
                self.std_file = open(os.path.join(file_dir, subfolder, '{}.log'.format(day)), 'a')
                
                sys.stdout = self.std_file
        except Exception as e:
            print e
    
    def ret_out(self):
        try:
            if self.std_file:
                self.timer = None
                
                sys.stdout = self.old_std
                
                self.std_file.close()
                self.std_file = None
        except Exception as e:
            print e
    
    def flush(self):
        try:
            if self.timer and self.std_file:
                self.std_file.flush()
        except Exception as e:
            print e
