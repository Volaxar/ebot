import blue
import uthread

from ibot.utils import *


class Chat:
    def __init__(self, _id, _name):
        self.jid_admin = 'admin@172.20.0.3'
        
        self.ja_online = False
        
        self.channel_id = _id
        
        login = '{}__{}@172.20.0.3/EVE Chat'.format(bot.login.lower(), _name.lower())
        password = ''
        server = '172.20.0.3'
        port = '5222'
        
        try:
            jid = xmpp.protocol.JID(login)
            
            self.ja_client = xmpp.Client(jid.getDomain(), debug=[])
            
            if self.ja_client.connect(server=(server, port), secure=0):
                xmpp.features.register(self.ja_client, jid.getDomain(),
                                       {'username': jid.getNode(), 'password': password, 'name': jid.getNode()})
                self.ja_client.auth(user=jid.getNode(), password=password, resource=jid.getResource())
                
                self.ja_client.RegisterHandler('message', self.OnMessage)
                self.ja_client.RegisterHandler('presence', self.OnPresence)
                
                self.ja_client.sendInitPresence(requestRoster=1)
                
                self.ja_client.send(xmpp.Presence(to=self.jid_admin, typ='subscribe'))
                self.ja_client.send(xmpp.Presence(to=self.jid_admin, typ='available'))
                
                uthread.new(self.ja_process)
                
                self.ja_online = True
        except Exception as e:
            print 'except in chat.__init__: {}'.format(e)
    
    # отправка сообщений
    def ja_send(self, to, msg):
        try:
            self.ja_client.send(xmpp.protocol.Message(to, msg))
        except Exception as e:
            print 'except in chat.ja_send: {}'.format(e)
            self.ja_close()
    
    # Закрытие джа клиента
    def ja_close(self):
        if self.ja_online and self.ja_client:
            try:
                self.ja_client.send(xmpp.Presence(to=self.jid_admin, typ='unavailable'))
                
                self.ja_client.UnregisterHandler('message', self.OnMessage)
                self.ja_client.UnregisterHandler('presence', self.OnPresence)
                
                self.ja_client.disconnect()
            except Exception as e:
                print 'exception in chat.ja_close: {}'.format(e)
            finally:
                self.ja_online = 0
                self.ja_client = None
    
    # Рабочий процесс джа клиента
    def ja_process(self):
        
        while self.ja_online:
            try:
                self.ja_client.Process()
            except Exception as e:
                print 'exception in chat.ja_process: {}'.format(e)
                self.ja_close()
            
            blue.pyos.synchro.SleepWallclock(100)
    
    # Обработчик входящих сообщений
    def OnMessage(self, con, msg):
        try:
            if msg.getBody():
                wnd = sm.GetService('LSC').GetChannelWindow(self.channel_id)
                
                if wnd:
                    do_action(3 + rnd_keys(), 2 + rnd_keys() + len(msg.getBody()))
                    
                    wnd.input.SetValue(msg.getBody())
                    wnd.InputKeyUp()
        
        except Exception as e:
            print 'except in chat.OnMessage: {}'.format(e)
    
    def OnPresence(self, con, msg):
        who = msg.getFrom()
        type = msg.getType()
        
        if type == 'unsubscribe':
            self.ja_client.Roster.Unauthorize(who)
            self.ja_client.Roster.Unsubscribe(who)
        
        elif type == 'subscribe':
            self.ja_client.Roster.Subscribe(who)
            self.ja_client.Roster.Authorize(who)
