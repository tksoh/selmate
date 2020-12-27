#
# Copyright 2020 TK Soh <teekaysoh@gmail.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2, incorporated herein by reference.
#

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


def get_wait(spec):
    if type(spec) is int:
        return spec
    elif spec == '':
        return 0

    arr = re.split(r'[e\s]+', spec.strip())
    if len(arr) == 2:
        start, stop = arr
    elif len(arr) == 1:
        start = arr[0]
        stop = 0
    else:
        return 0

    wait_time = WaitValue(start, stop).value()
    return wait_time


def dict_gets(d, keys, default=None):
    for k in keys:
        if k in d:
            return d[k]
    return default