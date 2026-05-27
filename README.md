# AstrBot maimai B50 国际服插件

[English README](https://github.com/Determination-X/astrbot_plugin_maib50/blob/master/README_EN.md)

这是一个独立 AstrBot 插件，通过国际服 maimai DX NET 的好友对战页面抓取好友成绩，结合外部定数表，生成 `B50` 和 `AP50` 图片或文字结果。

- 新增 `AP50`，按 `ALL PERFECT / ALL PERFECT+` 谱面筛选后再进行 `New15 + Old35` 计算。
- `B50` 与 `AP50` 共享同一套登录、好友校验、抓取和解析链路，减少重复逻辑。
- 绑定信息升级为按 `平台 + UID + 服务器` 存储，同一个用户在不同平台可分别绑定。
- 定数表支持 `INT / JP` 切换，并提供管理员手动刷新命令。
- Discord 额外适配了图片发送流程，避免直接发 URL 失败。

## 效果图

### B50

![B50效果图](https://raw.githubusercontent.com/Determination-X/astrbot_plugin_maib50/master/docs/b50.jpg)

### AP50

暂无，本人skill issue导致半首歌都没有AP，所以没有AP50效果图(((

## 安装

在Astrbot WebUI中，使用仓库链接 `https://github.com/Determination-X/astrbot_plugin_maib50.git` 安装
Astrbot插件商城暂未上架
Python依赖会由Astrbot自动依照开发者提供的`requirements.txt`管理

## 功能

- `/mai b50`：查询当前绑定好友码的国际服 `Best 50`。
- `/mai ap50`：查询当前绑定好友码的国际服 `AP50`，包含 `AP` 和 `AP+` 谱面。
- `/mai bind <服务器> <好友码>` / `/mai 绑定 <服务器> <好友码>`：绑定好友码。
- `/mai unbind [服务器]` / `/mai 解绑 [服务器]`：解绑当前平台上的好友码；不填服务器时解绑当前平台下全部记录。
- `/mai search <关键词>` / `/mai 搜索 <关键词>`：按标题或版本搜索当前定数表中的歌曲与定数。
- `/mai view-all-binds [--force|-f]`：管理员查看全部绑定；默认仅允许私聊中使用。
- `/mai reload-constant-table [JP|INT]`：管理员强制刷新定数表，并可顺便切换表版本。
- `/mai help`：查看帮助。

命令组使用标准 AstrBot 命令形式，不提供裸文本触发。实际使用时是否需要 `/` 等唤醒前缀，取决于你的 AstrBot 配置。

## 服务器说明

插件目前只有国际服 `INT` 真正可用。`国服CN / 日服JP / Rin服 / MuNET` 只保留了参数入口和名称归一化，绑定和查询逻辑尚未完成。

可识别的国际服别名包括：

- `INT`
- `int`
- `国际服`
- `國際服`
- `International`

## B50 / AP50 说明

插件会抓取好友五个难度页的数据，解析出：

- 曲名
- 难度
- 定级
- 谱面类型 `STD / DX`
- 达成率
- 清谱图标

之后再把这些结果和定数表做标题匹配，补上谱面定数、版本号和曲绘，用于生成结果图。

`B50` 和 `AP50` 都遵循：

- `New15 + Old35`
- `VERSION_FLOOR_THRESHOLD` 留空时自动推断当前版本底线
- 有配置时使用手动底线

`AP50` 的筛选规则是：

- 图标包含 `ap`
- 或图标包含 `app`

也就是同时统计 `ALL PERFECT` 和 `ALL PERFECT+`。

## 好友与查询流程

插件查询时会使用配置中的 Bot SEGA ID 登录国际服官网。

如果目标好友码已经在 Bot 账号的好友列表中，插件会直接抓取成绩；如果还不是好友，插件会尝试搜索并发送好友申请，然后结束本次查询，提示你去[DX NET](https://maimaidx-eng.com/maimai-mobile/home/)上通过好友申请。

这意味着：

- 机器人账号必须配置可正常登录的 `BOT_SID` 和 `BOT_PASSWORD`
- 目标玩家需要接受 Bot 的好友申请后，后续 `B50 / AP50` 才能正常查询

## 定数表说明

插件不从官网直接读取定数，而是使用外部定数表数据源：

- JP: `https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex.json`
- INT: `https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex-intl.json`

当前支持：

- 配置中选择默认使用 `JP` 或 `INT`
- 管理员命令临时切换并刷新
- 标题规范化匹配
- 少量已知异名映射

如果定数表和官网曲名不完全一致，插件会尽量通过标准化和别名表匹配；仍匹配不到的谱面不会参与评分。

歌曲别名功能仍在开发，可能会引入现有的别名库

## 图片渲染

插件使用内置 HTML 模板渲染结果图。

可配置项：

- `BACKGROUND_IMAGE`：自定义背景图

图片中的曲绘来自插件数据目录下的本地 `static/jacket` 文件。如果没有对应曲绘，结果仍可生成，只是该曲目的封面会为空。

在 Discord 上，插件会额外把渲染结果下载为二进制后转成 Base64 再发送，避免向Discord发送来自内网的图片 URL 失败。

## 配置

插件配置项位于 AstrBot 插件配置中 `INT` 分组下：

- `BOT_SID`：Bot 使用的 SEGA ID
- `BOT_PASSWORD`：Bot 使用的密码
- `VERSION_FLOOR_THRESHOLD`：手动指定 `New15` 版本底线；留空时自动检测
- `CONSTANT_TABLE_SELECTION`：默认定数表版本，支持 `JP` 和 `INT`
- `BACKGROUND_IMAGE`：结果图背景图

## 数据

插件数据保存在 AstrBot 标准插件数据目录下，主要包括：

- `bindings.db`
- `cookies.pkl`
- `static/jacket/*`（需要你手动放入曲绘资源，来源: [otoge-db](https://github.com/zvuc/otoge-db/tree/master/maimai/jacket)）

其中：

- `bindings.db` 使用 SQLite，保存 `uid + platform_name + server + friend_code`
- `cookies.pkl` 保存 Bot 登录后的 Cookie，用于减少重复登录

插件不会持久化每个用户的上一次 `B50 / AP50` 查询结果，也不会缓存每个人的历史成绩快照。

定数表默认只在进程内缓存；管理员执行刷新命令时会重新拉取上游数据。

## 运行环境

插件本身没有额外的独立启动方式，运行在 AstrBot 环境内。

实际部署时需要注意：

- 需要网络访问国际服官网和定数表 GitHub Raw 地址
- 需要一个可登录的国际服 Bot 账号
- Discord, Telegram等平台须配置代理

如果使用自定义背景图或本地曲绘，也需要保证 AstrBot 进程对插件数据目录有读权限。

## 已测试平台

- Discord
- QQ Official (WebSocket)
- Telegram

> 不代表其他平台用不了，只代表开发者还未在该平台测试
>
> 欢迎自行测试后反馈结果

## 限制

- 当前只支持国际服 `INT`
- 查询依赖 Bot 账号和目标玩家之间的好友关系
- 未匹配到定数表的谱面不会参与评分

## 排障

### 提示未配置 `BOT_SID` 或 `BOT_PASSWORD`

说明插件配置还没填好国际服 Bot 账号。到 AstrBot 插件配置页填写后重试。

### 提示未添加好友，已发送好友请求

说明目标好友码还不在 Bot 账号好友列表内。需先在[DX NET](https://maimaidx-eng.com/maimai-mobile/home/)接受好友申请，然后重新输入/mai b50查询。

### 提示未能在好友搜索页面解析到 token

说明 BOT 曾经发送过好友请求，但未接受，需在[DX NET](https://maimaidx-eng.com/maimai-mobile/home/)确认是否有好友申请

### 查到了成绩，但部分歌曲没有进入 B50 / AP50

常见原因：

- 该谱面未游玩
- 达成率过低，计算出的 rating 为 0
- 曲名没能匹配到定数表，可在logger中查看是否为定数表缺失
- `AP50` 下该谱面不是 `AP / AP+`

### 新旧版本划分不对

可以在配置中手动设置 `VERSION_FLOOR_THRESHOLD`。如果定数表版本更新滞后，自动检测可能把新谱误分到旧谱。

版本号参考:
(MURASAKi版本开始PLUS版本为其大版本号的基础上+500，大版本更新为上个大版本的+1000)
(MURASAKi前的版本为每个大版本+1000，PLUS同样视为大版本更新)

#### DX

- CiRCLE PLUS `26500`
- CiRCLE `26000`
- PRiSM `25000`
- BUDDiES `24000`
- FESTiVAL `23000`
- UNiVERSE `22000`
- Splash `21000`
- maimai DX PLUS `20500`
- maimai DX `20000`

#### 无印

- FiNALE `19900`
- MiLK PLUS `19500`
- MiLK `19000`
- MURASAKi PLUS `18500`
- MURASAKi `18000`
- PiNK PLUS `17000`
- PiNK `16000`
- ORANGE PLUS `15000`
- ORANGE `14000`
- GreeN PLUS `13000`
- GreeN `12000`
- maimai PLUS `11000`
- maimai `10000`

### 搜索命令结果和实际官网版本不一致

`/mai search` 查的是当前加载的外部定数表，不是官网接口本身。请确认：

- 当前使用的是 `JP` 还是 `INT` 定数表
- 是否已经执行过 `/mai reload-constant-table`

### Discord 上图片发送失败

当前已经有额外兼容逻辑；如果仍失败，优先检查：

- 是否需要使用Discord 代理
- Bot 是否有正常发送消息权限
- 渲染结果 URL 是否可被 AstrBot 所在环境访问
- 图片是否过大或网络请求被拦截

## TODO

- [x] INT B50
- [x] INT AP50
- [x] Discord 图片兼容
- [ ] 国服查询
- [ ] MuNET服查询
- [ ] 别名库
- [ ] 多语言

## 鸣谢

### 定数表数据来源

[otoge-db JP](https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex.json)

[otoge-db INT](https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex-intl.json)

### 曲绘资源来源

[otoge-db jacket](https://github.com/zvuc/otoge-db/tree/master/maimai/jacket)

### 以及最重要的

所有使用这个插件的玩家们以及提意见的群友们！谢谢你们的支持和反馈！
