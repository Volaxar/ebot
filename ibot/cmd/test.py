import log
import geo2
import invCtrl, trinity, const, uthread, blue, util, math, uix, maputils, base, sys, form
import evetypes, datetime
import uiutil, localization, copy
import carbonui.const as uiconst
import eve.common.script.sys.eveCfg as eveCfg

from sensorsuite.overlay.sitetype import *

from datetime import datetime as dt

import ibot

import ibot.utils.bms as bms
import ibot.utils.note as _note
import ibot.utils.repl as repl

from ibot.utils import *
from ibot.utils import js
from ibot.utils import ja
from ibot.utils import npc
from ibot.utils import fly
from ibot.utils import setting
from ibot.utils import include

from ibot.utils.places import *
from ibot.mac import oldminer
from ibot.mac import miner
from ibot.mac import collector
from ibot.mac import agentrun
from ibot.mac import oldcrub
from ibot.mac import crub
from ibot.mac import fly_to
from ibot.mac import eyes
from ibot.mac import bonus
from ibot.mac import bm10

from ibot.utils import cnt
from ibot.utils import places
from ibot.mac.template import mine
from ibot.mac.template import oldspace
from ibot.mac.template import space
from ibot.mac.template import macros


def run():
    try:
        pass

        if True:
            if not bot.macros:
                print ed('TEST макрос не загружен')

                # reload(cnt)
                # reload(include)
                # reload(repl)
                # reload(fly)
                # reload(setting)
                # reload(places)
                # reload(js)
                # reload(ja)
                # reload(macros)
                reload(space)
                # reload(mine)
                # reload(miner)
                # reload(fly_to)
                # reload(collector)
                # reload(eyes)
                reload(crub)
                # reload(bm10)
                # reload(bonus)

                # print 'Start macros'

                # bot.macros = crub.Crub()
                # bot.macros = fly_to.FlyTo()

                # print 'Macros started'

                # set_bot_params('online', True)\

            else:
                print ed('TEST макрос загружен')

                self = bot.macros

                print self.places

                # drones = self.get_drones_in_bay()
                #
                # drones_list = self.drones
                #
                # for x in drones:
                #     if x.typeID in drones_list:
                #         if x.stacksize <= drones_list[x.typeID]:
                #             drones_list[x.typeID] -= x.stacksize
                #         else:
                #             del drones_list[x.typeID]
                #
                # if not drones_list:
                #     print 'Ok', drones_list
                # else:
                #     print 'Error', drones_list

        else:
            pass
            print '33333333'
            # lsc = sm.GetService('LSC')
            #
            # for channel in lsc.channels:
            #     print channel
            #
            # print session.solarsystemid2
            # drones = sm.GetService('michelle').GetDrones()

            # print drones

            # shipui = uicore.layer.shipui
            #
            # if shipui.isopen:
            #     modules = shipui.controller.GetModules()
            #
            #     for m in modules:
            #         print m

            # info = sm.GetService('godma').GetStateManager().GetShipType(typeID)

            # def get_npc_pirates():
            #     npc = localization.GetByLabel('UI/Services/State/NonPlayerCharacter/Generic')
            #     pirate = localization.GetByLabel('UI/Services/State/NonPlayerCharacter/Pirate')
            #     mission = localization.GetByLabel('UI/Services/State/NonPlayerCharacter/Mission')
            #
            #     return util.GetNPCGroups()[npc][pirate]

            # print  evetypes.GetName(23923)
            # info = sm.GetService('godma').GetStateManager().GetShipType(23923)
            # print cfg.dgmattribs.Get(134).attributeName, getattr(info, cfg.dgmattribs.Get(134).attributeName)

            # bp = sm.GetService('michelle').GetBallpark()
            # for ball_id, ball in bp.balls.items():
            #
            #     slim = bp.GetInvItem(ball_id)
            #
            #     if slim and slim.categoryID == 6 and slim.itemID != session.shipid:
            #         print slim

            #     if slim and (slim.groupID in get_npc_pirates() or slim.groupID == const.groupDestructibleSentryGun):
            #         info = sm.GetService('godma').GetStateManager().GetShipType(slim.typeID)
            #
            #         print cfg.dgmattribs.Get(636).attributeName, getattr(info, cfg.dgmattribs.Get(636).attributeName)

    except Exception as e:
        print 'exception test.run: ' + str(e)
