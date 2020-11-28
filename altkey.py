from __future__ import print_function
import sys
from PyQt5.QtWidgets import QWidget, QPushButton, QApplication, QFrame
import PyQt5.QtWidgets as QtWidgets
from PyQt5.QtGui import QColor
import PyQt5.QtCore as QtCore
import threading
import pyWinhook as pyHook
import time

import win32api, win32con
import kb

def capslock_state():
    return win32api.GetKeyState(win32con.VK_CAPITAL)

MODIFIERS = ('Lcontrol', 'Rcontrol', 'Lshift', 'Rshift', 'Lmenu', 'Rmenu')
SHIFT = ('Lshift', 'Rshift')

hotkey = 'Rmenu' # AltGr
keymap = {'a': {'1':'á', '2':'ä', '6':'â', '-':'ā'}, 'A': {'1': 'Á'}}

class KeyboardListener():
    def __init__(self):
        self.modifiers = {k: False for k in MODIFIERS}
        self.active = False
        self.base_key = None

        hm = pyHook.HookManager()
        hm.KeyDown = self.key_down
        hm.KeyUp = self.key_up
        hm.HookKeyboard()

    def key_down(self, event):
        if event.Key in MODIFIERS:
            self.modifiers[event.Key] = True
        elif self.active:
            # Active - look for 2nd key
            window.sig_close.emit()
            self.active = False
            options = keymap.get(self.base_key)
            if options:
                output = options.get(chr(event.Ascii))
                # Generate output keypress if there is one
                if output: 
                    kb.press(output)
            return False
        else:
            # Inactive - look for hotkey + valid key
            if self.modifiers[hotkey]:
                key = event.KeyID
                if key >= 65 and key <= 90: # A-Z keys only
                    shift = self.modifiers[SHIFT[0]] or self.modifiers[SHIFT[1]]
                    caps = capslock_state()
                    uppercase = shift ^ caps
                    if not uppercase:
                        key += 0x20

                    print(chr(key))
                    self.active = True
                    self.base_key = chr(key)

                    window.sig_key.emit(self.base_key)

                    # Stop key propagating
                    return False

        #print(f'(Propagating {event.Key})')
        return True

    def key_up(self, event):
        if event.Key in MODIFIERS:
            self.modifiers[event.Key] = False
        return True

    def print_event(self, event):
        print(f'MessageName="{event.MessageName}"')
        print(f'ASCII: {event.Ascii} ({chr(event.Ascii)})\tScancode={event.ScanCode}\tExt={event.Extended}\tAlt={event.Alt}\tKeyID={event.KeyID}\tKey={event.Key}\tmod={[k for k in self.modifiers if self.modifiers[k]]}\tcap={capslock_state()}')
    

class Option(QWidget):
    def __init__(self, t, b):
        super().__init__()
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        top = QtWidgets.QLabel(t)
        bottom = QtWidgets.QLabel(b)
        self.layout.addWidget(top)
        self.layout.addWidget(bottom)

class Window(QWidget):
    sig_key = QtCore.pyqtSignal(str)
    sig_close = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(" ")

        #self.resize(800, 200)
        #self.setGeometry(300,300,300,300)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)        
        self.options = []
        self.sig_key.connect(self.key)
        self.sig_close.connect(self.close)

    def draw_options(self, key):
        for opt in self.options:
            self.layout.removeWidget(opt)
        self.options = []

        options = keymap.get(key)
        if not options: return
        for k in options:
            opt = Option(k, options[k])
            self.options.append(opt)
            self.layout.addWidget(opt)

    @QtCore.pyqtSlot(str)
    def key(self, k):
        self.draw_options(k)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized)# | QtCore.Qt.WindowActive)        
        self.show()
        

    @QtCore.pyqtSlot()
    def close(self):
        self.hide()




if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Window()
    listener = KeyboardListener()
    app.exec_()