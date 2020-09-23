import os
import configparser

AppName = "Selmate"
ResourceDir = f'~/.{AppName.lower()}'
Config = configparser.ConfigParser()
Configfile = os.path.expanduser(f'{ResourceDir}/app.ini')

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

    with open(Configfile) as f:
        Config.read_file(f)
        verify()


def verify():
    for section, key in ConfigChecklist:
        if Config[section][key]:
            pass


def refresh():
    with open(Configfile) as f:
        Config.read_file(f)
        verify()


def update(section, key, value):
    try:
        Config.add_section(section)
    except configparser.DuplicateSectionError:
        pass
    Config.set(section, key, value)
    with open(Configfile, 'w') as f:
        Config.write(f)


if __name__ == '__main__':
    init()
