def run():
    if bot.macros:
        if hasattr(bot.macros, 'last_flag'):
            bot.macros.last_flag = True
