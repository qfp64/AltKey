from __future__ import print_function
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import PyQt5.QtCore as QtCore

import pyWinhook as pyHook
import ctypes, string
import win32api, win32con
from sendinput import generate_keypress


MODIFIERS = ('Lcontrol', 'Rcontrol', 'Lshift', 'Rshift', 'Lmenu', 'Rmenu')
SHIFT = ('Lshift', 'Rshift')
KEYMAP_FILE = "keymap.txt" 
hotkey = 'Rmenu' # AltGr




class KeymapParser():
    NEWLINE = 1

    def __init__(self):
        pass

    def split_line(self, line):
        if len(line) > 0:
            if line[0] == '#':
                return []
        return line.split()

    def tokenise(self, lines):
        tokens = []
        for num, line in enumerate(lines):
            words = line.decode().strip().split()

            # Strip out comments 
            comment_pos = None
            for idx, word in enumerate(words):
                if word[0] == '#':
                    comment_pos = idx
                    break
            if comment_pos is not None:
                words = words[0:comment_pos]

            if len(words) == 0:
                # Blank line
                continue

            tokens += [self.NEWLINE, num+1]
            tokens.extend(words)
            
        tokens += [self.NEWLINE, num+1]
        self.tokens = tokens
        self.idx = 0
        self.line_number = 0
        self.newline()

    def next(self):
        try:
            token = self.tokens[self.idx]
            self.idx += 1
        except:
            return None
        return token

    def newline(self):
        t = self.next()
        if t != self.NEWLINE:
            raise Exception(f"Line {self.line_number}: expected newline")
        self.line_number = self.next()

    def parse(self, map_file):
        keymap = {}

        lines = open(map_file, 'rb').readlines()
        self.tokenise(lines)

        while True:
            t1 = self.next()
            if not t1: break
            t2 = self.next()
            print(t1, t2)
            self.newline()

            sequence = t1
            glyph = t2

            if len(glyph) != 1:
                return False, f'line {self.line_number}: glyphs must be a single character (got "{glyph}")'
            if len(sequence) != 2:
                return False, f'line {self.line_number}: key sequences must be of length 2 (got "{sequence}")'
            if sequence[0] not in keymap:
                keymap[sequence[0]] = {}

            if sequence[1] in keymap[sequence[0]]:
                print(f'WARNING: {sequence[0]}{sequence[1]} {glyph} overwrites {keymap[sequence[0]][sequence[1]]}')
            keymap[sequence[0]][sequence[1]] = glyph

                   
            # if len(ls) == 2:
            #     sequence = ls[0]
            #     glyph = ls[1]

            #     if sequence[0] == '[':
            #         pass
            #         # # Group: [glyphs] [
            #         # if glyph[-1] != ']':
            #         #     return False, f'line {self.lnum}: missing ] to close group'
            #         # glyph_group = glyph[1:-1]
            #         # if sequence[0] != '[':
            #         #     return False, f'line {self.lnum}: missing [ to start key group'
            #         # if sequence[-2] != ']': #hacky pls fix
            #         #     return False, f'line {self.lnum}: missing ] to close key group'
            #         # key_group = sequence[1:-2]
            #         # final_key = sequence[-1]

            #         # if len(glyph_group) != len(key_group):
            #         #     return False, f'line {self.lnum}: glyph and key groups must be the same length'

            #         # for i in range(len(glyph_group)):
            #         #     if key_group[i] not in keymap:
            #         #         keymap[key_group[i]] = {}
            #         #     keymap[key_group[i]][final_key] = glyph_group[i]

            #     else:

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

        # Build a table mapping "extended scancodes" to ascii chars
        # The return value of OemKeyScan is considered to be an "extended" scancode -
        # it's the scancode with the high dword containing the modifier bits
        self.EXT_SCANCODE_TO_ASCII = {}
        for c in range(256):
            scancode = ctypes.windll.user32.OemKeyScan(c)
            if scancode != -1:
                self.EXT_SCANCODE_TO_ASCII[scancode] = chr(c)
        self.EXT_SHIFT = 0x10000

    # Return current caps lock state
    def capslock_state(self):
        return win32api.GetKeyState(win32con.VK_CAPITAL)        

    # Get an ASCII character from a key event.
    # pyWinhook returns an ascii character, but e.g. on a UK keyboard, AltGr+A will return á, when
    # we really want a (or A, depending on shift/caps lock). To get this base character we have to
    # look at the scan code and modifiers.
    def get_ascii(self, event):
        ext_scancode = event.ScanCode
        shifted = self.modifiers[SHIFT[0]] or self.modifiers[SHIFT[1]]
        if shifted:
            ext_scancode |= self.EXT_SHIFT

        key = self.EXT_SCANCODE_TO_ASCII.get(ext_scancode)
        if not key: return None

        # Deal with caps lock for letters
        if key in string.ascii_letters:
            caps = self.capslock_state()
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
                    generate_keypress(output)
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
        print(f'ASCII: {event.Ascii} ({chr(event.Ascii)})\tScancode={event.ScanCode}\tExt={event.Extended}\tAlt={event.Alt}\tKeyID={event.KeyID}\tKey={event.Key}\tmod={[k for k in self.modifiers if self.modifiers[k]]}\tcap={self.capslock_state()}')
    

class Option(QWidget):
    def __init__(self, t, b):
        glyph_font = 'Arial'
        key_font = 'Trebuchet MS'

        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setSpacing(5)
        self.layout.setContentsMargins(0,0,0,0)
        
        # Character
        top = QLabel(t)
        top.setFont(QFont(glyph_font, 24))
        top.setAlignment(QtCore.Qt.AlignCenter)
        top.setStyleSheet("border: 0px solid red;")
        
        # Key
        key_size = 30
        key_font_size = 16
        bottom = QLabel(b)
        bottom.setFixedWidth(key_size)
        bottom.setFixedHeight(key_size)
        bottom.setFont(QFont(key_font, key_font_size))
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

    print(keymap)

    window = Window()
    listener = KeyboardListener()
    app.exec_()