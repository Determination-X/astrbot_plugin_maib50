"""Unit tests for instance-local aliases (run: python -m unittest discover -s tests)."""

import json
import tempfile
import unittest
from pathlib import Path

from alias_manager import AliasError, AliasManager


class AliasManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name)

    def test_empty_file_created_only_when_missing(self):
        manager = AliasManager(self.data_dir)
        self.assertEqual(json.loads(manager.path.read_text(encoding="utf-8")), {})
        manager.add("ieo", "INFiNiTE ENERZY -Overdoze-")
        reloaded = AliasManager(self.data_dir)
        self.assertEqual(reloaded.get_title("IEO"), "INFiNiTE ENERZY -Overdoze-")

    def test_multiple_aliases_for_one_title(self):
        manager = AliasManager(self.data_dir)
        manager.add("ieo", "INFiNiTE ENERZY -Overdoze-")
        manager.add("过量", "INFiNiTE ENERZY -Overdoze-")
        self.assertEqual(manager.get_title("  IEO  "), "INFiNiTE ENERZY -Overdoze-")
        self.assertEqual(manager.get_title("过量"), "INFiNiTE ENERZY -Overdoze-")
        self.assertEqual(len(manager.list_aliases()), 2)

    def test_normalized_conflicts_and_delete_take_effect_immediately(self):
        manager = AliasManager(self.data_dir)
        manager.add("ＲＯＮＤＯ", "RONDØ")
        self.assertEqual(manager.get_title("rondo"), "RONDØ")
        with self.assertRaises(AliasError):
            manager.add("RONDO", "Something else")
        self.assertEqual(manager.delete("rondo"), "RONDØ")
        self.assertIsNone(manager.get_title("RONDO"))

    def test_requests_and_live_approval(self):
        manager = AliasManager(self.data_dir)
        request_id = manager.submit("最水15", "PANDORA PARADOXXX", "qq", "123")
        self.assertEqual(manager.pending()[0]["id"], request_id)
        with self.assertRaises(AliasError):
            manager.submit("最水15", "PANDORA PARADOXXX", "qq", "456")
        manager.approve(request_id)
        self.assertEqual(manager.get_title("最水15"), "PANDORA PARADOXXX")
        self.assertEqual(manager.pending(), [])
        self.assertEqual(AliasManager(self.data_dir).get_title("最水15"), "PANDORA PARADOXXX")

    def test_rejection(self):
        manager = AliasManager(self.data_dir)
        request_id = manager.submit("bad", "Song", "telegram", "abc")
        manager.reject(request_id)
        self.assertEqual(manager.pending(), [])
        self.assertIsNone(manager.get_title("bad"))

    def test_malformed_existing_file_is_not_overwritten(self):
        path = self.data_dir / "title_aliases.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(AliasError):
            AliasManager(self.data_dir)
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")


if __name__ == "__main__":
    unittest.main()
