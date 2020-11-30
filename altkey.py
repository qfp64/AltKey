from __future__ import print_function
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import PyQt5.QtCore as QtCore

import pyWinhook as pyHook
import ctypes
import win32api, win32con
import kb
import string

def capslock_state():
    return win32api.GetKeyState(win32con.VK_CAPITAL)

MODIFIERS = ('Lcontrol', 'Rcontrol', 'Lshift', 'Rshift', 'Lmenu', 'Rmenu')
SHIFT = ('Lshift', 'Rshift')
KEYMAP_FILE = "keymap.txt"

hotkey = 'Rmenu' # AltGr


# Build a table mapping "extended scancodes" to ascii chars
# The return value of OemKeyScan is considered to be an "extended" scancode -
# it's the scancode with the high dword containing the modifier bits
EXT_SCANCODE_TO_ASCII = {}
for c in range(256):
    scancode = ctypes.windll.user32.OemKeyScan(c)
    if scancode != -1:
        EXT_SCANCODE_TO_ASCII[scancode] = chr(c)
EXT_SHIFT = 0x10000


class KeymapParser():
    def __init__(self):
        pass

    def split_line(self, line):
        if len(line) > 0:
            if line[0] == '#':
                return []
        return line.split()

    def parse(self, map_file):
        self.lnum = 0
        keymap = {}
        lines = open(map_file, 'rb').readlines()
        for lnum, line in enumerate(lines):
            self.lnum = lnum+1
            ld = line.decode().strip()
            ls = self.split_line(ld)
            if len(ls) == 2:
                glyph = ls[0]
                sequence = ls[1]

                if glyph[0] == '[':
                    # Group: [glyphs] [
                    if glyph[-1] != ']':
                        return False, f'line {self.lnum}: missing ] to close group'
                    glyph_group = glyph[1:-1]
                    if sequence[0] != '[':
                        return False, f'line {self.lnum}: missing [ to start key group'
                    if sequence[-2] != ']': #hacky pls fix
                        return False, f'line {self.lnum}: missing ] to close key group'
                    key_group = sequence[1:-2]
                    final_key = sequence[-1]

                    if len(glyph_group) != len(key_group):
                        return False, f'line {self.lnum}: glyph and key groups must be the same length'

                    for i in range(len(glyph_group)):
                        if key_group[i] not in keymap:
                            keymap[key_group[i]] = {}
                        keymap[key_group[i]][final_key] = glyph_group[i]

                else:
                    if len(glyph) != 1:
                        return False, f'line {self.lnum}: glyphs must be a single character (got "{glyph}")'
                    if len(sequence) != 2:
                        return False, f'line {self.lnum}: key sequences must be of length 2 (got "{sequence}")'
                    if sequence[0] not in keymap:
                        keymap[sequence[0]] = {}
                    keymap[sequence[0]][sequence[1]] = glyph
            elif len(ls) == 0:
                # blank line
                continue
            else:
                return False, f"line {self.lnum}: syntax error"

        return True, keymap



class KeyboardListener():
    def __init__(self):
        self.modifiers = {k: False for k in MODIFIERS}
        self.active = False
        self.base_key = None

        hm = pyHook.HookManager()
        hm.KeyDown = self.key_down
        hm.KeyUp = self.key_up
        hm.HookKeyboard()

    # Get an ASCII character from a key event.
    # pyWinhook returns an ascii character, but e.g. on a UK keyboard, AltGr+A will return á, when
    # we really want a (or A, depending on shift/caps lock). To get this base character we have to
    # look at the scan code and modifiers.
    def get_ascii(self, event):
        ext_scancode = event.ScanCode
        shifted = self.modifiers[SHIFT[0]] or self.modifiers[SHIFT[1]]
        if shifted:
            ext_scancode |= EXT_SHIFT

        key = EXT_SCANCODE_TO_ASCII.get(ext_scancode)
        if not key: return None

        # Deal with caps lock for letters
        if key in string.ascii_letters:
            caps = capslock_state()
            if caps:
                if key in string.ascii_uppercase:
                    key = key.lower()
                else: 
                    key = key.upper()
        print(f"** {key}")
        return key

    def key_down(self, event):
        if event.Key == 'Packet': return True
        if event.Key in MODIFIERS:
            # Track the state of the modifier keys
            self.modifiers[event.Key] = True

        elif self.active:
            # Active - look for 2nd key
            window.sig_close.emit()
            self.active = False
            options = keymap.get(self.base_key)
            if options:
                output = options.get(self.get_ascii(event))
                # Generate output keypress if there is one
                if output: 
                    print("Generating", output)
                    kb.press(output)
            return False
        else:
            # Inactive - look for hotkey + valid key
            if self.modifiers[hotkey]:
                self.base_key = self.get_ascii(event)
                self.active = True
                window.sig_key.emit(self.base_key)

                # Capture keypress
                return False

        # Returning True allows the keypress to propagate to whatever window is active
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
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(0,0,0,0)
        
        # Character
        top = QLabel(t)
        top.setFont(QFont('Arial', 24))
        top.setAlignment(QtCore.Qt.AlignCenter)
        top.setStyleSheet("border: 0px solid red;")
        
        # Key
        key_size = 30
        key_font_size = 16
        bottom = QLabel(b)
        bottom.setFixedWidth(key_size)
        bottom.setFixedHeight(key_size)
        bottom.setFont(QFont('Arial', key_font_size))
        bottom.setAlignment(QtCore.Qt.AlignCenter)
        bottom.setStyleSheet("border: 1px solid #707070; border-radius: 5px;")
        
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
        self.layout = QHBoxLayout()
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
            opt = Option(options[k], k)
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

    # Read keymap file
    parser = KeymapParser()
    parse_ok, output = parser.parse(KEYMAP_FILE)
    if not parse_ok:
        print("Reading the keymap file failed:\n{}".format(output))
        sys.exit(-1)
    else:
        keymap = output

    window = Window()
    listener = KeyboardListener()
    app.exec_()