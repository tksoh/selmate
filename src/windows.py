#
# Copyright 2020 TK Soh <teekaysoh@gmail.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2, incorporated herein by reference.
#

from PyQt5.QtGui import QIntValidator, QTextCursor, QFontMetrics
from PyQt5.QtWidgets import (
    QApplication, QDialog, QProgressBar,
    QPushButton, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QLineEdit, QMessageBox, QFrame, QCheckBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
import time
import sys
import re
import subprocess
from subprocess import Popen, PIPE
from datetime import datetime
from queue import Queue
from web import MyWeb
from settings import AppName
import settings
import cookies
from notification import notifyrun


def dprint(text):
    tm = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f'[{tm}] {text}')


class WebThread(QThread):
    def __init__(self, myweb):
        super().__init__()
        self.keepalive = True
        self.myweb = myweb

    def run(self):
        while True:
            self.myweb.check()
            time.sleep(0.1)


class QueueThread(QThread):
    receiver = pyqtSignal(str)

    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def run(self):
        while True:
            text = self.queue.get()
            self.receiver.emit(text)


class ProgQueueThread(QThread):
    receiver = pyqtSignal(str)

    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def run(self):
        while True:
            text = self.queue.get()
            self.receiver.emit(text)


class Postal(object):
    def __init__(self, win):
        self.window = win
        self.log_queue = win.log_queue
        self.status_queue = win.status_queue
        self.progress_queue = win.progress_queue
        self.notify_queue = win.notify_queue

    def log(self, text, timed=True):
        if timed:
            tm = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = f"[{tm}] {text}\n"
        else:
            msg = text

        self.log_queue.put(msg)
        self.notify_queue.put(msg)

    def status(self, text):
        self.status_queue.put(text)

    def countdown(self, seconds):
        self.progress_queue.put(f"{seconds}\n")


