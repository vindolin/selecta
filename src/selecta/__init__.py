"""Selecta 0.2.0"""

import codecs
import fcntl
from io import TextIOWrapper
import os
import re
import signal
import struct
import sys
import termios
from typing import Union

import urwid

__version__ = '0.2.0'

__all__ = []


def inject_command(command: str) -> None:
    """Inject the line into the terminal."""
    fd = sys.stdin.fileno()
    for c in (struct.pack('B', c) for c in os.fsencode(command)):
        fcntl.ioctl(fd, termios.TIOCSTI, c)


def debug(value, prefix: str = '') -> None:
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

signal.signal(signal.SIGINT, lambda *_: sys.exit(0))  # perish in style


class ItemWidget(urwid.WidgetWrap):
    """Base for a widget for a single line in the listbox."""
    def selectable(self) -> bool:
        return True

    def keypress(self, _, key: str) -> str:
        return key


class ItemWidgetPlain(ItemWidget):
    """Widget that displays a line as is."""
    def __init__(self, line: str) -> None:
        self.line = line
        text = urwid.AttrMap(urwid.Text(self.line), 'line', 'line_focus')
        super().__init__(text)


class ItemWidgetStartswith(ItemWidget):
    """Widget that displays a line as is."""
    def __init__(self, line: str, search_text: str) -> None:
        self.line = line
        parts = [('match', part) if part == search_text else part
                 for part in re.split(f'({re.escape(search_text)})', self.line)]
        text = urwid.AttrMap(urwid.Text(parts), 'line', 'line_focus')
        super().__init__(text)


class ItemWidgetPattern(ItemWidget):
    """Widget that highlights the matching part of a line."""
    def __init__(self, line: str, match: str) -> None:
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


def mark_parts(subject_string: str, s_words: list[str], case_sensitive: bool, highlight_matches: bool) -> list[Union[str, tuple]]:
    def wrap_part(part) -> Union[str, (tuple[str, str])]:
        return ('match', part) if highlight_matches else part

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
    def __init__(self, line, search_words, case_modifier, highlight_matches) -> None:
        self.line = line

        text = urwid.AttrMap(
            urwid.Text(mark_parts(line, search_words, case_modifier, highlight_matches)),
            'line',
            {'match': 'match_focus', None: 'line_focus'}
        )
        super().__init__(text)

    def split_words(self, words, subject) -> list[str]:
        """Split the subject into pieces for later styling."""
        return [word for word in re.split(rf"({'|'.join(words)})", subject) if word]


class SearchEdit(urwid.Edit):
    """Edit widget for the search input."""

    signals = ['done', 'toggle_regexp_modifier', 'toggle_case_modifier']

    def keypress(self, size, key) -> None:
        if key == 'enter':
            urwid.emit_signal(self, 'done', self.get_edit_text())
            return
        elif key == 'esc':
            raise urwid.ExitMainLoop()
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

    def __init__(self, *args) -> None:
        self.last_size = None
        urwid.ListBox.__init__(self, *args)

    def render(self, size, focus=False) -> Union[urwid.CompositeCanvas, urwid.SolidCanvas]:
        if size != self.last_size:
            self.last_size = size
            urwid.emit_signal(self, 'resize', size)
        return urwid.ListBox.render(self, size, focus)


class LineCountWidget(urwid.Text):
    """Widget that displays the number of matching lines / total lines."""
    def __init__(self, line_count: int = 0) -> None:
        super().__init__('')
        self.line_count = line_count

    def update(self, matching_line_count) -> None:
        """Update the widget with the current number of matching lines."""
        self.set_text(f'{matching_line_count}/{self.line_count}')


