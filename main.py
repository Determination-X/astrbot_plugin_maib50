import os
import pickle  # 用于保存和加载cookies
import re
import sqlite3  # 存储绑定信息的数据库
from datetime import datetime, timedelta, timezone

import aiohttp  # 异步HTTP请求库，用于向maimai net爬取数据
from bs4 import BeautifulSoup  # 用于解析HTML

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

plugin_name = "astrbot_plugin_maib50"
help_text = """/mai可用指令:
├─/mai b50
├─/mai bind INT <好友码>
│  /mai bind CN (开发中)
│  /mai bind JP (暫定)
│  /mai bind RIN (开发中)
│  /mai bind MUNET (开发中)
├─/mai unbind [服务器]
├─/mai help
└─/mai search <关键词>

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


@register("astrbot_plugin_maib50", "诶嘿怪awa", "Maib50 国际服插件", "0.0.1")
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
        self.db_path = os.path.join("data", "plugin_data", plugin_name, "bindings.db")
        self.cookies_path = os.path.join(
            "data", "plugin_data", plugin_name, "cookies.pkl"
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._ensure_bindings_table()
        self.debug_mode = False  # 是否开启调试模式，开启后会在查询过程中输出更多调试信息，方便开发和排查问题。发布前会关闭。

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

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

    def _ensure_bindings_table(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bindings'"
        )
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(bindings)")
            columns = [row[1] for row in cursor.fetchall()]
            if columns == ["qq_id", "friend_code", "server"]:
                cursor.execute("ALTER TABLE bindings RENAME TO bindings_old")
                cursor.execute(
                    """CREATE TABLE bindings (
                    qq_id TEXT,
                    friend_code TEXT,
                    server TEXT,
                    PRIMARY KEY (qq_id, server)
                )"""
                )
                cursor.execute(
                    "INSERT OR REPLACE INTO bindings (qq_id, friend_code, server) SELECT qq_id, friend_code, server FROM bindings_old"
                )
                cursor.execute("DROP TABLE bindings_old")
                self.conn.commit()
                return
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS bindings (
            qq_id TEXT,
            friend_code TEXT,
            server TEXT,
            PRIMARY KEY (qq_id, server)
        )"""
        )
        self.conn.commit()

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

    async def _debug(self, event: AstrMessageEvent, message: str):
        if not self.debug_mode:
            return
        yield event.plain_result(f"[DEBUG] {message}")

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
        for card in soup.select("div.music_expert_score_back"):
            title_node = card.select_one("div.music_name_block")
            level_node = card.select_one("div.music_lv_block")
            score_cells = card.select("td.expert_score_label")
            detail_cells = card.select("table tr:nth-of-type(2) td")
            if (
                title_node is None
                or level_node is None
                or len(score_cells) < 2
                or len(detail_cells) < 2
            ):
                continue

            title = self._normalize_whitespace(title_node.get_text())
            if not title:
                continue

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
                    "difficulty_index": diff_index,
                    "achievement": achievement,
                    "achievement_text": f"{achievement:.4f}%",
                    "unplayed": unplayed,
                    "icons": self._extract_icon_names(detail_cells[-1]),
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

    def _render_b50_summary(self, profile: dict, entries: list[dict]) -> str:
        played_entries = [entry for entry in entries if not entry["unplayed"]]
        played_entries.sort(key=lambda entry: entry["achievement"], reverse=True)
        top_entries = played_entries[:50]
        unplayed_count = len(entries) - len(played_entries)

        lines = [
            f"{profile['name']} (Rating: {profile['rating']})",
            f"Played charts: {len(played_entries)} / {len(entries)}",
            f"Unplayed charts excluded: {unplayed_count}",
            f"Top {len(top_entries)} charts by achievement:",
        ]
        for index, entry in enumerate(top_entries, start=1):
            lines.append(
                f"{index:02d}. [{entry['difficulty']}] {entry['title']} | {entry['type']} {entry['level']} | {entry['achievement_text']}"
            )
        if not top_entries:
            lines.append("No played charts found for this friend.")
        return "\n".join(lines)

    @filter.command_group("mai")
    async def mai(self):
        pass

    @mai.command("help", default=True)
    async def mai_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        yield event.plain_result(help_text)

    @mai.command("bind")
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
                "服务器输错了喵，请使用 INT、CN、RIN 或 MUNET 作为服务器参数"
            )
            return
        if len(event.message_str.split()) < 3:
            yield event.plain_result(
                "参数错误！请使用 /mai bind <服务器> <好友码> 的格式进行绑定喵"
            )
            return
        if not friend_code.isdigit():
            yield event.plain_result("好友码输错了喵，好友码应该是纯数字")
            return
        normalized_server = self._normalize_server(server)
        if not normalized_server:
            yield event.plain_result(
                "服务器输错了喵，请使用 INT、CN、RIN、JP 或 MUNET 作为服务器参数"
            )
            return
        if normalized_server != "INT":
            yield event.plain_result(
                f"{server} 的绑定功能正在开发喵~为什么不去找开发者催更呢w？"
            )
            return
        qq_id = event.get_sender_id()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT friend_code FROM bindings WHERE qq_id = ? AND server = ?",
            (qq_id, normalized_server),
        )
        row = cursor.fetchone()
        if row:
            old_code = row[0]
            if old_code == friend_code:
                yield event.plain_result(f"你已经绑定了当前国际服好友码：{friend_code}")
                return
            self.conn.execute(
                "INSERT OR REPLACE INTO bindings (qq_id, friend_code, server) VALUES (?, ?, ?)",
                (qq_id, friend_code, normalized_server),
            )
            self.conn.commit()
            yield event.plain_result(
                f"已将国际服好友码从 {old_code} 更新为 {friend_code}"
            )
            return
        self.conn.execute(
            "INSERT OR REPLACE INTO bindings (qq_id, friend_code, server) VALUES (?, ?, ?)",
            (qq_id, friend_code, normalized_server),
        )
        self.conn.commit()
        yield event.plain_result(f"成功绑定国际服好友码：{friend_code}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @mai.command("view-all-binds")
    async def mai_view_all_binds(self, event: AstrMessageEvent, force: str = ""):
        """管理员指令，查看所有绑定信息"""
        if event.get_group_id() != "" and force not in ["--force", "-f"]:
            yield event.plain_result(
                "该指令涉及玩家好友码隐私，只能在私聊中使用喵！如要強制在群里使用，请添加--force或-f参数"
            )
            return
        cursor = self.conn.cursor()
        cursor.execute("SELECT qq_id, friend_code, server FROM bindings")
        rows = cursor.fetchall()
        if not rows:
            yield event.plain_result("没有任何绑定信息")
            return
        result = "所有绑定信息:\n"
        for qq_id, friend_code, server in rows:
            result += f"QQ ID: {qq_id}, 服务器: {server}, 好友码: {friend_code}\n"
        yield event.plain_result(result)

    @mai.command("unbind")
    async def mai_unbind(self, event: AstrMessageEvent, server: str = ""):
        """解绑好友码"""
        qq_id = event.get_sender_id()
        cursor = self.conn.cursor()
        if server:
            normalized_server = self._normalize_server(server)
            if not normalized_server:
                yield event.plain_result(
                    "服务器输错了喵，请使用 INT、CN、RIN、JP 或 MUNET 作为服务器参数"
                )
                return
            cursor.execute(
                "SELECT friend_code FROM bindings WHERE qq_id = ? AND server = ?",
                (qq_id, normalized_server),
            )
            row = cursor.fetchone()
            if not row:
                yield event.plain_result(f"你还没有绑定{normalized_server}的好友码")
                return
            self.conn.execute(
                "DELETE FROM bindings WHERE qq_id = ? AND server = ?",
                (qq_id, normalized_server),
            )
            self.conn.commit()
            yield event.plain_result(
                f"已解绑{normalized_server}好友码，maimai DX NET上的好友关系需要你手动删除喵~(或者考虑找开发者催更一个自动删除好友的功能(挖坑+1...)"
            )
            return
        cursor.execute(
            "SELECT friend_code, server FROM bindings WHERE qq_id = ?", (qq_id,)
        )
        row = cursor.fetchone()
        if not row:
            yield event.plain_result("你还没有绑定任何好友码")
            return
        self.conn.execute("DELETE FROM bindings WHERE qq_id = ?", (qq_id,))
        self.conn.commit()
        yield event.plain_result(
            "解绑成功，maimai DX NET上的好友关系需要你手动删除喵~(或者考虑找开发者催更一个自动删除好友的功能w)"
        )

    @mai.command("b50")
    async def mai_b50(self, event: AstrMessageEvent):
        """查询maimai b50数据"""
        # code for login and data fetching here
        bot_sid = self.sid
        bot_password = self.password
        if bot_sid == "":
            yield event.plain_result(
                "插件未配置BOT_SID，无法查询数据，请联系管理员配置好BOT_SID后再试喵"
            )
            return
        if bot_password == "":
            yield event.plain_result(
                "插件未配置BOT_PASSWORD，无法查询数据，请联系管理员配置好BOT_PASSWORD后再试喵"
            )
            return

        # maimai DX NET Maintainance Time: Every Tuesday 2:00-6:00 UTC+9
        #now_gmt9 = datetime.now(timezone(timedelta(hours=9)))

        #if now_gmt9.weekday() == 1 and 2 <= now_gmt9.hour < 6:
        #    yield event.plain_result(
        #        "现在是每周二的维护时间(02:00-06:00 UTC+9),暂时无法查询数据,请在维护结束后再试喵"
        #    )
        #    return

        qq_id = event.get_sender_id()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT friend_code, server FROM bindings WHERE qq_id = ? AND server = ?",
            (qq_id, "INT"),
        )
        row = cursor.fetchone()
        if not row:
            yield event.plain_result(
                "未绑定国际服好友码，请先使用 /mai bind INT <好友码> 绑定"
            )
            return
        friend_code, server = row

        async for debug_msg in self._debug(
            event, f"SID= {bot_sid} , Friend Code= {friend_code}"
        ):
            yield debug_msg

        # Login using aiohttp
        login_url = "https://lng-tgk-aime-gw.am-all.net/common_auth/login/sid"
        login_data = {"retention": "1", "sid": bot_sid, "password": bot_password}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Cache-Control": "max-age=0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://lng-tgk-aime-gw.am-all.net",
            "Referer": "https://lng-tgk-aime-gw.am-all.net/common_auth/login?redirect_url=https%3A%2F%2Fmaimaidx-eng.com%2Fmaimai-mobile%2F&site_id=maimaidxex&back_url=https%3A%2F%2Fmaimai.sega.com%2F&alof=0",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }

        login_page_url = "https://lng-tgk-aime-gw.am-all.net/common_auth/login?redirect_url=https%3A%2F%2Fmaimaidx-eng.com%2Fmaimai-mobile%2F&site_id=maimaidxex&back_url=https%3A%2F%2Fmaimai.sega.com%2F&alof=0"
        get_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }

        async with aiohttp.ClientSession() as session:
            try:
                # Try to load cached cookies first
                cached_cookies = self._load_cookies()
                needs_login = True

                if cached_cookies:
                    # Load cached cookies into session
                    session.cookie_jar._cookies = cached_cookies  # pyright: ignore[reportAttributeAccessIssue]
                    async for debug_msg in self._debug(event, "使用缓存的cookies"):
                        yield debug_msg

                    # Verify if cached cookies are still valid by making a test request
                    test_url = "https://maimaidx-eng.com/maimai-mobile/home"
                    async with session.get(
                        test_url, allow_redirects=False
                    ) as test_resp:
                        async for debug_msg in self._debug(
                            event, f"验证缓存cookies状态码: {test_resp.status}"
                        ):
                            yield debug_msg
                        if test_resp.status == 200:
                            async for debug_msg in self._debug(
                                event, "缓存cookies仍然有效，跳过登录"
                            ):
                                yield debug_msg
                            needs_login = False
                        else:
                            async for debug_msg in self._debug(
                                event, "缓存cookies已过期，重新登录"
                            ):
                                yield debug_msg

                if needs_login:
                    async for debug_msg in self._debug(event, "执行登录流程"):
                        yield debug_msg

                    # First, GET the login page to establish session
                    async with session.get(login_page_url, headers=get_headers) as resp:
                        async for debug_msg in self._debug(
                            event, f"GET status: {resp.status}"
                        ):
                            yield debug_msg
                        if resp.status != 200:
                            yield event.plain_result(
                                f"获取登录页面失败，状态码: {resp.status}"
                            )
                            return

                    # Then, POST the login data
                    async with session.post(
                        login_url,
                        data=login_data,
                        headers=headers,
                        allow_redirects=True,
                    ) as resp:
                        final_url = str(resp.url)
                        async for debug_msg in self._debug(
                            event,
                            f"POST Response status: {resp.status}, Final URL: {final_url}",
                        ):
                            yield debug_msg
                        async for debug_msg in self._debug(
                            event, f"History length: {len(resp.history)}"
                        ):
                            yield debug_msg

                        # Check redirect history for ssid
                        ssid = None
                        for i, redirect_resp in enumerate(resp.history):
                            location = redirect_resp.headers.get("Location", "")
                            async for debug_msg in self._debug(
                                event, f"Redirect {i}: {location}"
                            ):
                                yield debug_msg
                            if "ssid=" in location:
                                ssid = (
                                    location.split("ssid=")[1].split("&")[0]
                                    if "&" in location.split("ssid=")[1]
                                    else location.split("ssid=")[1]
                                )
                                break

                        cookies = session.cookie_jar.filter_cookies(final_url)  # pyright: ignore[reportArgumentType]
                        async for debug_msg in self._debug(
                            event, f"Cookies: {dict(cookies)}"
                        ):
                            yield debug_msg

                        # Save cookies for future use
                        self._save_cookies(session.cookie_jar)
                        async for debug_msg in self._debug(event, "cookies已保存"):
                            yield debug_msg

                        if ssid:
                            async for debug_msg in self._debug(
                                event, f"登录成功，SSID from redirect: {ssid}"
                            ):
                                yield debug_msg
                        elif cookies.get("ssid"):
                            async for debug_msg in self._debug(
                                event, "登录成功，SSID from cookie"
                            ):
                                yield debug_msg
                        elif (
                            final_url == "https://maimaidx-eng.com/maimai-mobile/home/"
                        ):
                            async for debug_msg in self._debug(
                                event, "登录成功，到达home页面"
                            ):
                                yield debug_msg
                        else:
                            yield event.plain_result(f"登录失败，状态码: {resp.status}")
                            return

                # At this point, session has valid cookies, proceed with b50 data fetching
                # Start with fetching friend profile to verify friend status
                friend_bio_url = f"https://maimaidx-eng.com/maimai-mobile/friend/friendDetail/?idx={friend_code}"
                async with session.get(
                    friend_bio_url, headers=get_headers, allow_redirects=False
                ) as friend_resp:
                    async for debug_msg in self._debug(
                        event,
                        f"friendDetail GET status: {friend_resp.status}, url={friend_resp.url}",
                    ):
                        yield debug_msg
                    if friend_resp.status == 200:
                        async for debug_msg in self._debug(
                            event, "目标好友已在好友列表中，直接继续获取B50数据"
                        ):
                            yield debug_msg
                    else:
                        # Not a current friend: try to send a friend request using friendCode search and invite
                        friend_search_url = f"https://maimaidx-eng.com/maimai-mobile/friend/search/searchUser/?friendCode={friend_code}"
                        async with session.get(
                            friend_search_url,
                            headers={**get_headers, "Referer": friend_bio_url},
                        ) as search_resp:
                            async for debug_msg in self._debug(
                                event,
                                f"friend search status: {search_resp.status}, url={search_resp.url}",
                            ):
                                yield debug_msg
                            if search_resp.status != 200:
                                yield event.plain_result(
                                    f"获取好友搜索页面失败，状态码: {search_resp.status}"
                                )
                                return
                            search_html = await search_resp.text()
                        token = self._extract_token_from_html(search_html)
                        if not token:
                            yield event.plain_result(
                                "未能在好友搜索页面解析到 token，无法发送好友请求"
                            )
                            return
                        invite_url = "https://maimaidx-eng.com/maimai-mobile/friend/search/invite/"
                        invite_headers = {
                            "User-Agent": get_headers["User-Agent"],
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                            "Accept-Language": get_headers["Accept-Language"],
                            "Accept-Encoding": get_headers["Accept-Encoding"],
                            "Cache-Control": "max-age=0",
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Origin": "https://maimaidx-eng.com",
                            "Referer": friend_search_url,
                            "Upgrade-Insecure-Requests": "1",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "same-origin",
                            "Sec-Fetch-User": "?1",
                            "Sec-Ch-Ua": get_headers["Sec-Ch-Ua"],
                            "Sec-Ch-Ua-Mobile": get_headers["Sec-Ch-Ua-Mobile"],
                            "Sec-Ch-Ua-Platform": get_headers["Sec-Ch-Ua-Platform"],
                        }
                        invite_data = {"idx": friend_code, "token": token, "invite": ""}
                        async with session.post(
                            invite_url,
                            data=invite_data,
                            headers=invite_headers,
                            allow_redirects=False,
                        ) as invite_resp:
                            async for debug_msg in self._debug(
                                event,
                                f"invite POST status: {invite_resp.status}, url={invite_resp.url}",
                            ):
                                yield debug_msg
                            if invite_resp.status in (302, 303):
                                location = invite_resp.headers.get("Location", "")
                                async for debug_msg in self._debug(
                                    event, f"好友请求已发送，跳转到: {location}"
                                ):
                                    yield debug_msg
                                yield event.plain_result(
                                    "未添加好友，已发送好友请求，请等待对方批准"
                                )
                                return
                            invite_text = await invite_resp.text()
                            if (
                                "already" in invite_text.lower()
                                or "已添加" in invite_text
                                or "请求已发送" in invite_text
                            ):
                                yield event.plain_result(
                                    "好友已存在或好友请求已发送，请确认后再试"
                                )
                                return
                            yield event.plain_result(
                                f"发送好友请求失败，状态码: {invite_resp.status}"
                            )
                            return

                profile = None
                entries = []
                for diff_index in range(5):
                    diff_name = DIFF_LABELS.get(diff_index, str(diff_index))
                    async for debug_msg in self._debug(
                        event, f"Fetching friend VS page for {diff_name}"
                    ):
                        yield debug_msg
                    html = await self._fetch_friend_vs_page(
                        session, friend_code, diff_index, get_headers
                    )
                    if profile is None:
                        async for debug_msg in self._debug(
                            event, "Parsing friend profile from first VS page"
                        ):
                            yield debug_msg
                        profile = self._extract_friend_profile(html)
                    async for debug_msg in self._debug(
                        event, f"Parsing friend chart entries for {diff_name}"
                    ):
                        yield debug_msg
                    parsed_entries = self._parse_friend_entries_from_html(
                        html, diff_index
                    )
                    entries.extend(parsed_entries)
                    async for debug_msg in self._debug(
                        event,
                        f"Parsed {len(parsed_entries)} charts for {diff_name} ({sum(not entry['unplayed'] for entry in parsed_entries)} played)",
                    ):
                        yield debug_msg
                async for debug_msg in self._debug(
                    event,
                    f"Parsed {len(entries)} charts, {sum(not entry['unplayed'] for entry in entries)} played",
                ):
                    yield debug_msg
                yield event.plain_result(self._render_b50_summary(profile, entries))
                return

            except Exception as e:
                yield event.plain_result(f"登录出错: {str(e)}")

        # code for image generation here, we need Pillow here!

        # chain= [
        #     Comp.At(qq=event.get_sender_id()),
        #     Comp.Plain(" 你的B50来了喵~"),
        #     Comp.Image.fromFileSystem(f"data/plugin_data/{plugin_name}/b50_image/{event.get_sender_id()}.jpg")
        # ]
        # yield event.chain_result(chain)

    # @mai.command("search")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("debug")
    async def debug(self, event: AstrMessageEvent, debug_flag: str = "toggle"):
        """调试指令，输出调试信息"""
        if debug_flag == "toggle":
            self.debug_mode = not self.debug_mode
            yield event.plain_result(
                f"调试模式已{'开启' if self.debug_mode else '关闭'}"
            )
        elif debug_flag == "status":
            yield event.plain_result(
                f"调试模式当前状态: {'开启' if self.debug_mode else '关闭'}"
            )
        elif debug_flag == "on":
            self.debug_mode = True
            yield event.plain_result("调试模式已开启")
        elif debug_flag == "off":
            self.debug_mode = False
            yield event.plain_result("调试模式已关闭")
        else:
            yield event.plain_result(
                "无效的调试参数！使用 /debug toggle 切换调试模式，/debug status 查看当前状态"
            )

    # @filter.command_group("chu")
    # async def chu(self, event: AstrMessageEvent):
    #    pass

    @filter.command("chu")
    async def chu(self, event: AstrMessageEvent, keyword: str = ""):
        yield event.plain_result("中二相关功能正在开发喵！为什么不去找开发者催更呢w？")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        if hasattr(self, "conn"):
            self.conn.close()
