def run():
    import blue
    import __builtin__
    
    if hasattr(__builtin__, 'bot'):
        sm.ScatterEvent('OnScriptBreak')
        
        while bot.macros:
            blue.pyos.synchro.SleepWallclock(100)
    
    if hasattr(uicore, 'cmd'):
        stackless.tasklet(uicore.cmd.CmdQuitGame)()
    else:
        import atexit
        
        atexit._run_exitfuncs()
        blue.os.Terminate(0)
