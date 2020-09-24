import time
import utils
from utils import WaitValue
from PyQt5.QtCore import QObject, pyqtSignal


class Rule(QObject):
    info = pyqtSignal(str, str)

    def __init__(self, identify, name='unknown', actions=None, initwait=None):
        super().__init__()
        self.actions = actions
        self.name = name
        self.identify = identify
        self.initwait = initwait

    def run(self):
        self.show_status()

        if not self.id():
            return

        wait_time = self.getinitval()
        self.info.emit('initwait', str(wait_time))
        time.sleep(wait_time)
        self.actions.run()

    def getinitval(self):
        if isinstance(self.initwait, WaitValue):
            return self.initwait.value()
        elif self.initwait:
            return self.initwait
        else:
            return 0

    def show_status(self):
        try:
            start, stop = self.initwait.range()
            initwait = f'{start}~{stop}'
        except AttributeError:
            initwait = self.initwait
        self.info.emit('status', f'Running rule: "{self.name}". Initwait = {initwait} ')


class Rules:
    def __init__(self):
        self.rules = []

    def add(self, identify, name='unknown', actions=None, initwait=None):
        rule = Rule(identify, name, actions, initwait)
        self.rules.append(rule)

    def connect(self, handler):
        for rule in self.rules:
            rule.info.connect(handler)
            if rule.actions:
                rule.actions.connect(handler)

    def run(self):
        for rule in self.rules:
            rule.run()
