# Embedded file name: carbon/common/script/sys\alert.py
# Заглушка для стандартного сервиса
from service import *


class Alert(Service):
    __guid__ = 'svc.alert'
    __displayname__ = 'Alert Service'
    __exportedcalls__ = {'Alert': [ROLE_SERVICE],
                         'SendSimpleEmailAlert': [ROLE_SERVICE],
                         'SendMail': [ROLE_SERVICE],
                         'SendProxyStackTraceAlert': [ROLE_SERVICE],
                         'SendClientStackTraceAlert': [ROLE_PLAYER],
                         'BeanCount': [ROLE_ANY],
                         'BeanDelivery': [ROLE_ANY],
                         'GroupBeanDelivery': [ROLE_ANY],
                         'GetCPULoad': [ROLE_SERVICE],
                         'LogModeChanged': [ROLE_SERVICE],
                         'GetLogModeForError': [ROLE_ANY]}
    __dependencies__ = []
    __notifyevents__ = []
    
    def Run(self, memStream=None):
        pass
    
    def Stop(self, stream):
        print 'Alert.Stop'
        Service.Stop(self, stream)
    
    def IsLiveCluster(self):
        print 'Alert.IsLiveCluster'
    
    def DbZCluster(self):
        print 'Alert.DbZClaster'
    
    def __GetMailServer(self):
        print 'Alert.__GetMailServer'
    
    def Alert(self, sender, subject, message, throttle=None, recipients=None, html=0, sysinfo=0, attachments=[]):
        print 'Alert.Alert'
    
    def GetSysInfo(self):
        print 'Alert.GetSysInfo'
    
    def BeanCount(self, stackIDHash, **kw):
        print 'Alert.BeanCount'
    
    def OnClusterStartup(self):
        print 'Alert.Run'
    
    def OnBeanPrime(self, beans):
        print 'Alert.OnClusterStartup'
    
    def ConvertFloodingGroupBeansToBeans(self, floodingErrors):
        print 'Alert.ConvertFloodingGroupBeansToBeans'
    
    def CompressGroupBeans(self, groupBeans):
        print 'Alert.CompressGroupBeans'
    
    def ExpandGroupBeans(self, compressedGroupBeans):
        print 'Alert.ExpandGroupBeans'
    
    def __BeanDeliveryBoy(self):
        print 'Alert.__BeanDeliveryBoy'
    
    def BeanDelivery(self, beans):
        print 'Alert.BeanDelivery'
    
    def GroupBeanDelivery(self, compressedGroupBeans, nodeID=None):
        print 'Alert.GroupBeanDelivery'
    
    def SendStackTraceAlert(self, stackID, stackTrace, mode, **kw):
        bot.log.warn('SendStackTraceAlert')
        
        print 'Alert.SendStackTraceAlert'
    
    def SendStackTraceAlert_thread(self, stackID, stackTrace, mode, kw):
        print 'Alert.SendStackTraceAlert_thread'
    
    def SendProxyStackTraceAlert(self, stackID, stackTrace, mode, **kw):
        print 'Alert.SendProxyStackTraceAlert'
    
    def SendClientStackTraceAlert(self, stackID, stackTrace, mode, nextErrorKeyHash=None):
        print 'Alert.SendClientStackTraceAlert'
    
    def __SendStackTraceAlert(self, stackID, stackTrace, mode, nodeID=None, userID=None, charID=None, locationID1=None,
                              locationID2=None, nextErrorKeyHash=None, origin=None):
        print 'Alert.__SendStackTraceAlert'
    
    def SendSimpleEmailAlert(self, message, recipients=None, subject=None, sysinfo=1, html=0, attachments=[],
                             subjectonly=0):
        print 'Alert.SendSimpleEmailAlert'
    
    def SendMail(self, *args, **kw):
        print 'Alert.SendMail'
    
    def __mailqueue(self):
        print 'Alert.__mailqueue'
    
    def GetCPULoad(self, seconds=300):
        print 'Alert.GetCPULoad'
    
    def _GetSessionInfo(self):
        print 'Alert._GetSessionInfo'
    
    def NotifyAllSolAndProxyOfLogModeChange(self, errorID, logMode):
        print 'Alert.NotifyAllSolAndProxyOfLogModeChange'
    
    def LogModeChanged(self, errorID, logMode):
        print 'Alert.LogModeChanged'
    
    def UpdateLogModes(self):
        print 'Alert.UpdateLogModes'
    
    def GetLogModeForError(self, errorIDs):
        print 'Alert.GetLogModeForError'
    
    def CheckAndExpireUserCounts(self):
        print 'Alert.CheckAndExpireUserCounts'
    
    def DoNastyLoggingTest(self, randomUser=False, maxLoops=500000, showProgress=False):
        print 'Alert.DoNastyLoggingTest'
    
    def __DoNastyErrorLogSimulation(self, randomUser=False, maxLoops=50000, showProgress=False):
        print 'Alert.__DoNastyErrorLogSimulation'
