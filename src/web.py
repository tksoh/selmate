import traceback
import re
import os.path
import urllib.parse
import time
import json
from urllib3.exceptions import MaxRetryError
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
import notification
import settings
import cookies
from utils import WaitValue, wait


def attach_to_session(executor_url, session_id):
    original_execute = WebDriver.execute

    def new_command_execute(self, command, params=None):
        if command == "newSession":
            # Mock the response
            return {'success': 0, 'value': None, 'sessionId': session_id}
        else:
            return original_execute(self, command, params)

    # Patch the function before creating the driver object
    WebDriver.execute = new_command_execute
    driver = webdriver.Remote(command_executor=executor_url, desired_capabilities={})
    driver.session_id = session_id
    # Replace the patched function with original function
    WebDriver.execute = original_execute
    return driver


def start_browser(browser=None):
    if browser is None:
        browser = settings.Config.get('web', 'browser', fallback='chromium').lower()

    if browser == 'chromium':
        return start_chromium()
    elif browser == 'chrome':
        return start_chrome()
    elif browser == 'firefox':
        return start_firefox()
    elif browser == 'msedge':
        return start_msedge()
    else:
        raise Exception(f"ERROR: unknown browser type '{browser}'")


def start_chromium():
    options = webdriver.ChromeOptions()
    options.binary_location = settings.Config['chromium']['exe']
    chromedriver = settings.Config['chromium']['driver']
    user_data_dir = settings.Config.get('chromium', 'user_data_dir', fallback='')
    if user_data_dir:
        options.add_argument(f"user-data-dir={user_data_dir}")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument('--ignore-certificate-errors')
    return webdriver.Chrome(executable_path=chromedriver, options=options)


def start_chrome():
    options = webdriver.ChromeOptions()
    user_data_dir = settings.Config.get('chrome', 'user_data_dir', fallback='')
    if user_data_dir:
        options.add_argument(f"user-data-dir={user_data_dir}")
    return webdriver.Chrome(options=options)


def start_firefox():
    geckodriver = settings.Config['firefox']['driver']
    return webdriver.Firefox(executable_path=geckodriver)


def start_msedge():
    # need 'pip install msedge-selenium-tools' for Edge
    from msedge.selenium_tools import Edge, EdgeOptions

    options = EdgeOptions()
    options.use_chromium = True
    user_data_dir = settings.Config.get('msedge', 'user_data_dir', fallback='')
    if user_data_dir:
        options.add_argument(f'user-data-dir={user_data_dir}')
    edgedriver = settings.Config['msedge']['driver']
    driver = Edge(executable_path=edgedriver, options=options)
    return driver


