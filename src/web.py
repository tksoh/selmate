#
# Copyright 2020 TK Soh <teekaysoh@gmail.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2, incorporated herein by reference.
#

import sys
import traceback
import re
import os.path
import urllib.parse
import time
import json
import threading
from urllib3.exceptions import MaxRetryError
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementNotInteractableException,
    InvalidSessionIdException,
    NoAlertPresentException,
    NoSuchElementException,
    NoSuchWindowException,
    SessionNotCreatedException,
    StaleElementReferenceException,
    WebDriverException,
    TimeoutException as SeleniumTimeoutException,
)

import notification
import settings
import cookies
from utils import get_wait, dict_gets


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
        browser_config = settings.Config.get('web', 'browser', fallback='chrome').lower()
        browser = settings.Config.get(browser_config, 'browser', fallback='chrome').lower()

    if browser == 'chromium':
        return start_chromium(browser_config)
    elif browser == 'chrome':
        return start_chrome(browser_config)
    elif browser == 'firefox':
        return start_firefox(browser_config)
    elif browser == 'msedge':
        return start_msedge(browser_config)
    elif browser == 'opera':
        return start_opera(browser_config)
    else:
        raise Exception(f"ERROR: unknown browser config '{browser}'")


def start_chromium(browser_config):
    options = webdriver.ChromeOptions()
    options.binary_location = settings.Config[browser_config]['exe']
    chromedriver = settings.Config[browser_config]['driver']
    user_data_dir = settings.Config.get(browser_config, 'user_data_dir', fallback='')
    if user_data_dir:
        options.add_argument(f"user-data-dir={user_data_dir}")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument('--ignore-certificate-errors')
    return webdriver.Chrome(executable_path=chromedriver, options=options)


def start_chrome(browser_config):
    options = webdriver.ChromeOptions()
    chromedriver = settings.Config[browser_config]['driver']
    user_data_dir = settings.Config.get(browser_config, 'user_data_dir', fallback='')
    if user_data_dir:
        options.add_argument(f"user-data-dir={user_data_dir}")
    return webdriver.Chrome(executable_path=chromedriver, options=options)


def start_firefox(browser_config):
    geckodriver = settings.Config[browser_config]['driver']
    return webdriver.Firefox(executable_path=geckodriver)


def start_IE(browser_config):
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    cap = DesiredCapabilities.INTERNETEXPLORER.copy()
    cap['INTRODUCE_FLAKINESS_BY_IGNORING_SECURITY_DOMAINS'] = True
    driver = settings.Config[browser_config]['driver']
    return webdriver.Ie(executable_path=driver, capabilities=cap)


def start_msedge(browser_config):
    # need 'pip install msedge-selenium-tools' for Edge
    from msedge.selenium_tools import Edge, EdgeOptions

    options = EdgeOptions()
    options.use_chromium = True
    user_data_dir = settings.Config.get(browser_config, 'user_data_dir', fallback='')
    if user_data_dir:
        options.add_argument(f'user-data-dir={user_data_dir}')
    edgedriver = settings.Config[browser_config]['driver']
    driver = Edge(executable_path=edgedriver, options=options)
    return driver


def start_opera(browser_config):
    # options = webdriver.opera.options.Options
    # options.binary_location =
    operadriver = settings.Config[browser_config]['driver']
    driver = webdriver.Opera(executable_path=operadriver)
    return driver


