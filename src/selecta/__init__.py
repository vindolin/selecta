# pylint: disable=C0321

"""Selecta 0.2.0"""

import codecs
import fcntl
import os
import re
import signal
import struct
import sys
import termios
import urwid


def debug(value, prefix=''):
    """only usded when debugging"""
    with codecs.open('/tmp/selecta.log', 'a', encoding='utf-8') as file:
        file.write(f'{prefix} {value}\n')


if sys.version_info < (3, 0):
    sys.exit('Sorry, you need Python 3 to run this!')

palette = [
    ('head', '', '', '', '#bbb', '#618'),
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


class ItemWidget(urwid.WidgetWrap):
    """Base for a widget for a single line in the listbox."""
    def selectable(self):
        return True

    def keypress(self, _, key):
        return key


class ItemWidgetPlain(ItemWidget):
    """Widget that displays a line as is."""
    def __init__(self, line):
        self.line = line
        text = urwid.AttrMap(urwid.Text(self.line), 'line', 'line_focus')
        super().__init__(text)


class ItemWidgetPattern(ItemWidget):
    """Widget that highlights the matching part of a line."""
    def __init__(self, line, match):
        self.line = line

        # highlight the matches
        matches = re.split(f'({re.escape(match)})', self.line)

        parts = [('pattern', part) if part == match else part for part in matches]

        text = urwid.AttrMap(
            urwid.Text(parts),
            'line',
            {'pattern': 'pattern_focus', None: 'line_focus'}
        )

        super().__init__(text)


def mark_parts(subject_string, s_words, case_sensitive=False):
    def wrap_part(part):
        return ('pattern', part)

    # set re flags
    flags = 0
    if not case_sensitive:
        flags |= re.IGNORECASE

    # split sub string at word boundaries
    s_parts = [s_word for s_word in re.split(rf"({'|'.join(s_words)})", subject_string, flags=flags) if s_word]

    # create list of search words as lookup list,
    s_words_x = s_words if case_sensitive else [s_word.lower() for s_word in s_words]

    # generate list of the word parts and mark the search words
    if False:
        # use regular for loop
        l_parts = []
        for word in s_parts:
            word_x = word if case_sensitive else word.lower()
            l_parts.append(wrap_part(word) if word_x in s_words_x else word)
    else:
        # use faster(?) list comprehension
        l_parts = [wrap_part(word) if (word if case_sensitive else word.lower()) in s_words_x else word
                   for word in s_parts]

    return l_parts


class ItemWidgetWords(ItemWidget):
    """Widget that highlights the matching words of a line."""
    def __init__(self, line, search_words, case_modifier=False):
        self.line = line

        text = urwid.AttrMap(
            urwid.Text(mark_parts(line, search_words, case_modifier)),
            'line',
            {'pattern': 'pattern_focus', None: 'line_focus'}
        )
        super().__init__(text)

    def split_words(self, words, subject):
        """Split the subject into pieces for later styling."""
        # return [item for item in re.split(rf"({'|'.join(words)})", subject) if item]
        return [word for word in re.split(rf"({'|'.join(words)})", subject) if word]


class SearchEdit(urwid.Edit):
    """Edit widget for the search input."""

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
        # elif key == 'ctrl d':
        #     urwid.emit_signal(self, 'toggle_directory_modifier')
        #     urwid.emit_signal(self, 'change', self, self.get_edit_text())
        #     return
        elif key == 'down':
            urwid.emit_signal(self, 'done', None)
            return

        urwid.Edit.keypress(self, size, key)


class ResultList(urwid.ListBox):
    """List of the found lines."""
    signals = ['resize']

    def __init__(self, *args):
        self.last_size = None
        urwid.ListBox.__init__(self, *args)

    def render(self, size, focus=False):
        if size != self.last_size:
            self.last_size = size
            urwid.emit_signal(self, 'resize', size)
        return urwid.ListBox.render(self, size, focus)


class LineCountWidget(urwid.Text):
    """Widget that displays the number of matching lines / total lines."""
    def __init__(self, line_count=0):
        super().__init__('')
        self.line_count = line_count
        self.matching_lines = 0

    def update(self, matching_lines=None):
        """Update the widget with the current number of matching lines."""
        if matching_lines is not None:
            self.matching_lines = matching_lines

        self.set_text(f'{self.matching_lines}/{self.line_count}')


class Selector(object):
    """The main class of Selecta."""
    def __init__(self, revert_order, remove_bash_prefix, remove_zsh_prefix, regexp, case_sensitive,
                 remove_duplicates, show_matches, infile):

        self.show_matches = show_matches
        self.regexp_modifier = regexp
        self.case_modifier = case_sensitive
        # self.directory_modifier_modifier = False
        self.remove_bash_prefix = remove_bash_prefix

        self.lines = []

        if revert_order:
            lines = reversed(infile.readlines())
        else:
            lines = infile

        for line in lines:
            line = line.strip()
            if remove_bash_prefix:
                line = line.split(None, 1)[1]

            if remove_zsh_prefix:
                line = re.split(r'\s+', line, maxsplit=4)[-1]

            if 'selecta' in line:
                continue

            if remove_duplicates and line in self.lines:
                continue

            self.lines.append(line)

        self.line_widgets = []

        self.line_count_display = LineCountWidget(len(self.lines))

        self.search_edit = SearchEdit(edit_text='')

        self.modifier_display = urwid.Text('')

        self.update_modifiers()

        urwid.connect_signal(self.search_edit, 'done', self.edit_done)
        urwid.connect_signal(self.search_edit, 'toggle_case_modifier', self.toggle_case_modifier)
        urwid.connect_signal(self.search_edit, 'toggle_regexp_modifier',
                             self.toggle_regexp_modifier)
        # urwid.connect_signal(self.search_edit, 'toggle_directory_modifier', self.toggle_directory_modifier)
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
        # self.loop.screen.set_terminal_properties(colors=256)
        self.loop.screen.set_terminal_properties(colors=2**24)

        self.line_count_display.update(len(self.item_list))

        # HACK workaround, when update_list is called directly, the linecount widget gets not updated
        self.loop.set_alarm_in(0.01, lambda *loop: self.update_list(''))
        self.loop.run()

    def list_resize(self, size):
        self.line_count_display.update(size[1])

    def toggle_case_modifier(self):
        self.case_modifier = not self.case_modifier
        self.update_modifiers()

    def toggle_regexp_modifier(self):
        self.regexp_modifier = not self.regexp_modifier
        self.update_modifiers()

    def toggle_directory_modifier(self):
        self.directory_modifier = not self.directory_modifier
        self.update_modifiers()

    def update_modifiers(self):
        modifiers = []
        if self.regexp_modifier:
            modifiers.append('regexp')
        if self.case_modifier:
            modifiers.append('case')

        # if self.directory_modifier_modifier:
        #     modifiers.append('directory')

        if len(modifiers) > 0:
            self.modifier_display.set_text(f'[{", ".join(modifiers)}]')
        else:
            self.modifier_display.set_text('')

    def update_with_regex(self, pattern):
        """Filter the list with a regular expression."""
        flags = 0
        if not self.case_modifier:
            flags |= re.IGNORECASE

        try:
            # debug(pattern)
            re_search = re.compile(pattern, flags).search

            items = []
            if False:
                for line in self.lines:
                    match = re_search(line)
                    if match:
                        if self.show_matches:
                            items.append(ItemWidgetPattern(line, match.group()))
                        else:
                            items.append(ItemWidgetPlain(line))
            else:
                # use faster(?) list comprehension
                # items = [ItemWidgetPattern(line, match.group()) if match and self.show_matches else ItemWidgetPlain(line)
                #          for line in self.lines if (match := re_search(line))]
                items = [ItemWidgetPattern(line, match.group()) if match and self.show_matches else ItemWidgetPlain(line)
                         for line in self.lines if (match := re_search(line))]

            if len(items) > 0:
                return items
            else:
                return [urwid.Text(('empty_list', '- no matches -'))]

        except re.error as err:
            return [urwid.Text(('empty_list', f'Error in regular epression: {err}'))]

    def update_with_words(self, search_text):
        """Filter the list with a list of words."""

        def check_all_words(subject, words):
            """Check if all words are in the subject."""
            if False:
                if not self.case_modifier:
                    return all(word.lower() in subject.lower() for word in words)
                else:
                    return all(word in subject for word in words)
            else:
                # slightly faster
                return (all(word.lower() in subject.lower() for word in words)
                        if not self.case_modifier else all(word in subject for word in words))

        words = search_text.split()
        return [ItemWidgetWords(line, search_words=words, case_modifier=self.case_modifier)
                for line in self.lines if check_all_words(line, words)]

    def update_list(self, search_text=''):
        """Filter the list with the given search criteria."""

        # show all lines if search_text is empty
        if search_text == '' or search_text == '"' or search_text == '""':
            self.item_list[:] = [ItemWidgetPlain(line) for line in self.lines]
            self.line_count_display.update(len(self.item_list))

        # search for whole string if search_text begins with quotation mark
        elif search_text.startswith('"'):
            self.item_list[:] = [ItemWidgetPlain(item) for item in self.lines if search_text.lstrip('"') in item]

        elif self.regexp_modifier:
            self.item_list[:] = self.update_with_regex(search_text)

        # split search into words and search for each word
        else:
            self.item_list[:] = self.update_with_words(search_text)

        if len(self.item_list) == 0:
            self.item_list[:] = [urwid.Text(('empty_list', '- empty result -'))]
        self.line_count_display.update(len(self.item_list))

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
            return False

        if input_ == 'enter':
            focused_widget = self.listbox.get_focus()[0]
            if focused_widget is not None:
                line = focused_widget.line
            else:
                return False

            self.view.set_header(urwid.AttrMap(
                urwid.Text(f'selected: {line}'), 'head'))

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

        return False

    def inject_line(self, command):
        """Inject the line into the terminal."""
        command = (struct.pack('B', c) for c in os.fsencode(command))

        fd = sys.stdin.fileno()
        for c in command:
            fcntl.ioctl(fd, termios.TIOCSTI, c)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--revert-order', action='store_true', default=False, help='revert the order of the lines')
    parser.add_argument('-b', '--remove-bash-prefix', action='store_true', default=False, help='remove the numeric prefix from bash history')
    parser.add_argument('-z', '--remove-zsh-prefix', action='store_true', default=False, help='remove the time prefix from zsh history')
    parser.add_argument('-r', '--regexp', action='store_true', default=False, help='start in regexp mode')
    parser.add_argument('-a', '--case-sensitive', action='store_true', default=False, help='start in case-sensitive mode')
    parser.add_argument('-d', '--remove-duplicates', action='store_true', default=False, help='remove duplicated lines')
    parser.add_argument('-y', '--show-matches', action='store_true', default=False, help='highlight the part of each line which match the substrings or regexp')
    parser.add_argument('--bash', action='store_true', default=False, help='standard for bash history search, same as -b -i -d')
    parser.add_argument('--zsh', action='store_true', default=False, help='standard for zsh history search, same as -b -i -d')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin, help='the file which lines you want to select eg. <(history)')
    parser.add_argument('-v', '--version', help='print selecta version', action='version', version='%(prog)s 0.2.0')

    args = parser.parse_args()

    # debug('\033[2J')

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
