import types
import random
import re
import time


class WaitValue:
    def __init__(self, a, b=0):
        self.start = int(a)
        self.stop = int(b)

    def value(self):
        if self.stop:
            return random.randint(self.start, self.stop)
        else:
            return self.start

    def range(self):
        return self.start, self.stop


def wait(spec, counter=None):
    if spec == "":
        return

    arr = re.split(r'[e\s]+', spec.strip())
    if len(arr) == 2:
        start, stop = arr
    elif len(arr) == 1:
        start = arr[0]
        stop = 0
    else:
        return

    wait_time = WaitValue(start, stop).value()
    if counter:
        counter(str(wait_time))
    time.sleep(wait_time)
