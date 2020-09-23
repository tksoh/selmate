import os.path
import configparser
from settings import ResourceDir

Cookies = configparser.ConfigParser()
Cookiesfile = os.path.expanduser(f'{ResourceDir}/cookies.ini')


def init():
    refresh()


def refresh():
    try:
        with open(Cookiesfile) as f:
            Cookies.read_file(f)
    except FileNotFoundError:
        pass


def update(section, key, value):
    try:
        Cookies.add_section(section)
    except configparser.DuplicateSectionError:
        pass
    Cookies.set(section, key, value)
    with open(Cookiesfile, 'w') as f:
        Cookies.write(f)


if __name__ == '__main__':
    init()
    update('browser','session','xxx xxxx')
