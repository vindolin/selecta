import unittest
from pathlib import Path
from selecta import Selecta, mark_parts


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
        selecta = self.run_test('test.txt', '"orange cherry apple banana banana pe')
        self.assertEqual(selecta.matching_line_count, 1)

    def test_empty_file(self) -> None:
        selecta = self.run_test('test_empty.txt', 'foo')
        self.assertEqual(selecta.matching_line_count, 0)

    def test_mark_parts1(self) -> None:
        parts = mark_parts('orange cherry Orange apple Banana banana Pear apple', ['bana', 'apple', 'pear'], case_sensitive=False, highlight_matches=True)
        self.assertEqual(parts, ['orange cherry Orange ', ('match', 'apple'), ' ', ('match', 'Bana'), 'na ', ('match', 'bana'), 'na ', ('match', 'Pear'), ' ', ('match', 'apple')])

    def test_mark_parts2(self) -> None:
        parts = mark_parts('orange cherry Orange apple Banana banana Pear apple', ['cher', 'Bana'], case_sensitive=True, highlight_matches=True)
        self.assertEqual(parts, ['orange ', ('match', 'cher'), 'ry Orange apple ', ('match', 'Bana'), 'na banana Pear apple'])

    def test_mark_parts3(self) -> None:
        parts = mark_parts('apple orange cherry apple banana banana pear', ['pear', 'banana'], case_sensitive=True, highlight_matches=True)
        self.assertEqual(parts, ['apple orange cherry apple ', ('match', 'banana'), ' ', ('match', 'banana'), ' ', ('match', 'pear')])
