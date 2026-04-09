from astrbot.api.event import filter, AstrMessageEvent
import astrbot.api.message_components as Comp
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import aiohttp# 异步HTTP请求库，用于向maimai net爬取数据
import os 
import sqlite3 # 存储绑定信息的数据库

plugin_name = "astrbot_plugin_maib50"
help_text = """/mai可用指令: 
├─/mai b50
├─/mai bind INT <好友码>
│  /mai bind CN (开发中)
│  /mai bind JP (暫定)
├─/mai help
└─/mai search <关键词>

可用服务器:  国际服
开发中:  国服 Rin服 MuNET
咕咕中: 日服"""

@register("astrbot_plugin_maib50", "诶嘿怪awa", "Maib50 国际服插件", "0.0.1")
class MaiPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config # 获取插件配置，配置文件路径为 `data/plugin_data/astrbot_plugin_maib50/config.json`，如果没有这个文件会自动创建一个空的配置文件。可以在这个配置文件里添加一些插件需要的配置项。
        self.sid = self.config.get("INT", {}).get("BOT_SID", "") # 从配置文件中获取 BOT_SID 配置项的值，如果没有这个配置项或者值为空字符串，则默认为空字符串。
        self.password = self.config.get("INT", {}).get("BOT_PASSWORD", "") # 从配置文件中获取 BOT_PASSWORD 配置项的值，如果没有这个配置项或者值为空字符串，则默认为空字符串。
        self.db_path = os.path.join("data", "plugin_data", plugin_name, "bindings.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('''CREATE TABLE IF NOT EXISTS bindings (
            qq_id TEXT PRIMARY KEY,
            friend_code TEXT,
            server TEXT
        )''')
        self.conn.commit()
    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command_group("mai")
    async def mai(self, event: AstrMessageEvent):
        pass

    @mai.command("help", default=True)
    async def mai_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        yield event.plain_result(help_text)

    @mai.command("bind")
    async def mai_bind(self, event: AstrMessageEvent, server: str="", friend_code: str=""):
        """绑定好友码，当前仅支持国际服"""
        if server == "help" and friend_code == "":
            yield event.plain_result("""服务器可用参数说明:
INT int 国际服 國際服 International
CN  cn  国服 國服 China
JP  jp  日服  Japan JPN jpn
RIN rin Rin服 RinNET
MUNET munet MuNET""")
            return
        if server not in ["INT", "CN", "JP", "RIN", "MUNET",
                          "int", "cn", "jp", "rin", "munet", 
                          "国际服", "国服", "日服", "Rin服",
                          "國際服", "國服",
                          "International", "China", "Japan", "RinNET", "MuNET",
                          "JPN", "jpn"]:
            yield event.plain_result("服务器输错了喵！请使用 INT、CN、RIN 或 MUNET 作为服务器参数")
            return
        if server not in ["INT", "int", "国际服", "International"]:
            yield event.plain_result(f"{server} 的绑定功能正在开发喵~为什么不去找开发者催更呢w？")
            return
        if len(event.message_str.split()) < 3:
            yield event.plain_result("参数错误！请使用 /mai bind <服务器> <好友码> 的格式进行绑定喵")
            return
        if len(friend_code) != 13 or not friend_code.isdigit():
            yield event.plain_result("好友码输错了喵！好友码应该是13位数字")
            return
        if server in ["INT", "int", "国际服", "International"]:
            qq_id = event.get_sender_id()
            normalized_server = "INT"
            self.conn.execute('INSERT OR REPLACE INTO bindings (qq_id, friend_code, server) VALUES (?, ?, ?)', (qq_id, friend_code, normalized_server))
            self.conn.commit()
            yield event.plain_result(f"成功绑定国际服好友码 {friend_code} 喵！")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @mai.command("view-all-binds")
    async def mai_view_all_binds(self, event: AstrMessageEvent):
        """管理员指令，查看所有绑定信息"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT qq_id, friend_code, server FROM bindings')
        rows = cursor.fetchall()
        if not rows:
            yield event.plain_result("没有任何绑定信息喵！")
            return
        result = "所有绑定信息:\n"
        for qq_id, friend_code, server in rows:
            result += f"QQ ID: {qq_id}, 服务器: {server}, 好友码: {friend_code}\n"
        yield event.plain_result(result)
        
    @mai.command("b50")
    async def mai_b50(self, event: AstrMessageEvent):
        """查询maimai b50数据"""
        # code for login and data fetching here
        bot_sid= self.sid
        bot_password= self.password
        if bot_sid == "":
            yield event.plain_result("插件未配置BOT_SID，无法查询数据喵！请联系管理员配置好BOT_SID后再试喵！")
            return
        if bot_password == "":
            yield event.plain_result("插件未配置BOT_PASSWORD，无法查询数据喵！请联系管理员配置好BOT_PASSWORD后再试喵！")
            return
        
        qq_id = event.get_sender_id()
        cursor = self.conn.cursor()
        cursor.execute('SELECT friend_code, server FROM bindings WHERE qq_id = ?', (qq_id,))
        row = cursor.fetchone()
        if not row:
            yield event.plain_result("未绑定好友码，请先使用 /mai bind INT <好友码> 绑定")
            return
        friend_code, server = row
        
        yield event.plain_result(f"[DEBUG] SID= {bot_sid} , PASSWORD= {bot_password}, Friend Code= {friend_code}")
        
        # Login using aiohttp
        login_url = "https://lng-tgk-aime-gw.am-all.net/common_auth/login/sid"
        login_data = {
            'retention': '1',
            'sid': bot_sid,
            'password': bot_password
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Cache-Control': 'max-age=0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://lng-tgk-aime-gw.am-all.net',
            'Referer': 'https://lng-tgk-aime-gw.am-all.net/common_auth/login?redirect_url=https%3A%2F%2Fmaimaidx-eng.com%2Fmaimai-mobile%2F&site_id=maimaidxex&back_url=https%3A%2F%2Fmaimai.sega.com%2F&alof=0',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Sec-Ch-Ua': '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"'
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(login_url, data=login_data, headers=headers, allow_redirects=True) as resp:
                    if resp.status == 200:
                        final_url = str(resp.url)
                        if 'ssid=' in final_url:
                            ssid = final_url.split('ssid=')[1].split('&')[0] if '&' in final_url.split('ssid=')[1] else final_url.split('ssid=')[1]
                            yield event.plain_result(f"[DEBUG] 登录成功，SSID= {ssid}")
                            # TODO: Use ssid to fetch b50 data
                        else:
                            yield event.plain_result("登录成功，但未找到SSID")
                    else:
                        yield event.plain_result(f"登录失败，状态码: {resp.status}")
            except Exception as e:
                yield event.plain_result(f"登录出错: {str(e)}")
        
        
        # code for image generation here
        # chain= [
        #     Comp.At(qq=event.get_sender_id()),
        #     Comp.Plain(" 你的B50来了喵~"),
        #     Comp.Image.fromFileSystem(f"data/plugin_data/{plugin_name}/b50_image/{event.get_sender_id()}.jpg")
        # ]
        # yield event.chain_result(chain)
        
    # @mai.command("search") 
    
    #@filter.command_group("chu")
    #async def chu(self, event: AstrMessageEvent):
    #    pass
    @filter.command("chu")
    async def chu_search(self, event: AstrMessageEvent, keyword: str=""):
        yield event.plain_result("中二相关功能正在开发喵！为什么不去找开发者催更呢w？")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        if hasattr(self, 'conn'):
            self.conn.close()
