# Прерывает работу всех скриптов


def run():
    sm.ScatterEvent('OnScriptPause')
