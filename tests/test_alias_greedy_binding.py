"""Check AstrBot command binding without loading AstrBot itself.

AstrBot's CommandFilter stores a default value instead of its annotation.
GreedyStr must therefore have no default, or only one token is forwarded.
"""

import ast
import unittest
from pathlib import Path

from alias_command_parser import parse_alias_command


class AliasGreedyBindingTests(unittest.TestCase):
    def test_alias_handler_uses_greedystr_without_default(self):
        main = Path(__file__).resolve().parents[1] / "main.py"
        module = ast.parse(main.read_text(encoding="utf-8"))
        handlers = [
            node for node in ast.walk(module)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "mai_alias"
        ]
        self.assertEqual(len(handlers), 1)
        arguments = handlers[0].args
        self.assertEqual([arg.arg for arg in arguments.args], ["self", "event", "arguments"])
        self.assertIsInstance(arguments.args[-1].annotation, ast.Name)
        self.assertEqual(arguments.args[-1].annotation.id, "GreedyStr")
        self.assertFalse(arguments.defaults)

    def test_full_rest_of_command_is_required_for_add(self):
        self.assertEqual(
            parse_alias_command("add RONDO RONDØ"),
            ("add", "RONDO", "RONDØ"),
        )
        self.assertEqual(
            parse_alias_command('add "RONDO" "RONDØ"'),
            ("add", "RONDO", '"RONDØ"'),
        )

    def test_no_arguments_still_shows_help(self):
        self.assertEqual(parse_alias_command(""), ("", "", ""))


if __name__ == "__main__":
    unittest.main()
