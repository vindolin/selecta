#!/usr/bin/env python3
import fcntl
import termios
import sys
import struct
import urwid
import subprocess
import signal
import re
import os
import fileinput

palette = [
    ('head', '', '', '', '#aaa', '#618'),
    ('body', '', '', '', '#ddd', '#000'),
    ('focus', '', '', '', '#000', '#da0'),
    ('input', '', '', '', '#fff', '#618'),
    ('empty_list', '', '', '', '#ddd', '#b00'),
    ('pattern', '', '', '', '#f91', ''),
    ('pattern_focus', '', '', '', 'bold,#a00', '#da0'),
    ('line','', '', '', '', ''),
    ('line_focus','', '', '', '#000', '#da0'),
]

signal.signal(signal.SIGINT, lambda *_: sys.exit(0))  # die with style


class ItemWidget(urwid.WidgetWrap):
    def __init__(self, list_item, show_hits, match=None):
        self.list_item = list_item
        if match is not None and show_hits is True:
            parts = self.list_item.partition(match)
            text = urwid.AttrMap(
                urwid.Text(
                    [parts[0],
                    ('pattern', parts[1]),
                    parts[2]
                ]
            ), 'line', {'pattern': 'pattern_focus', None: 'line_focus'})
        else:
            text = urwid.AttrMap(urwid.Text(self.list_item), 'line', 'line_focus')

        urwid.WidgetWrap.__init__(self, text)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class SearchEdit(urwid.Edit):
    __metaclass__ = urwid.signals.MetaSignals
    signals = ['done', 'toggle_regexp_modifier', 'toggle_case_modifier']

    def keypress(self, size, key):
        if key == 'enter':
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
            urwid.emit_signal(self, 'done', None)
            return

        urwid.Edit.keypress(self, size, key)


class ResultList(urwid.ListBox):
    __metaclass__ = urwid.signals.MetaSignals
    signals = ['resize']

    def __init__(self, *args):
        self.last_size = 0
        urwid.ListBox.__init__(self, *args)

    def render(self, size, focus):
        if size != self.last_size:
            self.last_size = size
            urwid.emit_signal(self, 'resize', size[1])
        return urwid.ListBox.render(self, size, focus)


class LineCountWidget(urwid.Text):
    pass


