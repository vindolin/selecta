import fcntl
import termios
import sys
import struct
import urwid
import signal
import re
import os

if (sys.version_info < (3, 0)):
    exit('Sorry, you need Python 3 to run this!')

palette = [
    ('head', '', '', '', '#000', '#618'),
    ('body', '', '', '', '#ddd', '#000'),
    ('focus', '', '', '', '#000', '#da0'),
    ('input', '', '', '', '#fff', '#618'),
    ('empty_list', '', '', '', '#ddd', '#b00'),
    ('pattern', '', '', '', '#f91', ''),
    ('pattern_focus', '', '', '', 'bold,#a00', '#da0'),
    ('line', '', '', '', '', ''),
    ('line_focus', '', '', '', '#000', '#da0'),
]

signal.signal(signal.SIGINT, lambda *_: sys.exit(0))  # die with style

HIGHLIGHT_NONE, HIGHLIGHT_WHOLE_STRING, HIGHLIGHT_WORDS, HIGHLIGHT_REGEX = range(4)


class ItemWidget(urwid.WidgetWrap):
    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class ItemWidgetPlain(ItemWidget):
    def __init__(self, line):
        self.line = line
        text = urwid.AttrMap(urwid.Text(self.line), 'line', 'line_focus')
        super().__init__(text)


class ItemWidgetPattern(ItemWidget):
    def __init__(self, line, match=None):
        self.line = line

        # highlight the matches
        matches = re.split(f'({match})', self.line)
        parts = []
        for part in matches:
            if part == match:
                parts.append(('pattern', part))
            else:
                parts.append(part)

        text = urwid.AttrMap(
            urwid.Text(parts),
            'line',
            {'pattern': 'pattern_focus', None: 'line_focus'}
        )

        super().__init__(text)


class ItemWidgetWords(ItemWidget):
    def __init__(self, line, search_words):
        self.line = line

        subject = line
        parts = []
        split = []
        for search_word in search_words:
            if search_word:
                split = subject.split(search_word, maxsplit=1)
                subject = split[-1]
                parts += [split[0], ('pattern', search_word)]

        if 1 in split:
            parts += split[1]

        text = urwid.AttrMap(
            urwid.Text(parts),
            'line',
            {'pattern': 'pattern_focus', None: 'line_focus'}
        )

        super().__init__(text)


class SearchEdit(urwid.Edit):
    signals = ['done', 'toggle_regexp_modifier', 'toggle_case_modifier']

    def keypress(self, size, key):
        if key == 'enter':
            urwid.emit_signal(self, 'done', self.get_edit_text())
            return
        elif key == 'esc':
            urwid.emit_signal(self, 'done', None)
            return
        elif key == 'ctrl a':
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
    signals = ['resize']

    def __init__(self, *args):
        self.last_size = None
        urwid.ListBox.__init__(self, *args)

    def render(self, size, focus):
        if size != self.last_size:
            self.last_size = size
            urwid.emit_signal(self, 'resize', size)
        return urwid.ListBox.render(self, size, focus)


class LineCountWidget(urwid.Text):
    def update(self, relevant_lines=None, visible_lines=None):
        if not hasattr(self, 'relevant_lines'):
            self.relevant_lines = 0
            self.visible_lines = 0

        if relevant_lines is not None:
            self.relevant_lines = relevant_lines

        if visible_lines is not None:
            self.visible_lines = visible_lines

        self.set_text('{}/{}'.format(self.visible_lines, self.relevant_lines))