class Window(QDialog):
    log_queue = Queue()
    notify_queue = Queue()
    status_queue = Queue()
    progress_queue = Queue()

    def __init__(self):
        super().__init__()
        self.make_window()
        self.read_config()
        self.myweb = MyWeb(self.postal)
        self.update_connection_info()
        self.set_app_title()

    def read_config(self):
        try:
            settings.init()
            cookies.init()
        except KeyError as err:
            msg = f'ERROR: {err} is not defined in setting file'
            self.postal.log(msg)
            QMessageBox.warning(self, 'Setting Error', msg)
            return
        except FileNotFoundError as err:
            self.postal.log(f'ERROR openning ini file: {err}')

    def set_app_title(self):
        project = settings.Config.get('web', 'project', fallback='untitled')
        self.setWindowTitle(f"{AppName} [{project}]")

    def make_window(self):
        self.log_thread = QueueThread(self.log_queue)
        self.notify_thread = QueueThread(self.notify_queue)

        vbox = QVBoxLayout()
        self.setGeometry(400, 400, 500, 500)
        vbox.addWidget(QLabel("System log:"))
        self.syslog = QTextEdit()
        self.syslog.setReadOnly(True)
        vbox.addWidget(self.syslog)

        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        hbox.addWidget(QLabel("Initwait:"))
        self.progressbar = QProgressBar()
        self.progressbar.setMaximum(1000)
        self.progressbar.setValue(0)
        hbox.addWidget(self.progressbar)
        self.progressbar.setFormat('0/0')
        self.progressbar.setAlignment(Qt.AlignCenter)
        self.progress_enabled = False
        self.prog_max = 100
        self.prog_count = 0
        self.prog_queue_thread = ProgQueueThread(self.progress_queue)
        self.prog_queue_thread.receiver.connect(self.reset_progress_bar)
        self.prog_queue_thread.start()
        self.timer = QTimer()
        self.timer.timeout.connect(self.move_progress)

        hbox = QHBoxLayout()
        vbox.addWidget(QLabel("Browser Session:"))
        vbox.addLayout(hbox)
        self.connect_settings = QLineEdit("")
        hbox.addWidget(self.connect_settings)
        self.connect_button = QPushButton('Connect')
        hbox.addWidget(self.connect_button)
        self.new_browser_button = QPushButton('New')
        hbox.addWidget(self.new_browser_button)
        self.connect_button.clicked.connect(self.connect_browser)
        self.new_browser_button.clicked.connect(self.launch_browser)

        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        self.start_button = QPushButton('Start')
        self.start_button.clicked.connect(self.start_progress)
        self.start_button.setDisabled(True)
        self.stop_button = QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop_progress)
        self.stop_button.setDisabled(True)
        hbox.addWidget(self.start_button)
        hbox.addWidget(self.stop_button)
        self.setLayout(vbox)

        self.status_bar = QLabel()
        self.status_bar.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        vbox.addWidget(self.status_bar)
        self.status_thread = QueueThread(self.status_queue)
        self.status_thread.receiver.connect(self.status_update)
        self.status_thread.start()

        self.log_thread.receiver.connect(self.log)
        self.log_thread.start()
        self.notify_thread.receiver.connect(self.notify)
        self.notify_thread.start()

        self.postal = Postal(self)
        self.postal.status('Idle')

        self.show()

    def update_connection_info(self):
        try:
            cookies.refresh()
            info = cookies.Cookies['browser']['session']
            self.connect_settings.setText(info)
        except KeyError:
            pass

    def log(self, text):
        self.syslog.insertPlainText(text)
        self.syslog.moveCursor(QTextCursor.End)

    def status_update(self, text):
        fm = QFontMetrics(self.status_bar.font())
        elided = fm.elidedText(text, Qt.ElideRight, self.status_bar.width() - 10)
        self.status_bar.setText(elided)

    def notify(self, text):
        notifyrun(text)

    def start_progress_bar(self):
        self.set_progress_val(0)
        self.progress_enabled = True
        self.timer.start(1000)  # 1sec tick

    def start_progress(self):
        if not self.myweb.is_started():
            QMessageBox.warning(self, 'No Browser',
                                'Browser not nonnected/activated')
            return

        if settings.check_file_modified():
            reply = QMessageBox.question(self, 'Load INI',
                                         'INI file has been modified. Reload?',
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                settings.refresh()

        if self.myweb.check_json_file_modified():
            if self.myweb.json_data:
                msg = 'JSON file has been modified. Reload it?'
            else:
                msg = 'JSON file not loaded. Load it?'

            reply = QMessageBox.question(self, 'Load JSON', msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                if not self.myweb.load_json() and self.myweb.json_data:
                    self.postal.log("Continue with previously loaded JSON data")

        if self.myweb.json_data:
            self.myweb.clear()
            self.myweb.pause(False)
            self.web_thread = WebThread(self.myweb)
            self.web_thread.start()
            self.start_button.setDisabled(True)
            self.stop_button.setDisabled(False)
            self.update_connection_info()
            self.postal.log("Control started")
        else:
            self.postal.log("Unable to start. JSON data not loaded")

    def stop_progress_bar(self):
        self.progress_enabled = False
        self.timer.stop()

    def stop_progress(self):
        self.myweb.pause()
        self.web_thread.terminate()
        self.web_thread.wait()
        self.stop_progress_bar()
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)
        self.set_progress_val(0)
        self.postal.status('Idle')
        self.postal.log("Control stopped")

    def reset_progress_bar(self, text):
        assert int(text) <= 1000

        self.stop_progress_bar()
        self.prog_max = int(text)
        self.prog_count = self.prog_max
        self.start_progress_bar()
        self.set_progress_val(self.prog_max)

    def set_progress_val(self, val):
        maxcount = self.prog_max
        if maxcount > 0:
            steps = int(self.progressbar.maximum() / maxcount * val)
        else:
            steps = 0
        self.progressbar.setValue(steps)
        self.progressbar.setFormat(f'{val}/{maxcount}')

    def move_progress(self):
        if not self.progress_enabled:
            return

        # advance progress bar
        if self.prog_count > 0:
            self.prog_count -= 1
        self.set_progress_val(self.prog_count)

    def launch_browser(self):
        if self.myweb.is_started():
            reply = QMessageBox.question(self, 'Launch Browser',
                                         'Current session is still active. Relaunch?',
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        self.postal.log('starting new browser')
        cmd = [sys.executable, 'web.py']
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        with Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=False,
                   creationflags=flags) as proc:
            proc.wait()
            if proc.returncode:
                msg = str(proc.stdout.readline(), 'utf-8')
                self.postal.log(msg)
            else:
                self.update_connection_info()
                self.connect_browser()
                self.start_button.setDisabled(False)

    def connect_browser(self):
        if self.myweb.is_started():
            reply = QMessageBox.question(self, 'Connect Browser',
                                         'Current session is still active. Reconnect?',
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

            self.myweb.end()

        conn_string = self.connect_settings.text()
        rv = re.match(r"(http://\d+\.\d+\.\d+\.\d+:\d+)\s+([\w\-]+)", conn_string)
        if rv:
            exe_url, session_id = rv.groups()
            try:
                self.myweb.start([exe_url, session_id])
                self.update_connection_info()
                self.start_button.setDisabled(False)
            except ConnectionError:
                QMessageBox.warning(self, 'Connection Error',
                                    "Unable to connect. Please check to ensure remote session is active.")
        else:
            QMessageBox.warning(self, 'Connection Error', "Invalid connection setting. Please verify.")

    def closeEvent(self, event):
        if self.myweb.is_started():
            reply = QMessageBox.question(self, 'Close Application',
                                         'Browser session is active. Exit application?',
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.myweb.end()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def startwindow():
    app = QApplication(sys.argv)
    _window = Window()
    sys.exit(app.exec())