class Selector(object):
    def __init__(self, revert_order, remove_bash_prefix, remove_zsh_prefix, regexp, case_sensitive,
                 remove_duplicates, show_hits, infile):

        self.show_hits = show_hits
        self.regexp_modifier = regexp
        self.case_modifier = case_sensitive

        self.list_items = []

        for line in infile:
            if remove_bash_prefix:
                line = line.split(None, 1)[1]

            if remove_zsh_prefix:
                line = re.split('\s+', line, maxsplit=4)[-1]

            if 'selecta <(history)' not in line:
                if remove_duplicates:
                    if line not in self.list_items:
                        self.list_items.append(line)
                else:
                    self.list_items.append(line)

        if revert_order:
            self.list_items.reverse()

        self.list_item_widgets = []

        self.line_count_display = LineCountWidget('')
        self.search_edit = SearchEdit(edit_text='')

        self.modifier_display = urwid.Text('')

        urwid.connect_signal(self.search_edit, 'done', self.edit_done)
        urwid.connect_signal(self.search_edit, 'toggle_case_modifier', self.toggle_case_modifier)
        urwid.connect_signal(self.search_edit, 'toggle_regexp_modifier', self.toggle_regexp_modifier)
        urwid.connect_signal(self.search_edit, 'change', self.edit_change)

        header = urwid.AttrMap(urwid.Columns([
            ('pack', self.line_count_display),
            urwid.AttrMap(self.search_edit, 'input', 'input'),
            self.modifier_display,
        ], dividechars=1, focus_column=1), 'head', 'head')

        self.item_list = urwid.SimpleListWalker(self.list_item_widgets)
        self.listbox = ResultList(self.item_list)

        urwid.connect_signal(self.listbox, 'resize', self.list_resize)

        self.view = urwid.Frame(body=self.listbox, header=header)

        self.loop = urwid.MainLoop(self.view, palette, unhandled_input=self.on_unhandled_input)
        self.loop.screen.set_terminal_properties(colors=256)

        self.update_list('')
        self.loop.run()

    def list_resize(self, height):
        self.line_count_display.set_text('{}/{}'.format(height, len(self.list_items)))

    def meep(self, *args):
        logger.info(args)

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
            self.item_list[:] = [ItemWidget(item.strip(), show_hits=self.show_hits) for item in self.list_items]

        else:
            pattern = '{}'.format(search_text)

            flags = re.IGNORECASE | re.UNICODE

            if not self.regexp_modifier:
                pattern = re.escape(pattern)

            if self.case_modifier:
                flags ^= re.IGNORECASE


            try:
                re_search = re.compile(pattern, flags).search
                items = []
                for item in self.list_items:
                    match = re_search(item)
                    if match:
                        items.append(ItemWidget(item.strip(), match=match.group(), show_hits=self.show_hits))

                if len(items) > 0:
                    self.item_list[:] = items
                else:
                    self.item_list[:] = [urwid.Text(('empty_list', 'No selection'))]
            except re.error as err:
                self.item_list[:] = [urwid.Text(('empty_list', 'Error in regular epression: {}'.format(err)))]

        try:
            self.item_list.set_focus(0)
        except IndexError:  # no items
            pass

    def highlight_pattern(self, match):
        print(match)

    def edit_change(self, widget, search_text):
        self.update_list(search_text)

    def edit_done(self, search_text):
        self.view.set_focus('body')

    def on_unhandled_input(self, input_):
        if isinstance(input_, tuple):  # mouse events
            return True

        if input_ == 'enter':
            try:
                list_item = self.listbox.get_focus()[0].list_item
            except AttributeError:  # empty list
                return

            self.view.set_header(urwid.AttrMap(
                urwid.Text('selected: {}'.format(list_item)), 'head'))

            self.inject_command(list_item)
            raise urwid.ExitMainLoop()

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
        command = (struct.pack('B', c) for c in os.fsencode(command))

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] = new[3] & ~termios.ECHO  # disable echo
        termios.tcsetattr(fd, termios.TCSANOW, new)
        for c in command:
            fcntl.ioctl(fd, termios.TIOCSTI, c)
        termios.tcsetattr(fd, termios.TCSANOW, old)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--revert-order', action='store_true', default=False, help='revert the order of the lines')
    parser.add_argument('-b', '--remove-bash-prefix', action='store_true', default=False, help='remove the numeric prefix from bash history')
    parser.add_argument('-z', '--remove-zsh-prefix', action='store_true', default=False, help='remove the time prefix from zsh history')
    parser.add_argument('-e', '--regexp', action='store_true', default=False, help='start in regexp mode')
    parser.add_argument('-a', '--case-sensitive', action='store_true', default=False, help='start in case-sensitive mode')
    parser.add_argument('-d', '--remove-duplicates', action='store_true', default=False, help='remove duplicated lines')
    parser.add_argument('-y', '--show-hits', action='store_true', default=False, help='highlight the part of each line which match the substrings or regexp')
    parser.add_argument('--bash', action='store_true', default=False, help='standard for bash history search, same as -b -i -d')
    parser.add_argument('--zsh', action='store_true', default=False, help='standard for zsh history search, same as -b -i -d')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin, help='the file which lines you want to select eg. <(history)')
    args = parser.parse_args()

    if args.infile.name == '<stdin>':
        parser.print_help()
        exit('\nYou must provide an infile!')

    if args.bash:
        args.revert_order = True
        args.remove_bash_prefix = True
        args.remove_duplicates = True

    if args.zsh:
        args.revert_order = True
        args.remove_zsh_prefix = True
        args.remove_duplicates = True

    Selector(
        revert_order=args.revert_order,
        remove_bash_prefix=args.remove_bash_prefix,
        remove_zsh_prefix=args.remove_zsh_prefix,
        regexp=args.regexp,
        case_sensitive=args.case_sensitive,
        remove_duplicates=args.remove_duplicates,
        show_hits=args.show_hits,  # TODO highlight more than one part
        infile=args.infile,
        # TODO support missing options
    )


if __name__ == '__main__':
    main()
