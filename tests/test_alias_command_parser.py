"""Run with python -m unittest discover -s tests."""

import unittest

from alias_command_parser import parse_alias_command


class AliasCommandParserTests(unittest.TestCase):
    def test_unquoted_alias_and_multiword_title(self):
        self.assertEqual(
            parse_alias_command("add ieo INFiNiTE ENERZY -Overdoze-"),
            ("add", "ieo", "INFiNiTE ENERZY -Overdoze-"),
        )

    def test_quoted_multiword_alias_and_title(self):
        self.assertEqual(
            parse_alias_command('add "infinite energy overdose" INFiNiTE ENERZY -Overdoze-'),
            ("add", "infinite energy overdose", "INFiNiTE ENERZY -Overdoze-"),
        )

    def test_apostrophe_in_unquoted_alias(self):
        self.assertEqual(
            parse_alias_command("submit don't INFiNiTE ENERZY -Overdoze-"),
            ("submit", "don't", "INFiNiTE ENERZY -Overdoze-"),
        )

    def test_apostrophe_in_unquoted_or_quoted_title(self):
        self.assertEqual(
            parse_alias_command("add dsr DON'T STOP ROCKIN'"),
            ("add", "dsr", "DON'T STOP ROCKIN'"),
        )
        self.assertEqual(
            parse_alias_command('add dsr "DON\'T STOP ROCKIN\'"'),
            ("add", "dsr", '"DON\'T STOP ROCKIN\'"'),
        )

    def test_literal_paired_quotes_in_titles_are_not_lost(self):
        self.assertEqual(
            parse_alias_command("add literal 'Title'"),
            ("add", "literal", "'Title'"),
        )
        self.assertEqual(
            parse_alias_command('add literal "Title"'),
            ("add", "literal", '"Title"'),
        )

    def test_literal_title_is_prioritized_over_unquoted_fallback(self):
        from alias_command_parser import song_title_candidates

        self.assertEqual(song_title_candidates("'Title'"), ("'Title'", "Title"))
        self.assertEqual(song_title_candidates('"Title"'), ('"Title"', "Title"))
        self.assertEqual(song_title_candidates("DON'T STOP ROCKIN'"), ("DON'T STOP ROCKIN'",))
        self.assertEqual(song_title_candidates('"DON\'T STOP ROCKIN\'"'), ('"DON\'T STOP ROCKIN\'"', "DON'T STOP ROCKIN'"))

    def test_list_and_delete_quoted_alias(self):
        self.assertEqual(
            parse_alias_command('del "infinite energy overdose"'),
            ("del", "infinite energy overdose", ""),
        )
        self.assertEqual(
            parse_alias_command("list infinite energy overdose"),
            ("list", "infinite energy overdose", ""),
        )

    def test_invalid_double_quote(self):
        with self.assertRaises(ValueError):
            parse_alias_command('add "infinite energy overdose INFiNiTE ENERZY -Overdoze-')
        with self.assertRaises(ValueError):
            parse_alias_command('add "ieo"INFiNiTE ENERZY -Overdoze-')

    def test_whitespace_and_empty(self):
        self.assertEqual(parse_alias_command(" \t "), ("", "", ""))
        self.assertEqual(parse_alias_command("  ADD\t ieo\t INFiNiTE ENERZY -Overdoze-  "), ("add", "ieo", "INFiNiTE ENERZY -Overdoze-"))


if __name__ == "__main__":
    unittest.main()
