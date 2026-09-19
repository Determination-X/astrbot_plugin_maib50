"""Regression tests for constant-table refresh without importing AstrBot itself."""

import asyncio
import importlib
import logging
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class _Response:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def raise_for_status(self):
        pass

    async def text(self):
        return self.payload


class _Session:
    def __init__(self, payload):
        self.response = _Response(payload)

    def get(self, _url):
        return self.response


class ConstantTableRefreshTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        package = types.ModuleType("_maib50_refresh_test")
        package.__path__ = [str(root)]
        astrbot = types.ModuleType("astrbot")
        astrbot.__path__ = []
        api = types.ModuleType("astrbot.api")
        api.logger = logging.getLogger(__name__)
        aiohttp = types.ModuleType("aiohttp")
        aiohttp.ClientSession = object
        self.modules = patch.dict(
            sys.modules,
            {
                package.__name__: package,
                "astrbot": astrbot,
                "astrbot.api": api,
                "aiohttp": aiohttp,
            },
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.manager_type = importlib.import_module(
            f"{package.__name__}.constant_table_manager"
        ).ConstantTableManager

    def test_valid_json_populates_title_indexes(self):
        manager = self.manager_type()
        result = asyncio.run(
            manager.refresh(_Session("""[{"title": "DON'T STOP ROCKIN'", "version": "DX"}]"""))
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(manager.find_by_title("DON'T STOP ROCKIN'"), result)

    def test_invalid_json_raises_decode_error_not_name_error(self):
        manager = self.manager_type()
        with self.assertRaisesRegex(ValueError, "Failed to decode"):
            asyncio.run(manager.refresh(_Session("{broken")))


if __name__ == "__main__":
    unittest.main()
