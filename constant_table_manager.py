import json
import re
import unicodedata

import aiohttp

# from astrbot.api import logger

MUSIC_EX_URL = (
    "https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex.json"
)
MUSIC_EX_URL_INT = (
    "https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex-intl.json"
)
BASE_FIELDS = ("title", "version", "image_url")
CONSTANT_FIELD_PATTERN = re.compile(r"^(?:dx_)?lev_(?:bas|adv|exp|mas|remas)_i$")


class ConstantTableManager:
    def __init__(self, source_url: str | None = None, source_url_int: str | None = None, table_selection: str = "INT"):
        """
        Initialize ConstantTableManager.
        
        Args:
            source_url: URL for JP constant table (defaults to MUSIC_EX_URL)
            source_url_int: URL for INT constant table (defaults to MUSIC_EX_URL_INT)
            table_selection: Which table to use - "JP" or "INT" (defaults to "INT")
        """
        self.source_url = source_url or MUSIC_EX_URL  # JP table
        self.source_url_int = source_url_int or MUSIC_EX_URL_INT  # INT table
        self.table_selection = table_selection.upper()
        self._entries: list[dict[str, str]] = []
        self._title_index: dict[str, list[dict[str, str]]] = {}
        self._normalized_title_index: dict[str, list[dict[str, str]]] = {}
    
    def set_table_selection(self, selection: str) -> None:
        """Change the constant table selection ('JP' or 'INT')."""
        self.table_selection = selection.upper()
        if self.table_selection not in ("JP", "INT"):
            raise ValueError(f"Invalid table selection: {selection}. Must be 'JP' or 'INT'")
        # Clear cached entries when switching tables
        self._entries = []
        self._title_index = {}
        self._normalized_title_index = {}

    @property
    def entries(self) -> list[dict[str, str]]:
        return self._entries

    async def refresh(
        self, session: aiohttp.ClientSession | None = None
    ) -> list[dict[str, str]]:
        if session is None:
            async with aiohttp.ClientSession() as owned_session:
                return await self.refresh(owned_session)

        # Select URL based on table_selection setting
        if self.table_selection == "JP":
            selected_url = self.source_url  # JP table
        else:  # INT (default)
            selected_url = self.source_url_int  # INT table
        
        if not selected_url:
            raise ValueError(f"No source URL configured for {self.table_selection} constant table")

#       logger.debug("Fetching maimai constant table from %s (selection=%s)", selected_url, self.table_selection)
        async with session.get(selected_url) as response:
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
        self._normalized_title_index = {}
        for entry in extracted_entries:
            title = entry["title"]
            self._title_index.setdefault(title, []).append(entry)
            normalized_title = self._normalize_title(title)
            if normalized_title:
                self._normalized_title_index.setdefault(normalized_title, []).append(
                    entry
                )

#        logger.info("Loaded %s constant table entries", len(extracted_entries))
        return extracted_entries

    def find_by_title(self, title: str) -> list[dict[str, str]]:
        direct = self._title_index.get(title, [])
        if direct:
            return list(direct)

        normalized = self._normalize_title(title)
        if normalized:
            normalized_matches = self._normalized_title_index.get(normalized, [])
            if normalized_matches:
                return list(normalized_matches)

        alias_matches = self._find_by_alias(title)
        if alias_matches:
            return alias_matches

        return []

    def _find_by_alias(self, title: str) -> list[dict[str, str]]:
        alias_map = {
            "ずんだもんの朝食 〜目覚ましずんラップ〜": "ずんだもんの朝食～目覚ましずんラップ～",
            "チルノのパーフェクトさんすう教室 ⑨周年バージョン": "チルノのパーフェクトさんすう教室 9周年バージョン",
            "セイクリッド ルイン": "セイクリッド ルイン (jubeat VERSION)",
            "ぼくたちいつでも しゅわっしゅわ！": "ぼくたちいつでも しゅわっしゅわ!",
            "D✪N’T ST✪P R✪CKIN’": "DON'T STOP ROCKIN'",
            "バーチャルダム ネーション": "バーチャルダムネーション",
            "全世界共通リズム感テスト": "全世界共通リズム感テスト -SEKAI NO MINNA DE RYTHM KAN TEST-",
            "オーケー？ オーライ！": "オーケー? オーライ!",
        }

        alias_title = alias_map.get(title)
        if not alias_title:
            return []

        direct = self._title_index.get(alias_title, [])
        if direct:
            return list(direct)

        normalized = self._normalize_title(alias_title)
        if not normalized:
            return []
        return list(self._normalized_title_index.get(normalized, []))

    def _normalize_title(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text)
        normalized = normalized.replace("〜", "~").replace("～", "~")
        normalized = normalized.replace("’", "'").replace("‘", "'")
        normalized = normalized.replace("“", '"').replace("”", '"')
        normalized = normalized.replace("？", "?").replace("！", "!")
        normalized = normalized.replace("　", " ")
        normalized = normalized.replace("✪", "")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

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
