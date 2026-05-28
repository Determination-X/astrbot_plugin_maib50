import aiohttp

from astrbot.api import logger


class MaimaiLookupHelper:
    def _build_login_headers(self) -> dict[str, str]:
        return {
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

    def _build_get_headers(self) -> dict[str, str]:
        return {
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

    async def _ensure_logged_in(
        self,
        plugin,
        session: aiohttp.ClientSession,
        bot_sid: str,
        bot_password: str,
        command_label: str,
    ) -> str | None:
        login_url = "https://lng-tgk-aime-gw.am-all.net/common_auth/login/sid"
        login_page_url = "https://lng-tgk-aime-gw.am-all.net/common_auth/login?redirect_url=https%3A%2F%2Fmaimaidx-eng.com%2Fmaimai-mobile%2F&site_id=maimaidxex&back_url=https%3A%2F%2Fmaimai.sega.com%2F&alof=0"
        login_data = {"retention": "1", "sid": bot_sid, "password": bot_password}
        login_headers = self._build_login_headers()
        get_headers = self._build_get_headers()

        cached_cookies = plugin._load_cookies()
        needs_login = True

        if cached_cookies:
            session.cookie_jar._cookies = cached_cookies  # pyright: ignore[reportAttributeAccessIssue]
            logger.debug("Loaded cached cookies for /mai %s lookup", command_label)

            test_url = "https://maimaidx-eng.com/maimai-mobile/home"
            async with session.get(test_url, allow_redirects=False) as test_resp:
                logger.debug(
                    "Cached cookie validation for /mai %s returned status=%s",
                    command_label,
                    test_resp.status,
                )
                if test_resp.status == 200:
                    needs_login = False
                else:
                    logger.info("Cached cookies expired, logging in again")

        if not needs_login:
            return None

        logger.info("Executing maimai login flow for /mai %s", command_label)

        async with session.get(login_page_url, headers=get_headers) as resp:
            logger.debug("Login page GET returned status=%s", resp.status)
            if resp.status != 200:
                logger.error("Failed to load login page, status=%s", resp.status)
                return f"获取登录页面失败，状态码: {resp.status}"

        async with session.post(
            login_url,
            data=login_data,
            headers=login_headers,
            allow_redirects=True,
        ) as resp:
            final_url = str(resp.url)
            logger.debug(
                "Login POST returned status=%s final_url=%s history_len=%s",
                resp.status,
                final_url,
                len(resp.history),
            )

            ssid = None
            for i, redirect_resp in enumerate(resp.history):
                location = redirect_resp.headers.get("Location", "")
                logger.debug("Login redirect[%s]=%s", i, location)
                if "ssid=" in location:
                    ssid = (
                        location.split("ssid=")[1].split("&")[0]
                        if "&" in location.split("ssid=")[1]
                        else location.split("ssid=")[1]
                    )
                    break

            cookies = session.cookie_jar.filter_cookies(final_url)  # pyright: ignore[reportArgumentType]
            plugin._save_cookies(session.cookie_jar)
            logger.debug("Saved cookies after successful login")

            if ssid:
                logger.info("Login succeeded with SSID from redirect")
                return None
            if cookies.get("ssid"):
                logger.info("Login succeeded with SSID from cookie")
                return None
            if final_url == "https://maimaidx-eng.com/maimai-mobile/home/":
                logger.info("Login succeeded and reached maimai home page")
                return None

            logger.error(
                "Login failed after POST, status=%s final_url=%s",
                resp.status,
                final_url,
            )
            return f"登录失败，状态码: {resp.status}"

    async def _ensure_friend_available(
        self,
        plugin,
        session: aiohttp.ClientSession,
        friend_code: str,
        get_headers: dict[str, str],
    ) -> str | None:
        friend_bio_url = f"https://maimaidx-eng.com/maimai-mobile/friend/friendDetail/?idx={friend_code}"
        async with session.get(
            friend_bio_url, headers=get_headers, allow_redirects=False
        ) as friend_resp:
            logger.debug(
                "friendDetail returned status=%s url=%s",
                friend_resp.status,
                friend_resp.url,
            )
            if friend_resp.status == 200:
                logger.debug("Friend already exists in bot friend list")
                return None

        friend_search_url = f"https://maimaidx-eng.com/maimai-mobile/friend/search/searchUser/?friendCode={friend_code}"
        async with session.get(
            friend_search_url,
            headers={**get_headers, "Referer": friend_bio_url},
        ) as search_resp:
            logger.debug(
                "friend search returned status=%s url=%s",
                search_resp.status,
                search_resp.url,
            )
            if search_resp.status != 200:
                logger.error(
                    "Failed to load friend search page, status=%s",
                    search_resp.status,
                )
                return f"获取好友搜索页面失败，状态码: {search_resp.status}"
            search_html = await search_resp.text()

        token = plugin._extract_token_from_html(search_html)
        if not token:
            return (
                "未能在好友搜索页面解析到 token，无法发送好友请求/或者曾经添加过该好友"
            )

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
        invite_url = "https://maimaidx-eng.com/maimai-mobile/friend/search/invite/"
        async with session.post(
            invite_url,
            data=invite_data,
            headers=invite_headers,
            allow_redirects=False,
        ) as invite_resp:
            logger.debug(
                "invite POST returned status=%s url=%s",
                invite_resp.status,
                invite_resp.url,
            )
            if invite_resp.status in (302, 303):
                location = invite_resp.headers.get("Location", "")
                logger.info("Friend request sent successfully, redirect=%s", location)
                return "未添加好友，已发送好友请求，请批准后重新执行命令"

            invite_text = await invite_resp.text()
            if (
                "already" in invite_text.lower()
                or "已添加" in invite_text
                or "请求已发送" in invite_text
            ):
                return "好友已存在或好友请求已发送，请确认后再试"

            logger.error(
                "Failed to send friend request, status=%s",
                invite_resp.status,
            )
            return f"发送好友请求失败，状态码: {invite_resp.status}"

    async def fetch_friend_entries(
        self,
        plugin,
        bot_sid: str,
        bot_password: str,
        friend_code: str,
        command_label: str,
    ) -> tuple[str | None, dict | None, list[dict] | None]:
        get_headers = self._build_get_headers()

        async with aiohttp.ClientSession() as session:
            try:
                error_message = await self._ensure_logged_in(
                    plugin,
                    session,
                    bot_sid,
                    bot_password,
                    command_label,
                )
                if error_message:
                    return error_message, None, None

                error_message = await self._ensure_friend_available(
                    plugin,
                    session,
                    friend_code,
                    get_headers,
                )
                if error_message:
                    if (
                        "请等待对方批准" in error_message
                        or "请确认后再试" in error_message
                    ):
                        return error_message, None, None
                    return error_message, None, None

                profile = None
                entries = []
                await plugin._ensure_constant_table_loaded(session)
                for diff_index in range(5):
                    diff_name = (
                        plugin.DIFF_LABELS.get(diff_index, str(diff_index))
                        if hasattr(plugin, "DIFF_LABELS")
                        else str(diff_index)
                    )
                    logger.debug("Fetching friend VS page for %s", diff_name)
                    html = await plugin._fetch_friend_vs_page(
                        session, friend_code, diff_index, get_headers
                    )
                    if profile is None:
                        logger.debug("Parsing friend profile from first VS page")
                        profile = plugin._extract_friend_profile(html)
                    logger.debug("Parsing friend chart entries for %s", diff_name)
                    parsed_entries = plugin._parse_friend_entries_from_html(
                        html, diff_index
                    )
                    entries.extend(parsed_entries)
                    logger.debug(
                        "Parsed %s charts for %s (%s played)",
                        len(parsed_entries),
                        diff_name,
                        sum(not entry["unplayed"] for entry in parsed_entries),
                    )

                entries = plugin._attach_constant_table_data(entries)
                if profile is None:
                    return "Failed to parse profile", None, None

                logger.info(
                    "Parsed %s charts total (%s played)",
                    len(entries),
                    sum(not entry["unplayed"] for entry in entries),
                )
                return None, profile, entries
            except Exception as exc:
                logger.error("/mai %s failed: %s", command_label, exc, exc_info=True)
                return f"登录出错: {str(exc)}", None, None
