import unittest
from pathlib import Path

import urwid

from selecta import Selecta, mark_parts, ItemWidgetPlain, ItemWidgetWords


class TestSelecta(unittest.TestCase):
    def __init__(self, *args, **kwargs) -> None:
        super(TestSelecta, self).__init__(*args, **kwargs)

    def run_test(self, file, input, reverse_order=False, bash_mode=False, zsh_mode=False,
                 regexp=False, case_sensitive=False, remove_duplicates=False, highlight_matches=False) -> Selecta:

        with open(Path(__file__).parent / 'data' / file, 'r') as fh:
            selecta = Selecta(
                infile=fh,
                reverse_order=reverse_order,
                bash_mode=bash_mode,
                zsh_mode=zsh_mode,
                regexp=regexp,
                case_sensitive=case_sensitive,
                remove_duplicates=remove_duplicates,
                highlight_matches=highlight_matches,
                test_mode=True,
            )

            selecta.loop.start()
            selecta.edit_change(None, input)
            selecta.edit_done(None)
            selecta.loop.stop()

            return selecta

    def test_words_default_rd(self) -> None:
        selecta = self.run_test('test.txt', 'app bana', remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 2)

    def test_words_default_nrd(self) -> None:
        selecta = self.run_test('test.txt', 'app bana')
        self.assertEqual(selecta.matching_line_count, 3)

    def test_words_case_sensitive(self) -> None:
        selecta = self.run_test('test.txt', 'Orange', case_sensitive=True, remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 1)

    def test_baz(self) -> None:
        selecta = self.run_test('test.txt', 'baz')
        self.assertEqual(selecta.matching_line_count, 0)

    def test_regex_default(self) -> None:
        selecta = self.run_test('test.txt', 'Or.+bana', regexp=True, case_sensitive=True, remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 1)

    def test_bash_prefix(self) -> None:
        selecta = self.run_test('test_history.txt', r'^[^\d]+$', regexp=True, bash_mode=True, remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 76)

    def test_sentence(self) -> None:
        selecta = self.run_test('test.txt', '"apple orange cherry')
        self.assertEqual(selecta.matching_line_count, 1)

    def test_empty_file(self) -> None:
        selecta = self.run_test('test_empty.txt', 'foo')
        self.assertEqual(selecta.matching_line_count, 0)

    def test_initial_query_prefills_search(self) -> None:
        with open(Path(__file__).parent / 'data' / 'test.txt', 'r') as fh:
            selecta = Selecta(
                infile=fh,
                reverse_order=False,
                remove_duplicates=True,
                initial_query='app bana',
                test_mode=True,
            )
        # the search box starts pre-filled and the list is filtered
        self.assertEqual(selecta.search_edit.get_edit_text(), 'app bana')
        self.assertEqual(selecta.matching_line_count, 2)

    def test_initial_query_default_shows_all(self) -> None:
        with open(Path(__file__).parent / 'data' / 'test.txt', 'r') as fh:
            selecta = Selecta(
                infile=fh,
                reverse_order=False,
                test_mode=True,
            )
        self.assertEqual(selecta.search_edit.get_edit_text(), '')
        self.assertEqual(selecta.matching_line_count, len(selecta.lines))

    def _selecta(self, **kwargs) -> Selecta:
        with open(Path(__file__).parent / 'data' / 'test.txt', 'r') as fh:
            return Selecta(infile=fh, reverse_order=False, test_mode=True, **kwargs)

    def test_narrowing_matches_full_scan(self) -> None:
        # extending the query narrows the previous result...
        selecta = self._selecta()
        selecta.edit_change(None, 'app')
        selecta.edit_change(None, 'app bana')  # extension -> narrows
        narrowed = selecta.matching_line_count

        # ...and must produce the same result as a fresh full scan
        fresh = self._selecta()
        fresh.edit_change(None, 'app bana')  # full scan
        self.assertEqual(narrowed, fresh.matching_line_count)
        self.assertGreater(narrowed, 0)

    def test_narrowing_not_reused_after_deletion(self) -> None:
        # deleting a character must fall back to a full scan
        selecta = self._selecta()
        selecta.edit_change(None, 'app bana')
        selecta.edit_change(None, 'app ban')  # shorter -> full rescan
        after_delete = selecta.matching_line_count

        fresh = self._selecta()
        fresh.edit_change(None, 'app ban')  # full scan
        self.assertEqual(after_delete, fresh.matching_line_count)

    def test_words_no_highlight_uses_plain_widgets(self) -> None:
        selecta = self._selecta()
        selecta.edit_change(None, 'app')
        self.assertIsInstance(selecta.item_list[0], ItemWidgetPlain)

    def test_words_highlight_uses_words_widgets(self) -> None:
        selecta = self._selecta(highlight_matches=True)
        selecta.edit_change(None, 'app')
        self.assertIsInstance(selecta.item_list[0], ItemWidgetWords)

    def test_toggle_case_from_body_refilters(self) -> None:
        selecta = self._selecta()
        selecta.search_edit.set_edit_text('Orange')
        selecta.edit_change(None, 'Orange')          # case-insensitive
        selecta.on_unhandled_input('ctrl a')         # toggle to case-sensitive
        toggled = selecta.matching_line_count

        fresh = self._selecta(case_sensitive=True)
        fresh.edit_change(None, 'Orange')
        self.assertEqual(toggled, fresh.matching_line_count)

    def test_toggle_regex_from_body_refilters(self) -> None:
        selecta = self._selecta()
        selecta.search_edit.set_edit_text('Or.+bana')
        selecta.edit_change(None, 'Or.+bana')        # words mode
        selecta.on_unhandled_input('ctrl r')         # toggle regexp on
        toggled = selecta.matching_line_count

        fresh = self._selecta(regexp=True)
        fresh.edit_change(None, 'Or.+bana')
        self.assertEqual(toggled, fresh.matching_line_count)

    def test_regex_no_match_count_zero(self) -> None:
        selecta = self._selecta(regexp=True)
        selecta.edit_change(None, 'zzz_nothing')
        self.assertEqual(selecta.matching_line_count, 0)

    def test_regex_error_count_zero(self) -> None:
        selecta = self._selecta(regexp=True)
        selecta.edit_change(None, '(')
        self.assertEqual(selecta.matching_line_count, 0)

    def test_literal_no_match_count_zero(self) -> None:
        selecta = self._selecta()
        selecta.edit_change(None, '"zzz_nothing')
        self.assertEqual(selecta.matching_line_count, 0)

    def test_selected_none_by_default(self) -> None:
        selecta = self._selecta()
        self.assertIsNone(selecta.selected)

    def test_enter_sets_selected(self) -> None:
        selecta = self._selecta()
        selecta.edit_change(None, 'apple')
        with self.assertRaises(urwid.ExitMainLoop):
            selecta.on_unhandled_input('enter')
        self.assertEqual(selecta.selected, 'apple orange cherry apple banana banana pear')

    def test_help_toggle(self) -> None:
        selecta = self._selecta()
        self.assertFalse(selecta.help_shown)
        selecta.on_unhandled_input('f1')
        self.assertTrue(selecta.help_shown)
        self.assertIs(selecta.view.body, selecta.help_box)
        selecta.on_unhandled_input('f1')
        self.assertFalse(selecta.help_shown)
        self.assertIs(selecta.view.body, selecta.listbox)

    def test_help_closes_on_esc(self) -> None:
        selecta = self._selecta()
        selecta.on_unhandled_input('f1')
        selecta.help_box.keypress((80,), 'esc')
        self.assertFalse(selecta.help_shown)
        self.assertIs(selecta.view.body, selecta.listbox)

    def test_mark_parts1(self) -> None:
        parts = mark_parts('orange cherry Orange apple Banana banana Pear apple', ['bana', 'apple', 'pear'], case_sensitive=False, highlight_matches=True)
        self.assertEqual(parts, ['orange cherry Orange ', ('match', 'apple'), ' ', ('match', 'Bana'), 'na ', ('match', 'bana'), 'na ', ('match', 'Pear'), ' ', ('match', 'apple')])

    def test_mark_parts2(self) -> None:
        parts = mark_parts('orange cherry Orange apple Banana banana Pear apple', ['cher', 'Bana'], case_sensitive=True, highlight_matches=True)
        self.assertEqual(parts, ['orange ', ('match', 'cher'), 'ry Orange apple ', ('match', 'Bana'), 'na banana Pear apple'])

    def test_mark_parts3(self) -> None:
        parts = mark_parts('apple orange cherry apple banana banana pear', ['pear', 'banana'], case_sensitive=True, highlight_matches=True)
        self.assertEqual(parts, ['apple orange cherry apple ', ('match', 'banana'), ' ', ('match', 'banana'), ' ', ('match', 'pear')])