class Selecta(object):
    """The main class of Selecta."""

    line_widgets: list = [urwid.Widget]

    def __init__(self, infile: TextIOWrapper, reverse_order: bool,
                 remove_bash_prefix: bool = False, remove_zsh_prefix: bool = False,
                 regexp: bool = False, case_sensitive: bool = False, remove_duplicates: bool = False,
                 highlight_matches: bool = False, test_mode: bool = False) -> None:

        self.highlight_matches = highlight_matches
        self.regexp_modifier = regexp
        self.case_modifier = case_sensitive

        self.lines = self.parse_lines(infile, reverse_order,
                                      remove_bash_prefix, remove_zsh_prefix, remove_duplicates)
        self.matching_line_count = len(self.lines)

        self.search_edit = SearchEdit(edit_text='')
        self.modifier_display = urwid.Text('')
        self.line_count_display = LineCountWidget(self.matching_line_count)
        header = urwid.AttrMap(urwid.Columns([
            urwid.AttrMap(self.search_edit, 'input', 'input'),
            self.modifier_display,
            ('pack', self.line_count_display),
        ], dividechars=1, focus_column=0), 'head', 'head')

        self.item_list: urwid.SimpleListWalker = urwid.SimpleListWalker(self.line_widgets)
        self.listbox = ResultList(self.item_list)
        self.view = urwid.Frame(body=self.listbox, header=header)

        urwid.connect_signal(self.search_edit, 'change', self.edit_change)
        urwid.connect_signal(self.search_edit, 'done', self.edit_done)

        urwid.connect_signal(self.search_edit, 'toggle_case_modifier',
                             lambda *_: self.toggle_modifier('case_modifier'))
        urwid.connect_signal(self.search_edit, 'toggle_regexp_modifier',
                             lambda *_: self.toggle_modifier('regexp_modifier'))

        urwid.connect_signal(self.listbox, 'resize', self.list_resize)

        self.update_modifiers()
        self.loop = urwid.MainLoop(self.view, palette, unhandled_input=self.on_unhandled_input)

        # find out what this pylint error means (happens from >=2.2.0)
        # Cannot access member "set_terminal_properties"
        # for type "BaseScreen" Member "set_terminal_properties" is unknown
        # it doesn't seem to be a problem though
        self.loop.screen.set_terminal_properties(colors=256)  # type: ignore - make pylance happy
        # self.loop.screen.set_terminal_properties(colors=2**24)

        self.update_list('')

        if not test_mode:
            self.loop.run()

    def parse_lines(self, infile: TextIOWrapper, reverse_order: bool,
                    remove_bash_prefix: bool, remove_zsh_prefix: bool, remove_duplicates: bool) -> list[str]:
        """Get the lines from the infile."""

        lines: list[str] = []
        if reverse_order:
            lines_ = reversed(infile.readlines())
        else:
            lines_ = infile

        for line in lines_:
            line = line.strip()
            # remove bash/zsh line numbers from the beginning of the line
            if remove_bash_prefix or remove_zsh_prefix:
                try:
                    line = line.split(None, 1)[1]
                except IndexError:
                    pass  # ignore lines without prefix

            # zsh legacy line = re.split(r'\s+', line, maxsplit=4)[-1]

            if remove_duplicates and line in lines:
                continue

            lines.append(line)

        return lines
    # [ItemWidgetPlain(line) for line in self.lines]

    def update_item_list(self, items: list) -> None:
        """Update the list of items."""
        self.item_list[:] = items  # itemList is a SimpleListWalker which monitors the list for changes
        self.matching_line_count = len(self.item_list)
        self.line_count_display.update(self.matching_line_count)

    def list_resize(self, size) -> None:
        """get's called when the window is resized"""

    def toggle_modifier(self, modifier: str) -> None:
        setattr(self, modifier, not getattr(self, modifier))
        self.update_modifiers()

    def update_modifiers(self) -> None:
        """Update the modifier display"""
        modifiers: list = []
        if self.regexp_modifier:
            modifiers.append('regexp')
        if self.case_modifier:
            modifiers.append('case')
        # if self.fuzzy_modifier:
        #     modifiers.append('fuzzy')

        if len(modifiers) > 0:
            self.modifier_display.set_text(f'[{", ".join(modifiers)}]')
        else:
            self.modifier_display.set_text('')

    def filter_regex(self, pattern: str) -> list:
        """Filter the list with a regular expression."""

        flags = re.IGNORECASE if not self.case_modifier else 0

        try:
            re_search = re.compile(pattern, flags).search

            if False:
                items = []
                for line in self.lines:
                    match = re_search(line)
                    if match:
                        if self.highlight_matches:
                            items.append(ItemWidgetPattern(line, match.group()))
                        else:
                            items.append(ItemWidgetPlain(line))
            else:
                # use faster(?) list comprehension
                items = [ItemWidgetPattern(line, match.group())
                         if match and self.highlight_matches else ItemWidgetPlain(line)
                         for line in self.lines if (match := re_search(line))]

            if len(items) > 0:
                return items
            else:
                return [urwid.Text(('empty_list', '- no matches -'))]

        except re.error as err:
            return [urwid.Text(('empty_list', f'Error in regular epression: {err}'))]

    def filter_words(self, search_text: str) -> list[urwid.Widget]:
        """Filter the list with a list of words."""

        def check_all_words(subject, words) -> bool:
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

        return [ItemWidgetWords(line, search_words=words,
                                case_modifier=self.case_modifier, highlight_matches=self.highlight_matches)
                for line in self.lines if check_all_words(line, words)]

    def update_list(self, search_text: str = '') -> None:
        """Filter the list with the given search criteria."""

        # show all lines if search_text is empty
        if search_text == '' or search_text == '"' or search_text == '""':
            self.update_item_list([ItemWidgetPlain(line) for line in self.lines])

        # search for whole string if search_text begins with quotation mark
        elif search_text.startswith('"'):
            search_text = search_text[1:]
            self.update_item_list([
                ItemWidgetStartswith(line, search_text) if self.highlight_matches else ItemWidgetPlain(line)
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

    def edit_change(self, _, search_text) -> None:
        self.update_list(search_text)

    def edit_done(self, _) -> None:
        self.view.focus_position = 'body'

    def on_unhandled_input(self, input) -> bool:
        if isinstance(input, tuple):  # mouse events
            return False

        if input == 'enter':
            focused_widget = self.listbox.get_focus()[0]

            if focused_widget is None:
                return False

            if isinstance(focused_widget, urwid.Text):
                return False

            line = focused_widget.line

            self.view.set_header(urwid.AttrMap(
                urwid.Text(f'selected: {line}'), 'head'))

            inject_command(line)
            raise urwid.ExitMainLoop()

        elif input == 'ctrl a':
            self.toggle_modifier('case_modifier')

        elif input == 'ctrl r':
            self.toggle_modifier('regexp_modifier')

        # elif input_ == 'ctrl f':
        #     self.toggle_modifier('fuzzy_modifier')

        elif input == 'backspace':
            self.search_edit.set_edit_text(self.search_edit.get_text()[0][:-1])
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        elif input == 'esc':
            self.view.set_focus('header')

        elif len(input) == 1:  # ignore things like tab, enter
            self.search_edit.set_edit_text(self.search_edit.get_text()[0] + input)
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        return False


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--reverse-order',
                        action='store_true', default=False,
                        help='reverse the order of the lines')

    parser.add_argument('-b', '--remove-bash-prefix',
                        action='store_true', default=False,
                        help='remove the numeric prefix from bash history')

    parser.add_argument('-z', '--remove-zsh-prefix',
                        action='store_true', default=False,
                        help='remove the time prefix from zsh history')

    parser.add_argument('-r', '--regexp',
                        action='store_true', default=False,
                        help='start in regexp mode')

    parser.add_argument('-a', '--case-sensitive',
                        action='store_true', default=False,
                        help='start in case-sensitive mode')

    parser.add_argument('-d', '--remove-duplicates',
                        action='store_true', default=False,
                        help='remove duplicated lines')

    parser.add_argument('-y', '--highlight-matches',
                        action='store_true', default=False,
                        help='highlight the part of each line which match the substrings or regexp')

    parser.add_argument('--bash', action='store_true',
                        default=False, help='standard for bash history search, same as -b -i -d')

    parser.add_argument('--zsh', action='store_true',
                        default=False, help='standard for zsh history search, same as -z -i -d')

    parser.add_argument('infile', nargs='?',
                        type=argparse.FileType('r'), default=sys.stdin,
                        help='the file which lines you want to select eg. <(history)')

    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}',
                        help='print selecta version')

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
        args.reverse_order = True
        args.remove_duplicates = True

    Selecta(
        infile=args.infile,
        reverse_order=args.reverse_order,
        remove_bash_prefix=args.remove_bash_prefix,
        remove_zsh_prefix=args.remove_zsh_prefix,
        regexp=args.regexp,
        case_sensitive=args.case_sensitive,
        remove_duplicates=args.remove_duplicates,
        highlight_matches=args.highlight_matches,
        # TODO support missing options from the original selector
        # TODO directory history would be sweet!
    )


if __name__ == '__main__':
    main()
