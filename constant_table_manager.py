import json
import re

import aiohttp

# from astrbot.api import logger

MUSIC_EX_URL = (
    "https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex.json"
)
BASE_FIELDS = ("title", "version", "image_url")
CONSTANT_FIELD_PATTERN = re.compile(r"^(?:dx_)?lev_(?:bas|adv|exp|mas|remas)_i$")


class ConstantTableManager:
    def __init__(self, source_url: str = MUSIC_EX_URL):
        self.source_url = source_url
        self._entries: list[dict[str, str]] = []
        self._title_index: dict[str, list[dict[str, str]]] = {}

    @property
    def entries(self) -> list[dict[str, str]]:
        return self._entries

    async def refresh(
        self, session: aiohttp.ClientSession | None = None
    ) -> list[dict[str, str]]:
        if session is None:
            async with aiohttp.ClientSession() as owned_session:
                return await self.refresh(owned_session)

        # logger.debug("Fetching maimai constant table from %s", self.source_url)
        async with session.get(self.source_url) as response:
            response.raise_for_status()
            payload_text = await response.text()

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Failed to decode music-ex.json payload") from exc

        if not isinstance(payload, list):
            raise TypeError("music-ex.json payload is not a list")

        extracted_entries = [
            self._extract_entry(raw_entry)
            for raw_entry in payload
            if isinstance(raw_entry, dict)
        ]
        self._entries = extracted_entries
        self._title_index = {}
        for entry in extracted_entries:
            title = entry["title"]
            self._title_index.setdefault(title, []).append(entry)

        # logger.info("Loaded %s constant table entries", len(extracted_entries))
        return extracted_entries

    def find_by_title(self, title: str) -> list[dict[str, str]]:
        return list(self._title_index.get(title, []))

    def _extract_entry(self, raw_entry: dict) -> dict[str, str]:
        entry: dict[str, str] = {}
        for field in BASE_FIELDS:
            value = raw_entry.get(field, "")
            entry[field] = value if isinstance(value, str) else str(value)

        for key, value in raw_entry.items():
            if not CONSTANT_FIELD_PATTERN.fullmatch(key):
                continue
            if value is None:
                continue
            entry[key] = value if isinstance(value, str) else str(value)

        return entry
