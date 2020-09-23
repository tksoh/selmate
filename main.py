import sys
from windows import startwindow
import settings

def alertcheck():
    from notification import sendmail, notifyrun
    sendmail('testing')
    notifyrun('testing')

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    startwindow()
    print('done')
