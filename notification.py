import smtplib
import ssl
import threading
from playsound import playsound
from pushbullet import Pushbullet
from notify_run import Notify
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import settings
from settings import Config, AppName


def sendmail(msgbody, subject=f"[{AppName}] Alert!", forced=False):
    ini = Config.getboolean('notification', 'email', fallback=True)
    if not forced and not ini:
        return

    smtp_server = "smtp.gmail.com"
    port = 587  # For starttls
    context = ssl.create_default_context()

    password = Config['email']['password']
    sender = Config['email']['sender']
    tolist = Config['email']['to']
    cclist = Config.get('email', 'cc', fallback="")

    with smtplib.SMTP(smtp_server, port) as server:
        server.ehlo()  # Can be omitted
        server.starttls(context=context)
        server.ehlo()  # Can be omitted
        server.login(sender, password)

        rcpt = cclist.split(",") + [tolist]
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['To'] = tolist
        msg['Cc'] = cclist
        msg.attach(MIMEText(msgbody))
        server.sendmail(sender, rcpt, msg.as_string())
        server.quit()


def notifyrun(msg, forced=False):
    ini = Config.getboolean('notification', 'notifyrun', fallback=True)
    if not forced and not ini:
        return

    # put the sending work in thread in case there's delay in
    # accessing notifyrun's server
    channel = Config['notifyrun']['channel']

    def send():
        notify = Notify(endpoint=f"https://notify.run/{channel}")
        notify.send(msg)
    threading.Thread(target=send, args=()).start()


def play_sound(times=1, forced=False):
    ini = Config.getboolean('notification', 'playsound', fallback=True)
    if not forced and not ini:
        return

    mp3_file = Config['media']['soundtrack']
    for i in range(times):
        playsound(mp3_file)


def push_bullet(message, title='Fishing', forced=False):
    ini = Config.getboolean('notification', 'pushbullet', fallback=True)
    if not forced and not ini:
        return

    api_key = Config['pushbullet']['key']
    pb = Pushbullet(api_key)
    pb.push_note(title, message)


def send_notifications(msg):
    push_bullet(msg)
    play_sound(3)
    sendmail(msg)
    notifyrun(msg)

if __name__ == "__main__":
    import sys
    settings.init()
    send_notifications("testing 1234")