class MyWeb:
    def __init__(self, postal):
        self.url = ""
        self.postal = postal
        self.started = False
        self.paused = True
        self.rule_file_mtime = None
        self.rule_data = []
        self.load_rules()
        self.last_url = ""
        self.page_head = None
        self.rule_flags = {}
        self.current_rule = ""
        self.current_action = ""
        self.current_action_index = -1

    def set_url(self):
        if self.rule_data:
            url = self.rule_data[0]['url']
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
        self.rule_flags = {}

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

    def check_rule_file_modified(self):
        file = settings.Config['rules']['json_file']
        mtime = os.path.getmtime(file)
        if self.rule_file_mtime is None:
            return True
        elif self.rule_file_mtime < mtime:
            return True
        else:
            return False

    def load_rules(self):
        try:
            file = settings.Config['rules']['json_file']
            self.show_log(f'Loading JSON file \'{file}\'')
            with open(file) as f:
                self.rule_data = json.load(f)
            self.rule_file_mtime = os.path.getmtime(file)
        except FileNotFoundError as emsg:
            self.show_log(f'ERROR reading JSON file: {emsg}')
            return False
        except json.decoder.JSONDecodeError as emsg:
            self.show_log(f'ERROR reading JSON file: {emsg}')
            return False
        else:
            self.show_log(f'JSON file loaded')

        return True

    def process_rules(self):
        for rule in self.rule_data:
            self.run_rule(rule)

    def check_page_changed(self):
        # check if the page has changed or reloaded
        if not self.page_head:
            return True

        try:
            hd = self.driver.find_element_by_tag_name('head')
        except NoSuchElementException:
            return True
        except SeleniumTimeoutException:
            return True

        if hd == self.page_head:
            return False
        else:
            return True

    def wait_in_page(self, spec):
        def check_page():
            while self.keep_wait:
                if self.check_page_changed():
                    self.keep_wait = False
                    wait_event.set()
                time.sleep(0.5)

        wait_time = get_wait(spec)
        if not wait_time:
            return

        # start waiting until page changed
        checker = threading.Thread(target=check_page)
        wait_event = threading.Event()
        self.countdown(str(wait_time))
        self.keep_wait = True
        checker.start()
        wait_event.wait(wait_time)
        self.countdown("0")

        # stop the page changed check
        self.keep_wait = False
        checker.join()

    def run_rule(self, rule):
        self.current_rule = rule.get('name', '(unknown)')

        if not rule['enable']:
            return

        if not self.check_url(rule['url']):
            return

        if self.check_page_changed():
            self.page_head = self.driver.find_element_by_tag_name('head')
        else:
            return

        self.show_status(f"Running Rule: '{rule['name']}'. Initwait: {rule['initWait']}")
        self.wait_in_page(rule['initWait'])
        for idx, action in enumerate(rule["actions"]):
            self.current_action = action.get('name', '(unknown)')
            self.current_action_index = idx
            self.show_status(f"Running Rule: '{rule['name']}'. Initwait: {rule['initWait']} "
                             f"[Action #{idx}: '{self.current_action}'. Initwait: {action['initWait']}]")
            self.run_action(action)

    def run_action(self, action):
        if not action.get('enable', True):
            return

        if self.check_page_changed():
            return

        self.wait_in_page(action['initWait'])
        if self.check_page_changed():
            return

        try:
            xpath = dict_gets(action, ('xpath', 'elementFinder'))
            elem = self.driver.find_element_by_xpath(xpath)
            if not self.check_criteria(action) or \
                    not self.check_flags(action):
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
                if elem.tag_name == 'input' and elem.get_attribute('type') == 'text':
                    elem.send_keys(Keys.ENTER)
                else:
                    self.click(elem)

        except NoSuchElementException:
            pass
        except StaleElementReferenceException:
            pass
        except ElementNotInteractableException:
            pass
        except SeleniumTimeoutException:
            self.show_log('Except SeleniumTimeoutException')
            pass

    def check_criteria(self, action):
        try:
            criterion = action['addon']
            xpath = dict_gets(criterion, ('xpath', 'elementFinder'))
            if not xpath:
                return True

            uv = criterion['value']
            operator = criterion['condition']
        except KeyError as error:
            raise Exception(f"Missing key in addon: '{error}'")

        try:
            elem = self.driver.find_element_by_xpath(xpath)
            if elem.tag_name == 'input':
                ev = elem.get_attribute('value')
            elif elem.tag_name == 'label':
                ev = elem.text
            else:
                ev = elem.text
            op = operator.lower()
            if op in ('equals', '=='):
                result = ev == uv
            elif op in ('notequals', '!='):
                result = ev != uv
            elif op in ('contains', '@'):
                result = uv in ev
            elif op in ('notcontains', '!@'):
                result = uv not in ev
            elif op in ('search', '~'):
                result = re.search(uv, ev) is not None
            elif op in ('notsearch', '!~'):
                result = re.search(uv, ev) is None
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

    def check_flags(self, action):
        flag = action.get('flag', None)
        if not flag:
            return True

        result = self.evaluate_flag(flag)
        return result

    def evaluate_flag(self, flag):
        try:
            name = flag['name']
            uv = flag['value']
            operator = flag['condition']
        except KeyError as error:
            raise Exception(f"Missing key in flagCheck: '{error}'")

        op = operator.lower()
        ev = self.rule_flags.get(name, "")
        if not name:
            result = True
        elif op in ('equals', '=='):
            result = ev == uv
        elif op in ('notequals', '!='):
            result = ev != uv
        elif op in ('contains', '@'):
            result = uv in ev
        elif op in ('notcontains', '!@'):
            result = uv not in ev
        elif op in ('search', '~'):
            result = re.search(uv, ev) is not None
        elif op in ('notsearch', '!~'):
            result = re.search(uv, ev) is None
        elif op in ('lessthan', '<'):
            result = float(ev) < float(uv)
        elif op in ('lessthanequals', '<='):
            result = float(ev) <= float(uv)
        elif op in ('greaterthan', '>'):
            result = float(ev) > float(uv)
        elif op in ('greaterthanequals', '>='):
            result = float(ev) >= float(uv)
        else:
            raise SyntaxError(f"Unknown flag condition operator: '{operator}'")

        if 'and' in flag and 'or' in flag:
            raise SyntaxError(f"flag only allows either 'and' or 'or', not both")

        if 'and' in flag:
            result2 = self.evaluate_flag(flag['and'])
            result = result and result2

        if 'or' in flag:
            result2 = self.evaluate_flag(flag['or'])
            result = result or result2

        self.set_flags(flag, result)
        return result

    def set_flags(self, flag, cond):
        dotype = 'true' if cond else 'false'
        todo_list = flag.get(dotype, None)
        if todo_list is None:
            return

        for todo in todo_list:
            name = todo['name']
            val = todo['value']
            operator = todo['op']
            op = operator.lower()
            if not name:
                pass
            elif op in ('set', '='):
                self.rule_flags[name] = val
            elif op in ('decr', '-='):
                oldval = float(self.rule_flags[name])
                newval = float(val)
                self.rule_flags[name] = str(oldval - newval)
            elif op in ('incr', '+='):
                oldval = float(self.rule_flags[name])
                newval = float(val)
                self.rule_flags[name] = str(oldval + newval)
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

    def show_rule_info(self):
        self.show_log(f"  Rule: '{self.current_rule}'")
        self.show_log(f"  Action: [{self.current_action_index}] '{self.current_action}'")

    def check(self):
        # start monitoring for transaction
        if not self.started or self.paused:
            return

        try:
            if self.check_alert():
                self.show_log("in Alert")
                return

            self.show_status('Running...')
            self.process_rules()

        except SeleniumTimeoutException as error:
            self.show_log("TIMEOUT when running rules!")
            self.show_rule_info()
            self.show_log(traceback.format_exc())
            errmsg = str(error)
            try:
                self.driver.get_cookies()   # check if browser still healthy
                self.page_head = None
            except SeleniumTimeoutException:
                self.send_notification(f"Houston, we have a problem! {errmsg}")
                self.pause()
        except NoSuchWindowException:
            self.show_log('Detected NoSuchWindowException error')
            self.show_log(str(error))
            self.show_rule_info()
            self.show_log(traceback.format_exc())
        except ElementNotInteractableException as error:
            self.show_log('Detected ElementNotInteractableException error')
            self.show_log(str(error))
            self.show_rule_info()
            self.show_log(traceback.format_exc())
        except WebDriverException as error:
            self.show_log('Detected WebDriverException error')
            errmsg = str(error)
            self.show_log(errmsg)
            if '"code":-32000' in errmsg:
                self.show_log('known bug on Chromium <= v79')   # ignore Chrome webdriver known error
            else:
                self.show_rule_info()
                self.show_log(traceback.format_exc())
        except SyntaxError as error:
            self.show_log('Error in JSON file: ' + str(error))
            self.show_rule_info()
            self.show_log('Please fix and reload')
            self.pause()
        except Exception as error:
            self.show_log('Detected unhandled exception: ' + type(error).__name__)
            self.show_log(str(error))
            self.show_rule_info()
            self.show_log(traceback.format_exc())

if __name__ == '__main__':
    settings.init()
    cookies.init()
    try:
        webdrive = start_browser()
        eurl = webdrive.command_executor._url
        sid = webdrive.session_id
        print(eurl, sid)
        cookies.update('browser', 'session', f'{eurl} {sid}')
    except SessionNotCreatedException as error:
        print(f'ERROR when starting browser: {error}')
        sys.exit(1)
    except KeyError as error:
        print(f'ERROR when starting browser: undefined config {error}')
        sys.exit(1)
    except Exception as error:
        print(f'ERROR when starting browser: {error}')
        sys.exit(1)

