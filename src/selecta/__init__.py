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

__version__ = '0.2.0'

__all__ = []


def debug(value, prefix=''):
    """only usded when debugging"""
    with codecs.open('/tmp/selecta.log', 'a', encoding='utf-8') as file:
        file.write(f'{prefix} {value}\n')


palette = [
    ('head', '', '', '', '#bbb', '#618'),
    ('body', '', '', '', '#ddd', '#000'),
    ('focus', '', '', '', '#000', '#da0'),
    ('input', '', '', '', '#fff', '#618'),
    ('empty_list', '', '', '', '#ddd', '#b00'),
    ('match', '', '', '', '#f91', ''),
    ('match_focus', '', '', '', 'bold,#a00', '#da0'),
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


class ItemWidgetStartswith(ItemWidget):
    """Widget that displays a line as is."""
    def __init__(self, line, search_text):
        self.line = line
        parts = [('match', part) if part == search_text else part
                 for part in re.split(f'({re.escape(search_text)})', self.line)]
        text = urwid.AttrMap(urwid.Text(parts), 'line', 'line_focus')
        super().__init__(text)


class ItemWidgetPattern(ItemWidget):
    """Widget that highlights the matching part of a line."""
    def __init__(self, line, match):
        self.line = line

        # highlight the matches
        matches = re.split(f'({re.escape(match)})', self.line)

        parts = [('match', part) if part == match else part
                 for part in matches]

        text = urwid.AttrMap(
            urwid.Text(parts),
            'line',
            {'match': 'match_focus', None: 'line_focus'}
        )

        super().__init__(text)


def mark_parts(subject_string, s_words, case_sensitive=False):
    def wrap_part(part):
        return ('match', part)

    flags = re.IGNORECASE if not case_sensitive else 0

    # split sub string at word boundaries
    s_parts = ([s_word for s_word in
                re.split(rf"({'|'.join([re.escape(word) for word in s_words])})",
                         subject_string, flags=flags) if s_word])

    # create list of search words as lookup list,
    s_words_x = s_words if case_sensitive else [s_word.lower()
                                                for s_word in s_words]

    # generate list of the word parts and mark the search words
    if False:
        # use regular for loop
        l_parts = []
        for word in s_parts:
            word_x = word if case_sensitive else word.lower()
            l_parts.append(wrap_part(word) if word_x in s_words_x else word)
    else:
        # use faster(?) list comprehension
        l_parts = [wrap_part(word) if (word if case_sensitive else word.lower())
                   in s_words_x else word for word in s_parts]

    return l_parts


class ItemWidgetWords(ItemWidget):
    """Widget that highlights the matching words of a line."""
    def __init__(self, line, search_words, case_modifier=False):
        self.line = line

        text = urwid.AttrMap(
            urwid.Text(mark_parts(line, search_words, case_modifier)),
            'line',
            {'match': 'match_focus', None: 'line_focus'}
        )
        super().__init__(text)

    def split_words(self, words, subject):
        """Split the subject into pieces for later styling."""
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

    def update(self, matching_line_count):
        """Update the widget with the current number of matching lines."""
        self.set_text(f'{matching_line_count}/{self.line_count}')


class Selector(object):
    """The main class of Selecta."""

    matching_line_count = 0
    show_matches = False
    regexp_modifier = False
    case_modifier = False
    remove_bash_prefix = False
    line_widgets = []
    lines = []

    def __init__(self, revert_order, remove_bash_prefix, remove_zsh_prefix, regexp, case_sensitive,
                 remove_duplicates, show_matches, infile):

        self.show_matches = show_matches
        self.regexp_modifier = regexp
        self.case_modifier = case_sensitive
        self.remove_bash_prefix = remove_bash_prefix

        if revert_order:
            lines = reversed(infile.readlines())
        else:
            lines = infile

        for line in lines:
            line = line.strip()
            if remove_bash_prefix:
                line = line.split(None, 1)[1]

            if remove_zsh_prefix:
                line = line.split(None, 1)[1]
                # legacy line = re.split(r'\s+', line, maxsplit=4)[-1]

            if remove_duplicates and line in self.lines:
                continue

            self.lines.append(line)

        self.matching_line_count = len(self.lines)

        self.search_edit = SearchEdit(edit_text='')
        self.modifier_display = urwid.Text('')
        self.line_count_display = LineCountWidget(self.matching_line_count)
        header = urwid.AttrMap(urwid.Columns([
            urwid.AttrMap(self.search_edit, 'input', 'input'),
            self.modifier_display,
            ('pack', self.line_count_display),
        ], dividechars=1, focus_column=0), 'head', 'head')

        self.item_list = urwid.SimpleListWalker(self.line_widgets)
        self.listbox = ResultList(self.item_list)
        self.view = urwid.Frame(body=self.listbox, header=header)

        urwid.connect_signal(self.search_edit, 'change', self.edit_change)
        urwid.connect_signal(self.search_edit, 'done', self.edit_done)

        urwid.connect_signal(self.search_edit, 'toggle_case_modifier', lambda *_: self.toggle_modifier('case_modifier'))
        urwid.connect_signal(self.search_edit, 'toggle_regexp_modifier', lambda *_: self.toggle_modifier('regexp_modifier'))

        urwid.connect_signal(self.listbox, 'resize', self.list_resize)

        self.update_modifiers()
        self.loop = urwid.MainLoop(self.view, palette, unhandled_input=self.on_unhandled_input)

        # find out what this pylint error means (happens from >=2.2.0)
        # Cannot access member "set_terminal_properties" for type "BaseScreen" Member "set_terminal_properties" is unknown
        # it doesn't seem to be a problem though
        self.loop.screen.set_terminal_properties(colors=256)
        # self.loop.screen.set_terminal_properties(colors=2**24)

        self.line_count_display.update(self.matching_line_count)
        self.update_list('')

        self.loop.run()

    def update_item_list(self, items):
        """Update the list of items."""
        self.item_list[:] = items  # itemList is a SimpleListWalker which monitors the list for changes
        self.matching_line_count = len(self.item_list)
        self.line_count_display.update(self.matching_line_count)

    def list_resize(self, size):
        pass

    def toggle_modifier(self, modifier):
        setattr(self, modifier, not getattr(self, modifier))
        self.update_modifiers()

    def update_modifiers(self):
        """Update the modifier display"""
        modifiers = []
        if self.regexp_modifier:
            modifiers.append('regexp')
        if self.case_modifier:
            modifiers.append('case')

        if len(modifiers) > 0:
            self.modifier_display.set_text(f'[{", ".join(modifiers)}]')
        else:
            self.modifier_display.set_text('')

    def filter_regex(self, pattern):
        """Filter the list with a regular expression."""

        flags = re.IGNORECASE if not self.case_modifier else 0

        try:
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
                items = [ItemWidgetPattern(line, match.group())
                         if match and self.show_matches else ItemWidgetPlain(line)
                         for line in self.lines if (match := re_search(line))]

            if len(items) > 0:
                return items
            else:
                return [urwid.Text(('empty_list', '- no matches -'))]

        except re.error as err:
            return [urwid.Text(('empty_list', f'Error in regular epression: {err}'))]

    def filter_words(self, search_text):
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
            self.update_item_list([ItemWidgetPlain(line) for line in self.lines])

        # search for whole string if search_text begins with quotation mark
        elif search_text.startswith('"'):
            search_text = search_text[1:]
            self.update_item_list([
                ItemWidgetStartswith(line, search_text) if self.show_matches else ItemWidgetPlain(line)
                for line in self.lines if search_text in line])

        elif self.regexp_modifier:
            self.update_item_list(self.filter_regex(search_text))

        # split search into words and search for each word
        else:
            self.update_item_list(self.filter_words(search_text))

        # show empty list message if no items are found
        if len(self.item_list) == 0:
            self.item_list[:] = [urwid.Text(('empty_list', '- empty result -'))]
            self.matching_line_count = 0
            self.line_count_display.update(self.matching_line_count)

        self.item_list.set_focus(0)

    def edit_change(self, _, search_text):
        self.update_list(search_text)

    def edit_done(self, _):
        self.view.set_focus('body')

    def on_unhandled_input(self, input_):
        if isinstance(input_, tuple):  # mouse events
            return False

        if input_ == 'enter':
            focused_widget = self.listbox.get_focus()[0]

            if focused_widget is None:
                return False

            if isinstance(focused_widget, urwid.Text):
                return False

            line = focused_widget.line

            self.view.set_header(urwid.AttrMap(
                urwid.Text(f'selected: {line}'), 'head'))

            self.inject_line(line)
            raise urwid.ExitMainLoop()

        elif input_ == 'ctrl a':
            self.toggle_modifier('case_modifier')

        elif input_ == 'ctrl r':
            self.toggle_modifier('regexp_modifier')

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

        return False

    def inject_line(self, command):
        """Inject the line into the terminal."""
        fd = sys.stdin.fileno()
        for c in (struct.pack('B', c) for c in os.fsencode(command)):
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
    parser.add_argument('-v', '--version', help='print selecta version', action='version', version=f'%(prog)s {__version__}')

    args = parser.parse_args()

    # debug('\033[2J')

    # if no infile is given, print help and exit
    if args.infile.name == '<stdin>':
        parser.print_help()
        exit('\nYou must provide an infile!')

    if args.bash:
        args.remove_bash_prefix = True

    if args.zsh:
        args.remove_zsh_prefix = True

    if args.bash or args.zsh:
        args.revert_order = True
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
