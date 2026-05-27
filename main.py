import os
import pickle  # 用于保存和加载cookies
import re
import sqlite3  # 存储绑定信息的数据库
from base64 import b64encode
from mimetypes import guess_type
from pathlib import Path  # 用于处理文件路径

import aiohttp  # 异步HTTP请求库，用于向maimai net爬取数据
from bs4 import BeautifulSoup  # 用于解析HTML

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import (
    get_astrbot_plugin_data_path,
    get_astrbot_plugin_path,
)

from .ap50 import AP50Helper
from .b50 import B50Helper
from .constant_table_manager import ConstantTableManager
from .lookup import MaimaiLookupHelper

# constants from astrbot framework:
# self.name = astrbot_plugin_maib50
help_text = """/mai可用指令:
├──/mai b50
├──/mai ap50
├──/mai view-all-binds [--force|-f]
├──/mai bind <服务器> <好友码>
│   ├── INT
│   │   CN (开发中)
│   │   JP (暂定)
│   │   RIN (开发中)
│   │   MUNET (开发中)
├──/mai unbind [服务器]
├──/mai help
└──/mai search <关键词>
[可选参数] <必选参数>

可用服务器:  国际服
开发中:  国服 Rin服 MuNET
咕咕中: 日服"""

DIFF_LABELS = {
    0: "BASIC",
    1: "ADVANCED",
    2: "EXPERT",
    3: "MASTER",
    4: "Re:MASTER",
}

DIFF_CONSTANT_SUFFIX = {
    0: "bas",
    1: "adv",
    2: "exp",
    3: "mas",
    4: "remas",
}

DIFF_CLASS_NAMES = {
    0: "BASIC",
    1: "ADVANCED",
    2: "EXPERT",
    3: "MASTER",
    4: "RE-MASTER",
}

LAYOUT_WIDTH = 1200
LAYOUT_HEIGHT = 700
RENDER_WIDTH = 3024
RENDER_HEIGHT = 1700