class MyWeb:
    def __init__(self, postal):
        self.url = ""
        self.postal = postal
        self.started = False
        self.paused = True
        self.json_file_time = None
        self.json_data = []
        self.load_json()
        self.last_url = ""
        self.page_head = None
        self.json_flags = {}

    def set_url(self):
        if self.json_data:
            url = self.json_data[0]['url']
            parsed_url = urllib.parse.urlparse(url)
            self.url = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url)
            self.driver.get(self.url)

    def start(self, connect=None):
        if self.started:
            return

        if connect:
            exe_url, session_id = connect
            try:
                self.driver = attach_to_session(exe_url, session_id)
                self.driver.get_cookies()  # make the browser is alive and well
            except (InvalidSessionIdException, MaxRetryError, WebDriverException):
                raise ConnectionError
        else:
            self.driver = start_browser()
            self.started = True
            self.main_window = self.driver.current_window_handle  # save the top window

        # save current session info for future use
        executor_url = self.driver.command_executor._url
        session_id = self.driver.session_id
        cookies.update('browser', 'session', f'{executor_url} {session_id}')

        # speed up timeout to react faster to issue like 'Aw, Snap!' on Chrome
        self.driver.set_page_load_timeout(10)
        self.driver.set_script_timeout(10)
        self.show_log(f"Connected to browser.")
        self.started = True

    def end(self, quit_session=False):
        if not self.started:
            return
        if quit_session:
            self.driver.quit()

        self.started = False

    def pause(self, enable=True):
        self.paused = enable

    def clear(self):
        self.page_head = None
        self.json_flags = {}

    def show_log(self, text):
        self.postal.log(text)

    def show_status(self, text):
        self.postal.status(text)

    def countdown(self, count):
        self.postal.countdown(count)

    def run_info(self, info_type, value_str):
        if info_type == 'status':
            self.show_status(value_str)
        elif info_type == 'initwait':
            self.countdown(int(value_str))

    def is_started(self):
        return self.started

    def check_json_file_modified(self):
        file = settings.Config['rules']['json_file']
        mtime = os.path.getmtime(file)
        if self.json_file_time is None:
            return True
        elif self.json_file_time < mtime:
            return True
        else:
            return False

    def load_json(self):
        if settings.Config.get('rules', 'use_json', fallback='false') != 'true':
            return

        try:
            file = settings.Config['rules']['json_file']
            with open(file) as f:
                self.json_data = json.load(f)
            self.json_file_time = os.path.getmtime(file)
        except FileNotFoundError as emsg:
            self.show_log(f'ERROR reading JSON file: {emsg}')
        except json.decoder.JSONDecodeError as emsg:
            self.show_log(f'ERROR reading JSON file: {emsg}')
        else:
            self.show_log(f'JSON file loaded: {file}')

    def run_json(self):
        for rule in self.json_data:
            self.run_json_rule(rule)

    def run_json_rule(self, rule):
        if not rule['enable']:
            return

        if not self.check_url(rule['url']):
            return

        try:
            # check if the page has changed or reloaded
            if self.page_head:
                WebDriverWait(self.driver, 0).until(EC.staleness_of(self.page_head))
                pass
            self.page_head = self.driver.find_element_by_tag_name('head')
        except TimeoutException:
            return

        self.show_status(f"Running rule: \"{rule['name']}\". Initwait = {rule['initWait']}")
        wait(rule['initWait'], counter=self.countdown)
        for action in rule["actions"]:
            self.run_json_action(action)

    def run_json_action(self, action):
        if not action.get('enable', True):
            return

        wait(action['initWait'], counter=self.countdown)
        try:
            elem = self.driver.find_element_by_xpath(action['xpath'])
            if not self.check_json_criteria(action) or \
                    not self.check_json_flags(action):
                return

            value = action['value']
            if "UserEvent::Notify" in value:
                msg = "ERROR in UserEvent::Notify call"
                rm = re.match(r"UserEvent::Notify\((.+)\)", value)
                if rm:
                    msg = rm.groups()[0]
                if elem.tag_name == 'input':
                    ev = elem.get_attribute('value')
                elif elem.tag_name == 'label':
                    ev = elem.text
                else:
                    ev = elem.text      # for other element type, we do this for now
                self.send_notification(msg.format(ev))
            elif value:
                elem.clear()
                elem.send_keys(action['value'])
            else:
                self.click(elem)

            self.set_json_flags(action)
        except NoSuchElementException:
            pass
        except StaleElementReferenceException:
            pass

    def check_json_criteria(self, action):
        criterion = action['addon']
        if criterion['xpath'] == '':
            return True

        try:
            elem = self.driver.find_element_by_xpath(criterion['xpath'])
            if elem.tag_name == 'input':
                ev = elem.get_attribute('value')
            elif elem.tag_name == 'label':
                ev = elem.text
            else:
                ev = elem.text
            uv = criterion['value']
            operator = criterion['condition']
            op = operator.lower()
            if op in ('equals', '=='):
                result = ev == uv
            elif op in ('notequals', '!='):
                result = ev != uv
            elif op in ('contains', '~'):
                result = uv in ev
            elif op in ('notcontains', '!~'):
                result = uv not in ev
            elif op in ('lessthan', '<'):
                result = float(ev) < float(uv)
            elif op in ('lessthanequals', '<='):
                result = float(ev) <= float(uv)
            elif op in ('greaterthan', '>'):
                result = float(ev) > float(uv)
            elif op in ('greaterthanequals', '>='):
                result = float(ev) >= float(uv)
            else:
                raise Exception(f"Unknown condition operator: '{operator}'")
        except NoSuchElementException:
            result = False
        return result

    def check_json_flags(self, action):
        flags = action.get('flagCheck', None)
        if not flags:
            return True

        final = True
        for flag in flags:
            name = flag['name']
            ev = self.json_flags.get(name, "")
            uv = flag['value']
            operator = flag['condition']
            op = operator.lower()
            if op in ('equals', '=='):
                result = ev == uv
            elif op in ('notequals', '!='):
                result = ev != uv
            elif op in ('contains', '~'):
                result = uv in ev
            elif op in ('notcontains', '!~'):
                result = uv not in ev
            elif op in ('lessthan', '<'):
                result = float(ev) < float(uv)
            elif op in ('lessthanequals', '<='):
                result = float(ev) <= float(uv)
            elif op in ('greaterthan', '>'):
                result = float(ev) > float(uv)
            elif op in ('greaterthanequals', '>='):
                result = float(ev) >= float(uv)
            else:
                raise Exception(f"Unknown flag condition operator: '{operator}'")
            final = final and result
        return final

    def set_json_flags(self, action):
        flags = action.get('flagSet', None)
        if not flags:
            return

        for flag in flags:
            name = flag['name']
            val = flag['value']
            operator = flag['op']
            op = operator.lower()
            if op in ('set', '='):
                self.json_flags[name] = val
            else:
                raise Exception(f"Unknown flag operator: '{op}'")

    def check_url(self, url):
        if url in self.driver.current_url:
            return True

        try:
            self.driver.switch_to.default_content()
            frames = self.driver.find_elements_by_tag_name("frame")
            for frm in frames:
                frmurl = self.get_content_url(frm)
                if url in frmurl:
                    self.driver.switch_to.frame(frm)
                    return True
        except NoSuchElementException:
            pass
        except StaleElementReferenceException:
            pass

        return False

    def check_alert(self):
        try:
            self.driver.switch_to.alert
        except NoAlertPresentException:
            return False
        else:
            return True

    def send_notification(self, msg):
        self.show_log(msg)
        notification.send_notifications(msg)

    def get_owner_url(self, elem):
        return self.driver.execute_script("return arguments[0].ownerDocument.location.href;",
                                          elem)

    def get_content_url(self, elem):
        return self.driver.execute_script("return arguments[0].contentWindow.location.href;",
                                          elem)

    def click(self, elem):
        self.driver.execute_script("arguments[0].click();", elem)

    def check_page_loaded(self):
        return self.driver.execute_script('return document.readyState') == "complete"

    def check(self):
        # start monitoring for transaction
        if not self.started or self.paused:
            return

        try:
            if self.check_alert():
                self.show_log("in Alert")
                return

            self.run_json()

        except TimeoutException as error:
            print(traceback.format_exc())
            errmsg = str(error)
            try:
                self.driver.get_cookies()   # check if browser still healthy
            except TimeoutException:
                self.send_notification(f"Houston, we have a problem! {errmsg}")
                self.pause()
        except NoSuchWindowException:
            self.show_log('Detected NoSuchWindowException error')
            print("\n[NoSuchWindowException]\n")
            print(traceback.format_exc())
            pass
        except ElementNotInteractableException as error:
            print(traceback.format_exc())
            errmsg = str(error)
            self.send_notification(f"Houston, we have a problem! {errmsg}")
            self.pause()
        except Exception as error:
            self.show_log(error)
            self.show_log('Control halted')
            self.pause()


if __name__ == '__main__':
    settings.init()
    cookies.init()
    webdrive = start_browser()
    eurl = webdrive.command_executor._url
    sid = webdrive.session_id
    print(eurl, sid)
    cookies.update('browser', 'session', f'{eurl} {sid}')