class Selector(object):
    def __init__(self, revert_order, remove_bash_prefix, remove_zsh_prefix, regexp, case_sensitive,
                 remove_duplicates, show_matches, infile):

        self.show_matches = show_matches
        self.regexp_modifier = regexp
        self.case_modifier = case_sensitive
        self.remove_bash_prefix = remove_bash_prefix

        self.lines = []

        if revert_order:
            lines = reversed(infile.readlines())
        else:
            lines = infile

        import re

        for line in lines:
            if remove_bash_prefix:
                line = line.split(None, 1)[1].strip()

            if remove_zsh_prefix:
                line = re.split(r'\s+', line, maxsplit=4)[-1]

            if 'selecta <(history)' not in line:
                if not remove_duplicates or line not in self.lines:
                    self.lines.append(line)

        self.line_widgets = []

        self.line_count_display = LineCountWidget('')
        self.search_edit = SearchEdit(edit_text='')

        self.modifier_display = urwid.Text('')

        self.update_modifiers()

        urwid.connect_signal(self.search_edit, 'done', self.edit_done)
        urwid.connect_signal(self.search_edit, 'toggle_case_modifier', self.toggle_case_modifier)
        urwid.connect_signal(self.search_edit, 'toggle_regexp_modifier', self.toggle_regexp_modifier)
        urwid.connect_signal(self.search_edit, 'change', self.edit_change)

        header = urwid.AttrMap(urwid.Columns([
            urwid.AttrMap(self.search_edit, 'input', 'input'),
            self.modifier_display,
            ('pack', self.line_count_display),
        ], dividechars=1, focus_column=0), 'head', 'head')

        self.item_list = urwid.SimpleListWalker(self.line_widgets)
        self.listbox = ResultList(self.item_list)

        urwid.connect_signal(self.listbox, 'resize', self.list_resize)

        self.view = urwid.Frame(body=self.listbox, header=header)

        self.loop = urwid.MainLoop(self.view, palette, unhandled_input=self.on_unhandled_input)
        self.loop.screen.set_terminal_properties(colors=256)

        self.line_count_display.update(self.listbox.last_size, len(self.item_list))

        # TODO workaround, when update_list is called directly, the linecount widget gets not updated
        self.loop.set_alarm_in(0.01, lambda *loop: self.update_list(''))

        self.loop.run()

    def list_resize(self, size):
        self.line_count_display.update(visible_lines=size[1])

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

    def update_list(self, search_text=''):
        search_words = ''
        if search_text == '' or search_text == '"' or search_text == '""':  # show all lines
            self.item_list[:] = [ItemWidgetPlain(item) for item in self.lines]
            self.line_count_display.update(len(self.item_list))
        else:
            pattern = ''

            flags = re.UNICODE

            highlight_type = None

            # search string is a regular expression
            if self.regexp_modifier:
                highlight_type = HIGHLIGHT_REGEX
                pattern = search_text
            else:
                if search_text.startswith('"'):
                    # search for whole string between quotation marks
                    highlight_type = HIGHLIGHT_WHOLE_STRING
                    pattern = re.escape(search_text.strip('"'))
                else:
                    # default - split all words and convert to regular expression like: word1.*word2.*word3
                    subpatterns = search_text.split(' ')
                    if len(subpatterns) == 1:
                        search_words = pattern = search_text
                        pattern = re.escape(pattern)
                    else:
                        search_words = search_text.split(' ')
                        highlight_type = HIGHLIGHT_WORDS
                        pattern = '.*'.join([re.escape(word) for word in search_words])

            if self.case_modifier:
                flags ^= re.IGNORECASE

            try:
                re_search = re.compile(pattern, flags).search
                items = []
                for item in self.lines:
                    match = re_search(item)
                    if match:
                        if self.show_matches:
                            if highlight_type == HIGHLIGHT_WORDS:
                                items.append(ItemWidgetWords(item, search_words=search_words))
                            else:
                                items.append(ItemWidgetPattern(item, match=match.group()))
                        else:
                            items.append(ItemWidgetPlain(item))

                if len(items) > 0:
                    self.item_list[:] = items
                    self.line_count_display.update(relevant_lines=len(self.item_list))
                else:
                    self.item_list[:] = [urwid.Text(('empty_list', 'No selection'))]
                    self.line_count_display.update(relevant_lines=0)

            except re.error as err:
                self.item_list[:] = [urwid.Text(('empty_list', 'Error in regular epression: {}'.format(err)))]
                self.line_count_display.update(relevant_lines=0)

        try:
            self.item_list.set_focus(0)
        except IndexError:  # no items
            pass

    def edit_change(self, widget, search_text):
        self.update_list(search_text)

    def edit_done(self, search_text):
        self.view.set_focus('body')

    def on_unhandled_input(self, input_):
        if isinstance(input_, tuple):  # mouse events
            return True

        if input_ == 'enter':
            focused_widget = self.listbox.get_focus()[0]
            if focused_widget is not None:
                line = focused_widget.line
            else:
                return

            self.view.set_header(urwid.AttrMap(
                urwid.Text('selected: {}'.format(line)), 'head'))

            self.inject_line(line)
            raise urwid.ExitMainLoop()

        elif input_ == 'ctrl a':
            self.toggle_case_modifier()

        elif input_ == 'ctrl r':
            self.toggle_regexp_modifier()

        elif input_ == 'backspace':
            self.search_edit.set_edit_text(self.search_edit.get_text()[0][:-1])
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        elif input_ == 'esc':
            raise urwid.ExitMainLoop()

        # elif input_ == 'delete':
        #     if self.remove_bash_prefix:
        #         try:
        #             line = self.listbox.get_focus()[0].line
        #             self.lines.remove(line)
        #             self.item_list[:] = [ItemWidgetPlain(item) for item in self.lines]

        #             # TODO make this working when in bash mode
        #             call("sed -i '/^{}$/d' ~/.bash_history".format(line), shell=True)
        #         except AttributeError:  # empty list
        #             return True

        elif len(input_) == 1:  # ignore things like tab, enter
            self.search_edit.set_edit_text(self.search_edit.get_text()[0] + input_)
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        return True

    def inject_line(self, command):
        """Inject the line into the terminal."""
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
    parser.add_argument('-r', '--regexp', action='store_true', default=False, help='start in regexp mode')
    parser.add_argument('-a', '--case-sensitive', action='store_true', default=True, help='start in case-sensitive mode')
    parser.add_argument('-d', '--remove-duplicates', action='store_true', default=False, help='remove duplicated lines')
    parser.add_argument('-y', '--show-matches', action='store_true', default=False, help='highlight the part of each line which match the substrings or regexp')
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
        show_matches=args.show_matches,
        infile=args.infile,
        # TODO support missing options from the original selector
        # TODO directory history would be sweet!
    )


if __name__ == '__main__':
    main()
