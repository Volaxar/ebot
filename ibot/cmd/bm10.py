def run():
    if bot.macros:
        self = bot.macros

        bot.change_args = {
            'ship_id': session.shipid,
            'flags': self.flags
        }

        bot.change_role('bm10')
