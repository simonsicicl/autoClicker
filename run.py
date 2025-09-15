import ctypes
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)

from iClicker_driver import iClicker_driver as Driver

runner: Driver = Driver('config.json')
runner.start('XXXXXX')