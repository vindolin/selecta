import fcntl
import termios
import sys
import urwid
import subprocess
import signal
import re
import os
import fileinput

import logging
logging.basicConfig(filename='rivig.log', filemode='w', level=logging.INFO)

fd = sys.stdin.fileno()

old = termios.tcgetattr(fd)
new = termios.tcgetattr(fd)


# list_items = []
# for line in open(os.path.expanduser('~/.bash_history'), 'rb'):
#     try:
#         list_items.append(line.decode(sys.stdout.encoding).strip())
#     except:
#         raise
# list_items.reverse()

# list_items = subprocess.check_output('bash -i -c "history -r; history"', shell=True)
# list_items = [item.split(None, 1)[1] for item in list_items.decode(sys.stdout.encoding).strip().split('\n')]
# list_items.reverse()

list_items = []
for line in fileinput.input():
    line = line.split(None, 1)[1]
    if 'rivig.py' not in line:
        list_items.append(line.decode(sys.stdout.encoding).strip())
list_items.reverse()


line_count = 0
line_count_total = 0

palette = [
    ('head',  '', '', '', '#aaa', '#23b'),
    ('body',  '', '', '', '#ddd', '#000'),
    ('focus', '', '', '', '#000', '#da0'),
    ('input', '', '', '', '#fff', '#23b'),
]

signal.signal(signal.SIGINT, lambda *_: sys.exit(0))  # die with style


class ItemWidget(urwid.WidgetWrap):

    def __init__(self, description):
        self.content = description
        # self.item = [urwid.AttrMap(urwid.Text([self.content, ('test', 'bla')]), 'body', 'focus')]
        self.item = [urwid.AttrMap(urwid.Text(self.content), 'body', 'focus')]
        urwid.WidgetWrap.__init__(self, urwid.Columns(self.item))

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class SearchEdit(urwid.Edit):

    signals = ['done', 'toggle_regexp_modifier', 'toggle_case_modifier']

    def keypress(self, size, key):
        logging.info('search {} {}'.format(size, key))
        if key == 'enter':
            logging.info(self.get_edit_text())
            urwid.emit_signal(self, 'done', self.get_edit_text())
            return
        elif key == 'esc':
            urwid.emit_signal(self, 'done', None)
            return
        elif key == 'tab':
            urwid.emit_signal(self, 'toggle_case_modifier')
            urwid.emit_signal(self, 'change', self, self.get_edit_text())
            return
        elif key == 'ctrl r':
            urwid.emit_signal(self, 'toggle_regexp_modifier')
            urwid.emit_signal(self, 'change', self, self.get_edit_text())
            return
        elif key == 'down':
            urwid.emit_signal(self, 'done', '')
            return

        urwid.Edit.keypress(self, size, key)

class ResultList(urwid.ListBox):
    signals = ['resize']

    def render(self, size, focus):
        urwid.emit_signal(self, 'resize', size[1])
        return urwid.ListBox.render(self, size, focus)

class LineCountWidget(urwid.Text):
    pass

class Selector(object):
    def __init__(self):
        self.list_item_widgets = [ItemWidget(item.strip()) for item in list_items]

        self.line_count_display = LineCountWidget('')
        self.search_edit = SearchEdit(edit_text='')

        self.modifier_display = urwid.Text('')

        urwid.connect_signal(self.search_edit, 'done', self.edit_done)
        urwid.connect_signal(self.search_edit, 'toggle_case_modifier', self.toggle_case_modifier)
        urwid.connect_signal(self.search_edit, 'toggle_regexp_modifier', self.toggle_regexp_modifier)
        urwid.connect_signal(self.search_edit, 'change', self.edit_change)

        header = urwid.AttrMap(urwid.Columns([
            (8, self.line_count_display), # TODO pack at runtime?
            urwid.AttrMap(self.search_edit, 'input', 'input'),  # TODO pack at runtime?
            self.modifier_display,
        ]), 'head', 'head')

        self.item_list = urwid.SimpleListWalker(self.list_item_widgets)
        self.listbox = ResultList(self.item_list)

        urwid.connect_signal(self.listbox, 'resize', self.list_resize)

        self.view = urwid.Frame(body=urwid.AttrMap(self.listbox, 'body'), header=header)

        self.regexp_modifier = False
        self.case_modifier = False

        self.loop = urwid.MainLoop(self.view, palette, unhandled_input=self.on_unhandled_input)
        self.loop.screen.set_terminal_properties(colors=256)

        logging.info(self.loop.screen.get_cols_rows())

        self.loop.run()

    def list_resize(self, height):
        logging.info(height)
        self.line_count_display.set_text('{}/{} '.format(len(self.list_item_widgets), height))
        self.line_count_display.pack()

    def meep(self, *args):
        logging.info(args)

    def toggle_case_modifier(self):
        self.case_modifier = not self.case_modifier
        self.update_modifiers()

    def toggle_regexp_modifier(self):
        self.regexp_modifier = not self.regexp_modifier
        self.update_modifiers()

    def update_modifiers(self):
        modifiers = []
        if self.regexp_modifier:
            modifiers.append('regexp')
        if self.case_modifier:
            modifiers.append('case')

        if len(modifiers) > 0:
            self.modifier_display.set_text('[{}]'.format(','.join(modifiers)))
        else:
            self.modifier_display.set_text('')


    def update_list(self, search_text):
        if search_text == '':  # show whole list_items
            self.item_list[:] = self.list_item_widgets

        else:
            pattern = '{}'.format(search_text)

            flags = re.IGNORECASE | re.UNICODE

            if not self.regexp_modifier:
                pattern = re.escape(pattern)

            if self.case_modifier:
                flags ^= re.IGNORECASE

            self.item_list[:] = [
                ItemWidget(item.strip()) for item in list_items
                if re.search(pattern, item, flags)
            ]

        try:
            self.item_list.set_focus(0)
        except:
            pass

    def edit_change(self, widget, search_text):
        self.update_list(search_text)

    def edit_done(self, search_text):
        self.update_list(search_text)
        self.view.set_focus('body')

    def on_unhandled_input(self, input_):
        logging.info('input "{}"'.format(input_))
        if isinstance(input_, tuple):  # mouse events
            return True

        if input_ == 'enter':
            try:
                focus = self.listbox.get_focus()[0].content
            except AttributeError:  # empty list
                return

            self.view.set_header(urwid.AttrMap(
                urwid.Text('selected: %s' % str(focus)), 'head'))

            self.inject_command(str(focus))

        elif input_ == 'tab':
            self.toggle_case_modifier()

        elif input_ == 'ctrl r':
            self.toggle_regexp_modifier()

        elif input_ == 'backspace':
            self.search_edit.set_edit_text(self.search_edit.get_text()[0][:-1])
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        elif input_ == 'esc':
            raise urwid.ExitMainLoop()

        elif len(input_) == 1:  # ignore things like tab, enter
            self.search_edit.set_edit_text(self.search_edit.get_text()[0] + input_)
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        return True

    def inject_command(self, command):
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] = new[3] & ~termios.ECHO  # disable echo
        termios.tcsetattr(fd, termios.TCSANOW, new)
        for c in command:
            fcntl.ioctl(fd, termios.TIOCSTI, c)
        termios.tcsetattr(fd, termios.TCSANOW, old)
        raise urwid.ExitMainLoop()


if __name__ == '__main__':
    Selector()
