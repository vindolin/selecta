"""Selecta 0.3.0"""

import codecs
import fcntl
from io import TextIOWrapper
import os
import re
import signal
import struct
import sys
import termios
from typing import Optional, Sequence, Union

import urwid

__version__ = '0.3.0'

__all__ = []


def inject_command(command: str) -> None:
    """Inject the line into the terminal using TIOCSTI (legacy, disabled on Linux 6.2+)."""
    fd = sys.stdin.fileno()
    try:
        for c in (struct.pack('B', c) for c in os.fsencode(command)):
            fcntl.ioctl(fd, termios.TIOCSTI, c)
    except Exception as e:
        print(
            f'Error injecting command: {e}.\n'
            'TIOCSTI is disabled on modern Linux kernels (6.2+).\n'
            'Use --print (-p) mode with the shell wrapper function instead.\n'
            'See https://github.com/vindolin/selecta for updated setup instructions.',
            file=sys.stderr,
        )

def debug(value, prefix: str = '') -> None:
    """only usded when debugging"""
    return
    with codecs.open('/tmp/selecta.log', 'a', encoding='utf-8') as file:
        file.write(f'{prefix} {value}\n')


palette: list[tuple[str, str, str, str, str, str]] = [
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


class ItemWidgetLiteral(ItemWidget):
    """Widget that highlights the literal search string in a line."""
    def __init__(self, line: str, search_text: str) -> None:
        self.line = line
        parts = [('match', part) if part == search_text else part
                 for part in re.split(f'({re.escape(search_text)})', self.line)]
        text = urwid.AttrMap(
            urwid.Text(parts),
            'line',
            {'match': 'match_focus', None: 'line_focus'}
        )
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


def mark_parts(subject_string: str, s_words: list[str], case_sensitive: bool,
               highlight_matches: bool, split_re=None) -> list[Union[str, tuple]]:
    """Split the subject on the search words, marking the matching parts.

    ``split_re`` is an optional precompiled regex; when given it is reused
    instead of building/recompiling the pattern here (the caller can compile
    it once per keystroke rather than once per line).
    """
    def wrap_part(part: 'str') -> Union[str, (tuple[str, str])]:
        return ('match', part) if highlight_matches else part

    if split_re is None:
        flags = re.IGNORECASE if not case_sensitive else 0
        split_re = re.compile(rf"({'|'.join([re.escape(word) for word in s_words])})", flags)

    # split subject at word boundaries
    s_parts = [s_word for s_word in split_re.split(subject_string) if s_word]

    # create list of search words as lookup list,
    s_words_x = s_words if case_sensitive else [s_word.lower()
                                                for s_word in s_words]

    # mark the search words (list comprehension)
    l_parts = [wrap_part(word) if (word if case_sensitive else word.lower())
               in s_words_x else word for word in s_parts]

    return l_parts


class ItemWidgetWords(ItemWidget):
    """Widget that highlights the matching words of a line.

    The line is rendered as-is until the widget is actually drawn; only then
    is it split and highlighted. Since urwid only renders the visible rows,
    lines that are never shown never pay the split cost.
    """
    def __init__(self, line: str, search_words: list[str], case_modifier: bool,
                 highlight_matches: bool, split_re=None) -> None:
        self.line = line
        self.search_words = search_words
        self.case_modifier = case_modifier
        self.highlight_matches = highlight_matches
        self.split_re = split_re

        # start with the plain line so layout/rows are correct before decoration
        self._text = urwid.Text(line)
        self._decorated = False
        text = urwid.AttrMap(self._text, 'line', {'match': 'match_focus', None: 'line_focus'})
        super().__init__(text)

    def render(self, size, focus=False):
        if not self._decorated and self.highlight_matches:
            self._decorated = True
            parts = mark_parts(self.line, self.search_words, self.case_modifier,
                               True, self.split_re)
            self._text.set_text(parts)
        return super().render(size, focus)


class SearchEdit(urwid.Edit):
    """Edit widget for the search input."""

    signals = ['done', 'toggle_regexp_modifier', 'toggle_case_modifier']

    def keypress(self, size: tuple[int], key: str) -> None:
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


class LineCountWidget(urwid.Text):
    """Widget that displays the number of matching lines / total lines."""
    def __init__(self, line_count: int = 0) -> None:
        super().__init__('')
        self.line_count = line_count

    def update(self, matching_line_count: int) -> None:
        """Update the widget with the current number of matching lines."""
        self.set_text(f'{matching_line_count}/{self.line_count}')


class Selecta(object):
    """The main class of Selecta."""

    line_widgets: list = [urwid.Widget]
    lines: list[str] = []
    lower_lines: list[str] = []

    def __init__(self, infile: TextIOWrapper, reverse_order: bool,
                 bash_mode: bool = False, zsh_mode: bool = False,
                 case_sensitive: bool = False, regexp: bool = False,
                 remove_duplicates: bool = False, highlight_matches: bool = False,
                 test_mode: bool = False,
                 screen: Optional[urwid.BaseScreen] = None,
                 initial_query: str = '') -> None:

        self.highlight_matches = highlight_matches
        self.regexp_modifier = regexp
        self.case_modifier = case_sensitive
        self.regexp_modifier = regexp

        self.lines = self.parse_lines(infile, reverse_order, bash_mode, zsh_mode, remove_duplicates)
        # pre-lower the lines once so case-insensitive filtering never has to
        # call .lower() on every line on every keystroke
        self.lower_lines = [line.lower() for line in self.lines]
        self.matching_line_count = len(self.lines)

        # cache of the last words-mode filter, used to narrow the scan while typing
        self._filter_cache = None
        # the line selected when the user presses enter (None if cancelled)
        self.selected: Optional[str] = None

        self.search_edit = SearchEdit(edit_text=initial_query)
        self.modifier_display = urwid.Text('')
        self.line_count_display = LineCountWidget(self.matching_line_count)
        header = urwid.AttrMap(urwid.Columns([
            urwid.AttrMap(self.search_edit, 'input', 'input'),
            self.modifier_display,
            ('pack', self.line_count_display),
        ], dividechars=1, focus_column=0), 'head', 'head')

        self.item_list: urwid.SimpleListWalker = urwid.SimpleListWalker(self.line_widgets)
        self.listbox = urwid.ListBox(self.item_list)
        self.view = urwid.Frame(body=self.listbox, header=header)

        urwid.connect_signal(self.search_edit, 'change', self.edit_change)
        urwid.connect_signal(self.search_edit, 'done', self.edit_done)

        urwid.connect_signal(self.search_edit, 'toggle_case_modifier',
                             lambda *_: self.toggle_modifier('case_modifier'))
        urwid.connect_signal(self.search_edit, 'toggle_regexp_modifier',
                             lambda *_: self.toggle_modifier('regexp_modifier'))

        self.update_modifiers()
        loop_kwargs = dict(
            unhandled_input=self.on_unhandled_input,
        )
        if screen is not None:
            loop_kwargs['screen'] = screen

        self.loop = urwid.MainLoop(self.view, palette, **loop_kwargs)

        # find out what this pylint error means (happens from >=2.2.0)
        # Cannot access member "set_terminal_properties"
        # for type "BaseScreen" Member "set_terminal_properties" is unknown
        # it doesn't seem to be a problem though
        self.loop.screen.set_terminal_properties(colors=256)  # type: ignore - make pylance happy
        # self.loop.screen.set_terminal_properties(colors=2**24)

        self.update_list(initial_query)

    def run(self) -> Optional[str]:
        """Run the UI loop and return the selected line, or None if cancelled."""
        self.loop.run()
        return self.selected

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

    def update_item_list(self, items: list, count: Optional[int] = None) -> None:
        """Update the list of items.

        ``count`` optionally overrides the match count shown in the header; it's
        needed when ``items`` contains placeholder widgets (e.g. an "no matches"
        message) that don't represent real matches.
        """
        self.item_list[:] = items  # itemList is a SimpleListWalker which monitors the list for changes
        self.matching_line_count = count if count is not None else len(self.item_list)
        self.line_count_display.update(self.matching_line_count)

    def toggle_modifier(self, modifier: str) -> None:
        setattr(self, modifier, not getattr(self, modifier))
        self.update_modifiers()

    def update_modifiers(self) -> None:
        """Update the modifier display"""
        modifiers: set[str] = set()
        if self.regexp_modifier:
            modifiers.add('regexp')
        if self.case_modifier:
            modifiers.add('case')

        if len(modifiers) > 0:
            self.modifier_display.set_text(f'[{", ".join(modifiers)}]')
        else:
            self.modifier_display.set_text('')

    def filter_regex(self, pattern: str) -> tuple[list[urwid.Widget], int]:
        """Filter the list with a regular expression.

        Returns the widgets (including any placeholder message) and the number
        of actual matches.
        """

        flags = re.IGNORECASE if not self.case_modifier else 0

        try:
            re_search = re.compile(pattern, flags).search

            if self.highlight_matches:
                items: list[urwid.Widget] = [ItemWidgetPattern(line, match.group())
                                             for line in self.lines if (match := re_search(line))]
            else:
                items = [ItemWidgetPlain(line)
                         for line in self.lines if re_search(line)]

            if len(items) > 0:
                return items, len(items)
            else:
                return [urwid.Text(('empty_list', '- no matches -'))], 0

        except re.error as err:
            return [urwid.Text(('empty_list', f'Error in regular epression: {err}'))], 0

    def filter_words(self, search_text: str, indices: Optional[Sequence[int]] = None) -> tuple[list[urwid.Widget], list[int]]:
        """Filter the list with a list of words.

        ``indices`` optionally restricts the scan to a subset of line indices
        (used to narrow the previous result while the query is being extended).
        Returns the widgets and the indices of the matching lines.
        """
        if indices is None:
            indices = range(len(self.lines))

        words = search_text.split()

        if self.case_modifier:
            matched = [i for i in indices
                       if all(word in self.lines[i] for word in words)]
        else:
            lowered_words = [word.lower() for word in words]
            matched = [i for i in indices
                       if all(word in self.lower_lines[i] for word in lowered_words)]

        if self.highlight_matches:
            # compile the split regex once per keystroke, not once per line
            split_re = re.compile(rf"({'|'.join(re.escape(word) for word in words)})",
                                  re.IGNORECASE if not self.case_modifier else 0)
            items = [ItemWidgetWords(self.lines[i], words, self.case_modifier, True, split_re)
                     for i in matched]
        else:
            # no highlighting needed: skip the split entirely
            items = [ItemWidgetPlain(self.lines[i]) for i in matched]

        return items, matched

    def filter_literal(self, search_text: str) -> tuple[list[urwid.Widget], int]:
        search_text = search_text.strip('"')  # quote marks were only used to indicate literal search
        items: list[urwid.Widget] = []
        for line in self.lines:
            if line.startswith(search_text):  # filter out matching lines
                if self.highlight_matches:
                    items.append(ItemWidgetLiteral(line, search_text))
                else:
                    items.append(ItemWidgetPlain(line))

        if len(items) > 0:
            return items, len(items)
        else:
            return [urwid.Text(('empty_list', '- no matches -'))], 0

    def update_list(self, search_text: str = '') -> None:
        """Filter the list with the given search criteria."""

        # show all lines if search_text is empty
        if search_text == '' or search_text == '"' or search_text == '""':
            self._filter_cache = None
            self.update_item_list([ItemWidgetPlain(line) for line in self.lines])

        # search for whole string if search_text begins with quotation mark
        elif search_text.startswith('"'):
            self._filter_cache = None
            items, count = self.filter_literal(search_text)
            self.update_item_list(items, count)

        # search for regexp if regexp modifier is set
        elif self.regexp_modifier:
            self._filter_cache = None
            items, count = self.filter_regex(search_text)
            self.update_item_list(items, count)

        # split search into words and search for each word
        else:
            # while typing, extend the previous result instead of rescanning all
            # lines: any line matching the longer query also matched the shorter
            # one, so the new match set is a subset of the previous one
            indices = None
            cache = self._filter_cache
            if (cache is not None
                    and cache[1] == 'words'
                    and cache[2] == self.case_modifier
                    and search_text.startswith(cache[0])
                    and search_text != cache[0]):
                indices = cache[3]

            items, matched = self.filter_words(search_text, indices=indices)
            self._filter_cache = (search_text, 'words', self.case_modifier, matched)
            self.update_item_list(items)

        # show empty list message if no items are found
        if len(self.item_list) == 0:
            self.item_list[:] = [urwid.Text(('empty_list', '- empty result -'))]
            self.matching_line_count = 0
            self.line_count_display.update(self.matching_line_count)

        self.item_list.set_focus(0)

    def edit_change(self, _, search_text) -> None:
        self.update_list(search_text.strip())

    def edit_done(self, _) -> None:
        self.view.focus_position = 'body'

    def on_unhandled_input(self, key: Union[str, tuple[str, int, int, int]]) -> bool:
        if isinstance(key, tuple):  # mouse events
            return False

        if key == 'enter':
            focused_widget = self.listbox.get_focus()[0]

            if focused_widget is None:
                return False

            if isinstance(focused_widget, urwid.Text):
                return False

            line = focused_widget.line

            self.view.set_header(urwid.AttrMap(
                urwid.Text(f'selected: {line}'), 'head'))

            self.selected = line
            raise urwid.ExitMainLoop()

        elif key == 'ctrl a':
            self.toggle_modifier('case_modifier')
            self.update_list(self.search_edit.get_edit_text().strip())

        elif key == 'ctrl r':
            self.toggle_modifier('regexp_modifier')
            self.update_list(self.search_edit.get_edit_text().strip())

        # elif key == 'ctrl f':
        #     self.toggle_modifier('fuzzy_modifier')

        elif key == 'backspace':
            self.search_edit.set_edit_text(self.search_edit.get_text()[0][:-1])
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        elif key == 'f1':
            if (self.view.get_footer() is None):
                self.view.set_footer(urwid.AttrMap(urwid.Text(f'selecta v{__version__}', align='center'), 'head'))
            else:
                self.view.set_footer(None)

        elif key == 'esc':
            self.view.set_focus('header')

        elif len(key) == 1:  # ignore things like tab, enter
            self.search_edit.set_edit_text(self.search_edit.get_text()[0] + key)
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        return False


def main() -> None:
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))  # perish in style
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--reverse-order',
                        action='store_true', default=False,
                        help='reverse the order of the lines')

    parser.add_argument('-b', '--remove-bash-prefix', dest='bash_mode',
                        action='store_true', default=False,
                        help='remove the numeric prefix from bash history')

    parser.add_argument('-z', '--remove-zsh-prefix', dest='zsh_mode',
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

    parser.add_argument('infile', nargs='?',
                        type=argparse.FileType('r'), default=sys.stdin,
                        help='the file which lines you want to select eg. <(history)')

    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}',
                        help='print selecta version')

    parser.add_argument('-p', '--print', dest='print_result',
                        action='store_true', default=False,
                        help='print the selected command to stdout (use with shell wrapper for TIOCSTI-free operation)')

    parser.add_argument('-q', '--query', default='',
                        help='initial search string (e.g. the current shell command line)')

    args = parser.parse_args()

    # debug('\033[2J')

    # if no infile is given, print help and exit
    if args.infile.name == '<stdin>':
        parser.print_help()
        parser.exit(2, '\nYou must provide an infile!\n')

    if args.bash_mode or args.zsh_mode:
        args.reverse_order = True
        args.remove_duplicates = True

    # In print mode, redirect the TUI to /dev/tty so stdout is free for the result
    screen = None
    if args.print_result:
        try:
            tty_output = open('/dev/tty', 'w')
            screen = urwid.raw_display.Screen(output=tty_output)
        except (IOError, OSError):
            print('Error: could not open /dev/tty for TUI output', file=sys.stderr)
            sys.exit(1)

    selected = Selecta(
        infile=args.infile,
        reverse_order=args.reverse_order,
        bash_mode=args.bash_mode,
        zsh_mode=args.zsh_mode,
        case_sensitive=args.case_sensitive,
        regexp=args.regexp,
        remove_duplicates=args.remove_duplicates,
        highlight_matches=args.highlight_matches,
        screen=screen,
        initial_query=args.query,
        # TODO support missing options from the original selector
        # TODO directory history would be sweet!
    ).run()
    if selected is not None:
        if args.print_result:
            print(selected)
        else:
            inject_command(selected)


if __name__ == '__main__':
    main()

