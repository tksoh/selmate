#
# Copyright 2020 TK Soh <teekaysoh@gmail.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2, incorporated herein by reference.
#

import os
import configparser

AppName = "Selmate"
ResourceDir = f'~/.{AppName.lower()}'
Config = configparser.ConfigParser()
Configfile = os.path.expanduser(f'{ResourceDir}/app.ini')
ConfigfileTime = None

ConfigChecklist = [
    # (section, option, requirement)
    ('web', 'browser', ()),
    ('email', 'sender', ('notification', 'email', 'yes')),
    ('email', 'password', ('notification', 'email', 'yes')),
    ('email', 'to', ('notification', 'email', 'yes')),
    ('media', 'soundtrack', ('notification', 'playsound', 'yes')),
    ('pushbullet', 'key', ('notification', 'pushbullet', 'yes')),
    ('notifyrun', 'channel', ('notification', 'notifyrun', 'yes')),
]


def init():
    try:
        os.mkdir(os.path.expanduser(ResourceDir))
    except FileExistsError:
        pass

    refresh()


def verify():
    for section, key, required in ConfigChecklist:
        if required:
            req_sec, rec_key, rec_val = required
            val = Config[req_sec][rec_key]
            if rec_val == val and Config[section][key]:
                pass
        elif Config[section][key]:
            pass


def refresh():
    global ConfigfileTime

    with open(Configfile) as f:
        Config.read_file(f)
        verify()
    ConfigfileTime = os.path.getmtime(Configfile)


def update(section, key, value):
    try:
        Config.add_section(section)
    except configparser.DuplicateSectionError:
        pass
    Config.set(section, key, value)
    with open(Configfile, 'w') as f:
        Config.write(f)


def check_file_modified():
    mtime = os.path.getmtime(Configfile)
    if ConfigfileTime is None:
        return True
    elif ConfigfileTime < mtime:
        return True
    else:
        return False


if __name__ == '__main__':
    init()