# Deprecated    @register("astrbot_plugin_maib50", "诶嘿怪awa", "Maib50 国际服插件", "1.0.1")
class MaiPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config  # 获取插件配置，配置文件路径为 `data/plugin_data/astrbot_plugin_maib50/config.json`，如果没有这个文件会自动创建一个空的配置文件。可以在这个配置文件里添加一些插件需要的配置项。
        self.sid = self.config.get(
            "INT", {}
        ).get(
            "BOT_SID", ""
        )  # 从配置文件中获取 BOT_SID 配置项的值，如果没有这个配置项或者值为空字符串，则默认为空字符串。
        self.password = self.config.get(
            "INT", {}
        ).get(
            "BOT_PASSWORD", ""
        )  # 从配置文件中获取 BOT_PASSWORD 配置项的值，如果没有这个配置项或者值为空字符串，则默认为空字符串。
        self.version_floor_threshold = self.config.get(
            "INT", {}
        ).get(
            "VERSION_FLOOR_THRESHOLD", ""
        )  # 从配置文件中获取 VERSION_FLOOR_THRESHOLD 配置项的值，如果没有这个配置项或者值为空字符串，则默认为空字符串。这个配置项用于指定版本底线，只有常数表版本号大于等于这个底线的谱面才会被算入New15评分计算，否则会被当做旧谱面处理为Old35。这个配置项主要是为了应对常数表更新滞后于游戏版本更新的情况，允许管理员手动指定一个版本底线来区分新旧谱面。如果这个配置项设置为一个有效的整数值（比如23000），则版本号大于等于这个值的谱面会被算入New15评分计算；如果这个配置项设置为一个无效值或者留空，则插件会尝试自动检测当前版本底线，自动检测的方法是找出所有好友谱面中常数表版本号的最大值，然后向下取整到最近的千位数作为版本底线（比如如果最大版本号是23145，则版本底线会被自动设定为23000）。需要注意的是，如果常数表数据严重滞后导致无法正确检测出当前版本底线，可能会导致新旧谱面划分错误，从而影响评分计算结果，因此建议管理员根据实际情况合理设置这个配置项。

        # Get constant table selection (default to INT if not specified)
        self.constant_table_selection = self.config.get("INT", {}).get(
            "CONSTANT_TABLE_SELECTION", "INT"
        )
        if self.constant_table_selection not in ("JP", "INT"):
            logger.warning(
                "Invalid CONSTANT_TABLE_SELECTION=%r, defaulting to INT",
                self.constant_table_selection,
            )
            self.constant_table_selection = "INT"

        self.plugin_data_path = Path(get_astrbot_plugin_data_path()) / self.name
        self.plugin_path = Path(get_astrbot_plugin_path()) / self.name
        self.db_path = self.plugin_data_path / "bindings.db"

        self.cookies_path = self.plugin_data_path / "cookies.pkl"
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._ensure_bindings_table()
        self.constant_table_manager = ConstantTableManager(
            table_selection=self.constant_table_selection
        )

        self.template_path = self.plugin_path / "templates"
        self.b50_helper = B50Helper(self.template_path)
        self.ap50_helper = AP50Helper(self.template_path)
        self.lookup_helper = MaimaiLookupHelper()

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    async def _ensure_constant_table_loaded(self, session: aiohttp.ClientSession):
        if self.constant_table_manager.entries:
            return
        logger.info("Constant table cache is empty, loading upstream data")
        await self.constant_table_manager.refresh(session)

    def _attach_constant_table_data(self, entries: list[dict]) -> list[dict]:
        attached_entries = []
        missing_titles: set[str] = set()
        ambiguous_titles: set[str] = set()
        for entry in entries:
            matches = self.constant_table_manager.find_by_title(entry["title"])
            if not matches:
                if entry["title"] not in missing_titles:
                    logger.warning(
                        "No constant table match found for parsed entry title=%r",
                        entry["title"],
                    )
                    missing_titles.add(entry["title"])
                attached_entries.append({**entry, "constant_table": None})
                continue
            selected_match = self._select_best_constant_match(entry, matches)
            if len(matches) > 1:
                if entry["title"] not in ambiguous_titles:
                    logger.warning(
                        "Multiple constant table matches found for parsed entry title=%r count=%s",
                        entry["title"],
                        len(matches),
                    )
                    ambiguous_titles.add(entry["title"])
            attached_entries.append({**entry, "constant_table": selected_match})
        return attached_entries

    def _select_best_constant_match(self, entry: dict, matches: list[dict]) -> dict:
        diff_suffix = DIFF_CONSTANT_SUFFIX.get(entry.get("difficulty_index", -1))
        if not diff_suffix:
            return matches[0]
        if entry.get("type") == "DX":
            candidate_keys = [f"dx_lev_{diff_suffix}_i", f"lev_{diff_suffix}_i"]
        else:
            candidate_keys = [f"lev_{diff_suffix}_i", f"dx_lev_{diff_suffix}_i"]

        for key in candidate_keys:
            for match in matches:
                value = match.get(key)
                if value not in (None, ""):
                    return match
        return matches[0]

    def _load_cookies(self):
        """从文件加载保存的cookies"""
        try:
            if os.path.exists(self.cookies_path):
                with open(self.cookies_path, "rb") as f:
                    return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cookies: {e}")
        return None

    def _save_cookies(self, jar):
        """保存cookies到文件"""
        try:
            os.makedirs(os.path.dirname(self.cookies_path), exist_ok=True)
            with open(self.cookies_path, "wb") as f:
                pickle.dump(jar._cookies, f)
        except Exception as e:
            logger.warning(f"Failed to save cookies: {e}")

    def _file_to_data_uri(self, file_path: Path) -> str:
        try:
            mime_type = guess_type(file_path.name)[0] or "application/octet-stream"
            encoded = b64encode(file_path.read_bytes()).decode("ascii")
        except OSError as exc:
            logger.warning("Failed to read image file %s: %s", file_path, exc)
            return ""

        return f"data:{mime_type};base64,{encoded}"

    def _resolve_background_image(self, configured_value: list[str] | str) -> str:
        if isinstance(configured_value, list):
            rel_path = next(
                (
                    item.strip()
                    for item in configured_value
                    if isinstance(item, str) and item.strip()
                ),
                "",
            )
        elif isinstance(configured_value, str):
            rel_path = configured_value.strip()
        else:
            rel_path = ""

        if not rel_path:
            return ""

        background_path = (self.plugin_data_path / rel_path).resolve(strict=False)
        if not background_path.is_file():
            logger.warning(
                "Configured background image not found: %s",
                background_path,
            )
            return ""
        return self._file_to_data_uri(background_path)

    def _get_template_background(self) -> str:
        return self._resolve_background_image(
            self.config.get("INT", {}).get("BACKGROUND_IMAGE", [])
        )

    def _resolve_song_jacket(self, entry: dict) -> str:
        constant_table = entry.get("constant_table") or {}
        jacket_name = str(constant_table.get("image_url", "")).strip()
        if not jacket_name:
            return ""

        jacket_path = (
            self.plugin_data_path / "static" / "jacket" / jacket_name
        ).resolve(strict=False)
        if not jacket_path.is_file():
            logger.debug(
                "Song jacket not found for title=%r image_url=%r path=%s",
                entry.get("title"),
                jacket_name,
                jacket_path,
            )
            return ""

        return self._file_to_data_uri(jacket_path)

    def _ensure_bindings_table(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bindings'"
        )
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(bindings)")
            columns = [row[1] for row in cursor.fetchall()]
            if "platform_name" not in columns:
                cursor.execute("ALTER TABLE bindings RENAME TO bindings_old")
                cursor.execute(
                    """CREATE TABLE bindings (
                    uid TEXT,
                    platform_name TEXT DEFAULT '',
                    friend_code TEXT,
                    server TEXT,
                    PRIMARY KEY (uid, platform_name, server)
                )"""
                )
                cursor.execute(
                    "INSERT OR REPLACE INTO bindings (uid, platform_name, friend_code, server) SELECT uid, '', friend_code, server FROM bindings_old"
                )
                cursor.execute("DROP TABLE bindings_old")
                self.conn.commit()
                return
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS bindings (
            uid TEXT,
            platform_name TEXT DEFAULT '',
            friend_code TEXT,
            server TEXT,
            PRIMARY KEY (uid, platform_name, server)
        )"""
        )
        self.conn.commit()

    def _get_binding(
        self, uid: str, platform_name: str, server: str
    ) -> tuple[str, str] | None:
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT platform_name, friend_code
            FROM bindings
            WHERE uid = ? AND server = ? AND platform_name IN (?, '')
            ORDER BY CASE WHEN platform_name = ? THEN 0 ELSE 1 END
            LIMIT 1""",
            (uid, server, platform_name, platform_name),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return row[0], row[1]

    def _normalize_server(self, server: str) -> str | None:
        normalized = server.strip()
        mapping = {
            "INT": "INT",
            "int": "INT",
            "国际服": "INT",
            "國際服": "INT",
            "International": "INT",
            "CN": "CN",
            "cn": "CN",
            "国服": "CN",
            "國服": "CN",
            "China": "CN",
            "JP": "JP",
            "jp": "JP",
            "日服": "JP",
            "Japan": "JP",
            "JPN": "JP",
            "RIN": "RIN",
            "rin": "RIN",
            "Rin服": "RIN",
            "RinNET": "RIN",
            "MUNET": "MUNET",
            "munet": "MUNET",
        }
        return mapping.get(normalized)

    def _extract_token_from_html(self, html: str) -> str | None:
        match = re.search(
            r'<input[^>]+name=["\']token["\'][^>]*value=["\']([^"\']+)["\']', html, re.I
        )
        if match:
            return match.group(1)
        match = re.search(
            r'<input[^>]+value=["\']([^"\']+)["\'][^>]*name=["\']token["\']', html, re.I
        )
        return match.group(1) if match else None

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _parse_achievement_text(self, raw_text: str) -> tuple[float, bool]:
        text = self._normalize_whitespace(raw_text)
        if not text or "―" in text:
            return 0.0, True
        text = text.replace("%", "")
        try:
            return float(text), False
        except ValueError:
            return 0.0, True

    def _extract_icon_names(self, container) -> list[str]:
        icons = []
        for img in container.select("img"):
            src = img.get("src", "")
            if not src:
                continue
            icon_name = src.rsplit("/", 1)[-1].split("?", 1)[0]
            if icon_name.startswith("music_icon_"):
                icons.append(icon_name.removeprefix("music_icon_").removesuffix(".png"))
        return icons

    def _extract_friend_profile(self, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        friend_block = soup.select_one("div.friend_vs_friend_block")
        if not friend_block:
            return {"name": "Unknown", "rating": "Unknown"}
        name_node = friend_block.select_one("div.f_b")
        rating_node = friend_block.select_one("div.rating_block")
        return {
            "name": self._normalize_whitespace(name_node.get_text())
            if name_node
            else "Unknown",
            "rating": self._normalize_whitespace(rating_node.get_text())
            if rating_node
            else "Unknown",
        }

    def _parse_friend_entries_from_html(self, html: str, diff_index: int) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        entries = []
        for card in soup.select('div[class*="_score_back"]'):
            title_node = card.select_one("div.music_name_block")
            level_node = card.select_one("div.music_lv_block")
            score_cells = card.select('td[class*="score_label"]')
            detail_cells = card.select("table tr:nth-of-type(2) td")
            if title_node is None:
                logger.warning(
                    "Dropping score card for %s: missing title node. card_html=%s",
                    DIFF_LABELS.get(diff_index, str(diff_index)),
                    str(card),
                )
                continue
            if level_node is None:
                logger.warning(
                    "Dropping score card for %s: missing level node. card_html=%s",
                    DIFF_LABELS.get(diff_index, str(diff_index)),
                    str(card),
                )
                continue
            if len(score_cells) < 2:
                logger.warning(
                    "Dropping score card for %s: expected at least 2 score cells, got %s. card_html=%s",
                    DIFF_LABELS.get(diff_index, str(diff_index)),
                    len(score_cells),
                    str(card),
                )
                continue

            title = self._normalize_whitespace(title_node.get_text())
            if not title:
                logger.warning(
                    "Dropping score card for %s: title is empty after normalization. raw_title=%r card_html=%s",
                    DIFF_LABELS.get(diff_index, str(diff_index)),
                    title_node.get_text(),
                    str(card),
                )
                continue

            if len(detail_cells) < 2:
                logger.warning(
                    "Score card for %s has fewer than 2 detail cells, icons will be empty. title=%r card_html=%s",
                    DIFF_LABELS.get(diff_index, str(diff_index)),
                    title,
                    str(card),
                )

            achievement, unplayed = self._parse_achievement_text(
                score_cells[-1].get_text()
            )
            kind_icon = card.select_one("img.music_kind_icon")
            raw_kind_src = kind_icon.get("src") if kind_icon else None
            kind_src = raw_kind_src if isinstance(raw_kind_src, str) else ""
            if "music_standard" in kind_src:
                chart_type = "STD"
            elif "music_dx" in kind_src:
                chart_type = "DX"
            else:
                chart_type = "UNKNOWN"

            entries.append(
                {
                    "title": title,
                    "level": self._normalize_whitespace(level_node.get_text()),
                    "type": chart_type,
                    "difficulty": DIFF_LABELS.get(diff_index, str(diff_index)),
                    "difficulty_class": DIFF_CLASS_NAMES.get(
                        diff_index, str(diff_index)
                    ),
                    "difficulty_index": diff_index,
                    "achievement": achievement,
                    "achievement_text": f"{achievement:.4f}%",
                    "unplayed": unplayed,
                    "icons": self._extract_icon_names(detail_cells[-1])
                    if len(detail_cells) >= 2
                    else [],
                }
            )
        return entries

    async def _fetch_friend_vs_page(
        self,
        session: aiohttp.ClientSession,
        friend_code: str,
        diff_index: int,
        headers: dict,
    ) -> str:
        url = "https://maimaidx-eng.com/maimai-mobile/friend/friendGenreVs/battleStart/"
        params = {
            "scoreType": 2,
            "genre": 99,
            "diff": diff_index,
            "idx": friend_code,
        }
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                raise RuntimeError(
                    f"Failed to fetch diff {diff_index}: HTTP {resp.status}"
                )
            return await resp.text()

    async def _fetch_friend_b50_data(
        self,
        session: aiohttp.ClientSession,
        friend_code: str,
        headers: dict,
    ) -> tuple[dict, list[dict]]:
        profile: dict | None = None
        entries: list[dict] = []
        for diff_index in range(5):
            html = await self._fetch_friend_vs_page(
                session, friend_code, diff_index, headers
            )
            if profile is None:
                profile = self._extract_friend_profile(html)
            entries.extend(self._parse_friend_entries_from_html(html, diff_index))
        return profile or {"name": "Unknown", "rating": "Unknown"}, entries

    def _get_rank_factor(self, achievement: float) -> float:
        if achievement >= 100.5:
            return 22.4
        if achievement >= 100.0:
            return 21.6
        if achievement >= 99.5:
            return 21.1
        if achievement >= 99.0:
            return 20.8
        if achievement >= 98.0:
            return 20.3
        if achievement >= 97.0:
            return 20.0
        if achievement >= 94.0:
            return 16.8
        if achievement >= 90.0:
            return 15.2
        if achievement >= 80.0:
            return 13.6
        return 0.0

    def _extract_chart_constant(self, entry: dict) -> float | None:
        constant_table = entry.get("constant_table")
        if not constant_table:
            return None
        diff_suffix = DIFF_CONSTANT_SUFFIX.get(entry.get("difficulty_index", -1))
        if not diff_suffix:
            return None
        chart_type = entry.get("type", "")
        if chart_type == "DX":
            candidate_keys = [f"dx_lev_{diff_suffix}_i", f"lev_{diff_suffix}_i"]
        else:
            candidate_keys = [f"lev_{diff_suffix}_i", f"dx_lev_{diff_suffix}_i"]
        for key in candidate_keys:
            raw_value = constant_table.get(key)
            if raw_value in (None, ""):
                continue
            try:
                return float(raw_value)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid constant value %r for key=%s title=%r",
                    raw_value,
                    key,
                    entry.get("title"),
                )
        return None

    def _build_rated_entry(self, entry: dict) -> dict | None:
        if entry.get("unplayed"):
            return None
        chart_constant = self._extract_chart_constant(entry)
        if chart_constant is None:
            return None
        achievement = float(entry.get("achievement", 0.0))
        capped_achievement = min(achievement, 100.5)
        rank_factor = self._get_rank_factor(capped_achievement)
        if rank_factor <= 0.0:
            return None
        rating = int((capped_achievement / 100.0) * rank_factor * chart_constant)
        return {
            **entry,
            "chart_constant": chart_constant,
            "constant_display": f"{chart_constant:.1f} → {rating}",
            "rank_factor": rank_factor,
            "rating": rating,
            "version": str((entry.get("constant_table") or {}).get("version", "")),
            "img": self._resolve_song_jacket(entry),
        }

    def _detect_current_version_floor(self, entries: list[dict]) -> int | None:
        version_numbers = []
        for entry in entries:
            constant_table = entry.get("constant_table")
            if not constant_table:
                continue
            version_raw = constant_table.get("version", "")
            try:
                version_numbers.append(int(str(version_raw)))
            except ValueError:
                continue
        if not version_numbers:
            return None
        latest_version = max(version_numbers)
        return (latest_version // 500) * 500 - 1000

    def _get_current_version_floor(self, entries: list[dict]) -> int | None:
        configured_value = self.version_floor_threshold
        if configured_value not in (None, ""):
            try:
                return int(str(configured_value).strip())
            except ValueError:
                logger.warning(
                    "Invalid VERSION_FLOOR_THRESHOLD=%r, fallback to auto detection",
                    configured_value,
                )
        return self._detect_current_version_floor(entries)

    def _is_current_version_entry(
        self, entry: dict, current_version_floor: int | None
    ) -> bool:
        if current_version_floor is None:
            return False
        try:
            return int(entry.get("version", "0")) >= current_version_floor
        except ValueError:
            return False

    @filter.command_group("mai")
    async def mai(self):
        pass

    @mai.command("help", default=True, alias={"?"})
    async def mai_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        yield event.plain_result(help_text)

    @mai.command("bind", alias={"绑定"})
    async def mai_bind(
        self, event: AstrMessageEvent, server: str = "", friend_code: str = ""
    ):
        """绑定好友码，当前仅支持国际服"""
        if server == "help" and friend_code == "":
            yield event.plain_result("""服务器可用参数说明:
INT int 国际服 國際服 International
CN  cn  国服 國服 China
JP  jp  日服  Japan JPN jpn
RIN rin Rin服 RinNET
MUNET munet MuNET""")
            return
        if server not in [
            "INT",
            "CN",
            "JP",
            "RIN",
            "MUNET",
            "int",
            "cn",
            "jp",
            "rin",
            "munet",
            "国际服",
            "国服",
            "日服",
            "Rin服",
            "國際服",
            "國服",
            "International",
            "China",
            "Japan",
            "RinNET",
            "MuNET",
            "JPN",
            "jpn",
        ]:
            yield event.plain_result(
                "服务器输错了，请使用 INT、CN、RIN 或 MUNET 作为服务器参数"
            )
            return
        if len(event.message_str.split()) < 3:
            yield event.plain_result(
                "参数错误！请使用 /mai bind <服务器> <好友码> 的格式进行绑定"
            )
            return
        if not friend_code.isdigit():
            yield event.plain_result("好友码输错了，好友码应该是纯数字")
            return
        normalized_server = self._normalize_server(server)
        if not normalized_server:
            yield event.plain_result(
                "服务器输错了，请使用 INT、CN、RIN、JP 或 MUNET 作为服务器参数"
            )
            return
        if normalized_server != "INT":
            yield event.plain_result(
                f"{server} 的绑定功能正在开发喵~为什么不去找开发者催更呢w？"
            )
            return
        platform_name = event.get_platform_name()
        uid = event.get_sender_id()
        row = self._get_binding(uid, platform_name, normalized_server)
        if row:
            bound_platform_name, old_code = row
            if old_code == friend_code:
                yield event.plain_result(f"你已经绑定了当前国际服好友码：{friend_code}")
                return
            self.conn.execute(
                "DELETE FROM bindings WHERE uid = ? AND server = ? AND platform_name IN (?, '')",
                (uid, normalized_server, platform_name),
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO bindings (uid, platform_name, friend_code, server) VALUES (?, ?, ?, ?)",
                (
                    uid,
                    platform_name or bound_platform_name,
                    friend_code,
                    normalized_server,
                ),
            )
            self.conn.commit()
            yield event.plain_result(
                f"已将国际服好友码从 {old_code} 更新为 {friend_code}"
            )
            return
        self.conn.execute(
            "INSERT OR REPLACE INTO bindings (uid, platform_name, friend_code, server) VALUES (?, ?, ?, ?)",
            (uid, platform_name, friend_code, normalized_server),
        )
        self.conn.commit()
        yield event.plain_result(f"成功绑定国际服好友码：{friend_code}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @mai.command("view-all-binds", alias={"查看所有绑定", "VAB", "vab"})
    async def mai_view_all_binds(self, event: AstrMessageEvent, force: str = ""):
        """管理员指令，查看所有绑定信息"""
        if event.get_group_id() != "" and force not in ["--force", "-f"]:
            yield event.plain_result(
                "该指令涉及玩家好友码隐私，只能在私聊中使用！如要強制在群里使用，请添加--force或-f参数"
            )
            return
        cursor = self.conn.cursor()
        cursor.execute("SELECT uid, platform_name, friend_code, server FROM bindings")
        rows = cursor.fetchall()
        if not rows:
            yield event.plain_result("没有任何绑定信息")
            return
        result = "所有绑定信息:\n"
        for uid, platform_name, friend_code, server in rows:
            result += (
                f"UID: {uid}, 平台: {platform_name or '<legacy>'}, "
                f"服务器: {server}, 好友码: {friend_code}\n"
            )
        yield event.plain_result(result)

    @mai.command("unbind", alias={"解绑"})
    async def mai_unbind(self, event: AstrMessageEvent, server: str = ""):
        """解绑好友码"""
        platform_name = event.get_platform_name()
        uid = event.get_sender_id()
        if server:
            normalized_server = self._normalize_server(server)
            if not normalized_server:
                yield event.plain_result(
                    "服务器输错了，请使用 INT、CN、RIN、JP 或 MUNET 作为服务器参数"
                )
                return
            row = self._get_binding(uid, platform_name, normalized_server)
            if not row:
                yield event.plain_result(f"你还没有绑定{normalized_server}的好友码")
                return
            self.conn.execute(
                "DELETE FROM bindings WHERE uid = ? AND server = ? AND platform_name IN (?, '')",
                (uid, normalized_server, platform_name),
            )
            self.conn.commit()
            yield event.plain_result(
                f"已解绑{normalized_server}好友码，maimai DX NET上的好友关系需要你手动删除~(或者考虑找开发者催更一个自动删除好友的功能(挖坑+1...)"
            )
            return
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT friend_code, server FROM bindings WHERE uid = ? AND platform_name IN (?, '')",
            (uid, platform_name),
        )
        row = cursor.fetchone()
        if not row:
            yield event.plain_result("你还没有绑定任何好友码")
            return
        self.conn.execute(
            "DELETE FROM bindings WHERE uid = ? AND platform_name IN (?, '')",
            (uid, platform_name),
        )
        self.conn.commit()
        yield event.plain_result(
            "解绑成功，maimai DX NET上的好友关系需要你手动删除~(或者考虑找开发者催更一个自动删除好友的功能w)"
        )

    @mai.command("b50")
    async def mai_b50(self, event: AstrMessageEvent):
        """查询maimai b50数据"""
        bot_sid = self.sid
        bot_password = self.password
        if bot_sid == "":
            yield event.plain_result(
                "插件未配置BOT_SID，无法查询数据，请联系管理员配置好BOT_SID后再试"
            )
            return
        if bot_password == "":
            yield event.plain_result(
                "插件未配置BOT_PASSWORD，无法查询数据，请联系管理员配置好BOT_PASSWORD后再试"
            )
            return

        # maimai DX NET Maintainance Time: Every Tuesday 2:00-6:00 UTC+9
        # now_gmt9 = datetime.now(timezone(timedelta(hours=9)))

        # if now_gmt9.weekday() == 1 and 2 <= now_gmt9.hour < 6:
        #    yield event.plain_result(
        #        "现在是每周二的维护时间(02:00-06:00 UTC+9),暂时无法查询数据,请在维护结束后再试"
        #    )
        #    return

        platform_name = event.get_platform_name()
        uid = event.get_sender_id()
        row = self._get_binding(uid, platform_name, "INT")
        if not row:
            yield event.plain_result(
                "未绑定国际服好友码，请先使用 /mai bind INT <好友码> 绑定"
            )
            return
        _, friend_code = row

        yield event.plain_result("正在查询数据，请稍候~")
        error_message, profile, entries = await self.lookup_helper.fetch_friend_entries(
            self,
            bot_sid,
            bot_password,
            friend_code,
            "b50",
        )
        if error_message:
            yield event.plain_result(error_message)
            return

        try:
            assert entries is not None
            image_url = await self.b50_helper.generate_image(
                self, profile, entries, uid
            )
            if (
                event.get_platform_name() == "discord"
            ):  # 在Discord上，依靠yield进行被动发送图片会导致图片发送失败，正在对self.context.send_message(即主动发送)进行测试
                umo = event.unified_msg_origin
                message_chain = (
                    MessageChain().message("这是你的B50数据~").image(image_url)
                )
                await self.context.send_message(umo, message_chain)
            else:
                chain = [Comp.Plain("这是你的B50数据~"), Comp.Image.fromURL(image_url)]
                yield event.chain_result(chain)
        except Exception as e:
            logger.error("Failed to generate B50 image: %s", e, exc_info=True)
            yield event.plain_result(
                f"绘制失败了... 只能给你文字版了：\n{self.b50_helper.render_summary(self, profile, entries)}"
            )

    @mai.command("ap50")
    async def mai_ap50(self, event: AstrMessageEvent):
        """查询maimai ap50数据"""
        bot_sid = self.sid
        bot_password = self.password
        if bot_sid == "":
            yield event.plain_result(
                "插件未配置BOT_SID，无法查询数据，请联系管理员配置好BOT_SID后再试"
            )
            return
        if bot_password == "":
            yield event.plain_result(
                "插件未配置BOT_PASSWORD，无法查询数据，请联系管理员配置好BOT_PASSWORD后再试"
            )
            return

        platform_name = event.get_platform_name()
        uid = event.get_sender_id()
        row = self._get_binding(uid, platform_name, "INT")
        if not row:
            yield event.plain_result(
                "未绑定国际服好友码，请先使用 /mai bind INT <好友码> 绑定"
            )
            return
        _, friend_code = row

        yield event.plain_result("正在查询 AP50 数据，请稍候~")
        error_message, profile, entries = await self.lookup_helper.fetch_friend_entries(
            self,
            bot_sid,
            bot_password,
            friend_code,
            "ap50",
        )
        if error_message:
            yield event.plain_result(error_message)
            return

        try:
            assert entries is not None
            image_url = await self.ap50_helper.generate_image(
                self, profile, entries, uid
            )
            if event.get_platform_name() == "discord":
                umo = event.unified_msg_origin  # 在Discord上，依靠yield进行被动发送图片会导致图片发送失败，正在对self.context.send_message(即主动发送)进行测试
                message_chain = (
                    MessageChain().message("这是你的AP50数据~").image(image_url)
                )
                await self.context.send_message(umo, message_chain)
            else:
                chain = [Comp.Plain("这是你的AP50数据~"), Comp.Image.fromURL(image_url)]
                yield event.chain_result(chain)
        except Exception as e:
            logger.error("Failed to generate AP50 image: %s", e, exc_info=True)
            yield event.plain_result(
                f"绘制失败了... 只能给你文字版了：\n{self.ap50_helper.render_summary(self, profile, entries)}"
            )

    @mai.command("search", alias={"搜索"})
    async def mai_search(self, event: AstrMessageEvent, keyword: str = ""):
        """搜索maimai歌曲定数"""
        if not keyword or keyword.strip() == "":
            yield event.plain_result(
                "请输入搜索关键词，例如: /mai search SUPER AMBULANCE"
            )
            return

        async with aiohttp.ClientSession() as session:
            try:
                await self._ensure_constant_table_loaded(session)

                # Search through entries
                keyword_lower = keyword.lower()
                matching_entries = []

                for entry in self.constant_table_manager.entries:
                    title = entry.get("title", "").lower()
                    # Search by title or version
                    if (
                        keyword_lower in title
                        or keyword_lower in entry.get("version", "").lower()
                    ):
                        matching_entries.append(entry)

                if not matching_entries:
                    yield event.plain_result(f"未找到匹配 '{keyword}' 的歌曲~")
                    return

                # Sort by title
                matching_entries.sort(key=lambda x: x.get("title", ""))

                # Format results (limit to first 20 to avoid spam)
                result_lines = [
                    f"找到 {len(matching_entries)} 首歌曲 (使用{self.constant_table_selection}定数表):"
                ]

                for i, entry in enumerate(matching_entries[:20], 1):
                    title = entry.get("title", "Unknown")
                    version = entry.get("version", "Unknown")

                    # Extract and display constants for all difficulties
                    constants = []
                    for diff_idx, diff_label in DIFF_LABELS.items():
                        dx_key = f"dx_lev_{DIFF_CONSTANT_SUFFIX.get(diff_idx)}_i"
                        std_key = f"lev_{DIFF_CONSTANT_SUFFIX.get(diff_idx)}_i"

                        dx_const = entry.get(dx_key)
                        std_const = entry.get(std_key)

                        if std_const:
                            constants.append(f"[{diff_label[:3]}] {std_const}")
                        if dx_const:
                            constants.append(f"[{diff_label[:3]}*] {dx_const}")

                    const_str = " ".join(constants) if constants else "No data"
                    result_lines.append(f"{i:2d}. {title} (v{version}) | {const_str}")

                if len(matching_entries) > 20:
                    result_lines.append(f"... 还有 {len(matching_entries) - 20} 首歌曲")

                yield event.plain_result("\n".join(result_lines))

            except Exception as e:
                logger.error("Search command failed: %s", e, exc_info=True)
                yield event.plain_result(f"搜索出错: {str(e)}")

    # @filter.command_group("chu")
    # async def chu(self, event: AstrMessageEvent):
    #    pass

    @filter.permission_type(filter.PermissionType.ADMIN)
    @mai.command(
        "reload-constant-table", alias={"reload-CT", "rct", "刷新定数表", "RCT"}
    )
    async def reload_constant_table(self, event: AstrMessageEvent, selection: str = ""):
        """管理员指令，强制刷新定数表数据，可选择表版本 (JP/INT)"""
        # If selection is specified, switch to that table first
        if selection:
            selection_upper = selection.upper()
            if selection_upper not in ("JP", "INT"):
                yield event.plain_result("无效的表版本，请使用 JP 或 INT")
                return
            try:
                self.constant_table_manager.set_table_selection(selection_upper)
                self.constant_table_selection = selection_upper
                logger.info("Switched constant table to %s", selection_upper)
            except ValueError as e:
                yield event.plain_result(f"切换表版本失败: {str(e)}")
                return

        async with aiohttp.ClientSession() as session:
            try:
                entries = await self.constant_table_manager.refresh(session)
                yield event.plain_result(
                    f"定数表已刷新 (使用{self.constant_table_selection}版本)，当前共有 {len(entries)} 条记录"
                )
                logger.info(
                    "Constant table reloaded with %s version, %s entries loaded",
                    self.constant_table_selection,
                    len(entries),
                )
            except Exception as e:
                logger.error("Failed to refresh constant table: %s", e, exc_info=True)
                yield event.plain_result(f"刷新定数表失败: {str(e)}")

    @filter.command("chu")
    async def chu(self, event: AstrMessageEvent, keyword: str = ""):
        yield event.plain_result("中二相关功能正在开发喵！为什么不去找开发者催更呢w？")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        if hasattr(self, "conn"):
            self.conn.close()
