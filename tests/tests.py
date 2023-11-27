import unittest
from selecta import Selecta


class TestSelecta(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestSelecta, self).__init__(*args, **kwargs)

    def run_test(self, file, input, reverse_order=False, remove_bash_prefix=False, remove_zsh_prefix=False,
                 regexp=False, case_sensitive=False, remove_duplicates=False, show_matches=False):

        with open(file) as fh:
            selecta = Selecta(
                infile=fh,
                reverse_order=reverse_order,
                remove_bash_prefix=remove_bash_prefix,
                remove_zsh_prefix=remove_zsh_prefix,
                regexp=regexp,
                case_sensitive=case_sensitive,
                remove_duplicates=remove_duplicates,
                show_matches=show_matches,
                test_mode=True,
            )

            selecta.loop.start()
            selecta.edit_change(None, input)
            selecta.edit_done(None)
            selecta.loop.stop()

            return selecta

    def test_words_default_rd(self):
        selecta = self.run_test('tests/test.txt', 'app bana', remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 2)

    def test_words_default_nrd(self):
        selecta = self.run_test('tests/test.txt', 'app bana')
        self.assertEqual(selecta.matching_line_count, 3)

    def test_words_case_sensitive(self):
        selecta = self.run_test('tests/test.txt', 'Orange', case_sensitive=True, remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 1)

    def test_baz(self):
        selecta = self.run_test('tests/test.txt', 'baz')
        self.assertEqual(selecta.matching_line_count, 0)

    def test_regex_default(self):
        selecta = self.run_test('tests/test.txt', 'Or.+bana', regexp=True, case_sensitive=True, remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 1)

    def test_bash_prefix(self):
        selecta = self.run_test('tests/test_history.txt', r'^[^\d]+$', regexp=True, remove_bash_prefix=True, remove_duplicates=True)
        self.assertEqual(selecta.matching_line_count, 4)

    def test_empty_file(self):
        selecta = self.run_test('tests/test_empty.txt', 'foo')
        self.assertEqual(selecta.matching_line_count, 0)
