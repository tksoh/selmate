import os
import configparser

AppName = "Selmate"
ResourceDir = f'~/.{AppName.lower()}'
Config = configparser.ConfigParser()
Configfile = os.path.expanduser(f'{ResourceDir}/app.ini')
ConfigfileTime = None

ConfigChecklist = [
    ('chromium', 'exe'),
    ('chromium', 'driver'),
    ('chromium', 'user_data_dir'),
    ('email', 'sender'),
    ('email', 'password'),
    ('email', 'to'),
    ('media', 'soundtrack'),
    ('pushbullet', 'key'),
    ('notifyrun', 'channel'),
]


def init():
    try:
        os.mkdir(os.path.expanduser(ResourceDir))
    except FileExistsError:
        pass

    refresh()


def verify():
    for section, key in ConfigChecklist:
        if Config[section][key]:
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
