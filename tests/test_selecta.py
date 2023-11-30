import unittest
from pathlib import Path
from selecta import Selecta, mark_parts


class TestSelecta(unittest.TestCase):
    def __init__(self, *args, **kwargs) -> None:
        super(TestSelecta, self).__init__(*args, **kwargs)

    def run_test(self, file_name: str, input: str, reverse_order: bool = False, bash_mode: bool = False,
                 zsh_mode: bool = False, case_sensitive: bool = False, regexp: bool = False,
                 path_mode: bool = False, remove_duplicates: bool = False,
                 highlight_matches: bool = False) -> Selecta:

        with open(Path(__file__).parent / 'data' / file_name, 'r') as fh:
            selecta = Selecta(
                infile=fh,
                reverse_order=reverse_order,
                bash_mode=bash_mode,
                zsh_mode=zsh_mode,
                case_sensitive=case_sensitive,
                regexp=regexp,
                path_mode=path_mode,
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

    def test_regex_default1(self) -> None:
        selecta = self.run_test('test.txt', 'Or.+bana', regexp=True, case_sensitive=True, remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 1)

    def test_bash_prefix(self) -> None:
        selecta = self.run_test('test_history.txt', r'fake\w+.*[^\d]$', regexp=True, bash_mode=True, remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 9)

    def test_sentence1(self) -> None:
        selecta = self.run_test('test.txt', '"orange cherry apple banana banana pe')
        self.assertEqual(selecta.matching_line_count, 1)

    def test_empty_file(self) -> None:
        selecta = self.run_test('test_empty.txt', 'foo')
        self.assertEqual(selecta.matching_line_count, 0)

    # test marking of parts
    def test_mark_parts1(self) -> None:
        parts = mark_parts('orange cherry Orange apple Banana banana Pear apple', ['bana', 'apple', 'pear'], case_sensitive=False, highlight_matches=True)
        self.assertEqual(parts, ['orange cherry Orange ', ('match', 'apple'), ' ', ('match', 'Bana'), 'na ', ('match', 'bana'), 'na ', ('match', 'Pear'), ' ', ('match', 'apple')])

    def test_mark_parts2(self) -> None:
        parts = mark_parts('orange cherry Orange apple Banana banana Pear apple', ['cher', 'Bana'], case_sensitive=True, highlight_matches=True)
        self.assertEqual(parts, ['orange ', ('match', 'cher'), 'ry Orange apple ', ('match', 'Bana'), 'na banana Pear apple'])

    def test_mark_parts3(self) -> None:
        parts = mark_parts('apple orange cherry apple banana banana pear', ['pear', 'banana'], case_sensitive=True, highlight_matches=True)
        self.assertEqual(parts, ['apple orange cherry apple ', ('match', 'banana'), ' ', ('match', 'banana'), ' ', ('match', 'pear')])

    # test directory mode
    def test_dir1(self) -> None:
        selecta = self.run_test('test_history.txt', '', path_mode=True)
        self.assertEqual(selecta.matching_line_count, 31)

    def test_dir2(self) -> None:
        selecta = self.run_test('test_history.txt', r'/g\w+', regexp=True, path_mode=True)
        self.assertEqual(selecta.matching_line_count, 4)
