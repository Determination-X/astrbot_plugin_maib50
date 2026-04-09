from astrbot.api.event import filter, AstrMessageEvent
import astrbot.api.message_components as Comp
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import aiohttp

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
        self.config = config# 获取插件配置，配置文件路径为 `data/plugin_data/astrbot_plugin_maib50/config.json`，如果没有这个文件会自动创建一个空的配置文件。可以在这个配置文件里添加一些插件需要的配置项。
        self.sid = self.config.get("INT", {}).get("BOT_SID", "") # 从配置文件中获取 BOT_SID 配置项的值，如果没有这个配置项或者值为空字符串，则默认为空字符串。
        self.password = self.config.get("INT", {}).get("BOT_PASSWORD", "") # 从配置文件中获取 BOT_PASSWORD 配置项的值，如果没有这个配置项或者值为空字符串，则默认为空字符串。
    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command_group("mai")
    async def mai(self, event: AstrMessageEvent):
        yield event.plain_result(help_text)

    @mai.command("help", default=True)
    async def mai_help(self, event: AstrMessageEvent):
        yield event.plain_result(help_text)

    @mai.command("bind")
    async def mai_bind(self, event: AstrMessageEvent, server: str="", friend_code: str=""):
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
        if server != "INT" and server != "int" and server != "国际服" and server != "International":
            yield event.plain_result(f"{server} 的绑定功能正在开发喵~为什么不去找开发者催更呢w？")
            return
        if len(event.message_str.split()) < 3:
            yield event.plain_result("参数错误！请使用 /mai bind <服务器> <好友码> 的格式进行绑定喵")
            return
        if len(friend_code) != 13 or not friend_code.isdigit():
            yield event.plain_result("好友码输错了喵！好友码应该是13位数字")
            return

    @mai.command("debug")
    async def mai_debug(self, event: AstrMessageEvent):
        yield event.plain_result(f"[DEBUG] SID= {self.sid} , PASSWORD= {self.password}")

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
        yield event.plain_result(f"[DEBUG] SID= {bot_sid} , PASSWORD= {bot_password}")

        # code for image generation here
        # chain= [
        #     Comp.At(qq=event.get_sender_id()),
        #     Comp.Plain(" 你的B50来了喵~"),
        #     Comp.Image.fromFileSystem(f"data/plugin_data/{plugin_name}/b50_image/{event.get_sender_id()}.jpg")
        # ]
        # yield event.chain_result(chain)
        
    # @mai.command("search")
    
    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        pass
