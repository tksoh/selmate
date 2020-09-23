import time
import types
import utils
from utils import WaitValue
from PyQt5.QtCore import QObject, pyqtSignal


def getvalue(foo):
    if isinstance(foo, types.FunctionType):
        return foo()
    else:
        return foo


class Action(QObject):
    info = pyqtSignal(str, str)

    def __init__(self, func, name='unknown',
                 cond=None, whentrue=None, whenfalse=None, initwait=None):
        super().__init__()
        self.func = func
        self.name = name
        self.cond = cond
        self.whentrue = whentrue
        self.whenfalse = whenfalse
        self.initwait = initwait

    def run(self):
        self.show_status()

        if self.cond and not self.cond():
            return

        if isinstance(self.initwait, WaitValue):
            wait_time = self.initwait.value()
        elif self.initwait:
            wait_time = self.initwait
        else:
            wait_time = 0

        self.info.emit('initwait', str(wait_time))
        time.sleep(wait_time)

        rv = self.func()
        if self.whentrue and rv:
            self.whentrue()
        elif self.whenfalse and not rv:
            self.whenfalse()

    def show_status(self):
        try:
            start, stop = self.initwait.range()
            initwait = f'{start}~{stop}'
        except AttributeError:
            initwait = self.initwait
        self.info.emit('status', f'Running action: "{self.name}". Initwait = {initwait} ')


class ActionList:
    def __init__(self):
        self.actionlist = []
        pass

    def add(self, func, name='unknown', cond=None, whentrue=None,
            whenfalse=None, initwait=None):
        action = Action(func, name, cond, whentrue, whenfalse, initwait)
        self.actionlist.append(action)

    def connect(self, handler):
        for act in self.actionlist:
            act.info.connect(handler)

    def run(self):
        for act in self.actionlist:
            act.run()
