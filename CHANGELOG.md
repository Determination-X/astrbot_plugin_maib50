# Changelog

## 1.3.1 (2026-09-19)

### 修复与功能 / Fixes and features

- 删除仓库内的 `title_aliases.json`，在插件数据目录首次启动时创建空别名库；已有实例 JSON 不覆盖、不自动迁移旧文件。
- 别名管理拆分为 `alias_manager.py`，在内存索引查询，添加/审核通过后即时生效；JSON 原子写入。
- 支持多个别名指向同一歌曲、冲突检查、用户提交与管理员审核/直接增删。
- Removed bundled aliases; initialize empty instance-local JSON and preserve existing files without migration.
- Added in-memory alias indexing, immediate updates, moderation commands, duplicate checks and atomic persistence.

## 1.3.0 (2026-09-19)

### 增加功能 / Added feature

- `/mai search` 支持通过 `title_aliases.json` 查询歌曲别名，包括玩家简称和特殊字符兼容映射（例如 `ieo`、`最水15`、`RONDO`）。
- 歌曲完整标题和别名优先匹配；未找到时保留原有的标题与版本模糊搜索。
- 别名查询支持英文字母大小写、Unicode 和空白字符规范化；保留原有异名映射。
- Added community song aliases to `/mai search`, reusing `title_aliases.json` for both nicknames and title compatibility mappings.
- Prioritized exact-title and alias matches, retained substring title/version search as fallback, and normalized alias input.

## 1.2.0 (2026-05-22)

### 修复 / Fix

- 针对Discord的图片发送功能进行了适配，修复了Discord发送图片失败的问题。
- Adapted to Discord's image sending functionality and fixed the issue of failing to send images on Discord.

### 增加功能 / Added feature

- /mai ap50命令，查询ap50(ALL PERFECT 50)相关信息
- /mai ap50 command, to query information related to ap50(ALL PERFECT 50)

## 1.1.0 (2024-06-01)

### 优化 / Optimize

- 优化b50模版显示，在显示DXscore的基础上增加了定数显示
- Optimized the b50 template display, adding constant display on the basis of DXscore display

### 增加功能 / Added feature

- 平台识别，根据不同平台分开绑定信息
- Platform recognition, separate binding information based on different platforms

## 1.0.0 (2024-05-30)

- 初始版本发布，提供了maimai国际服相关基础功能，如b50与定数查询
- Initial release, providing basic features related to maimai international server, such as b50 and constant queries
