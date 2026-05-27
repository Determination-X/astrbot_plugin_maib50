# AstrBot maimai B50 International Server Plugin

[中文README](https://github.com/Determination-X/astrbot_plugin_maib50/)

This is a standalone AstrBot plugin that logs into the international version of maimai DX NET, fetches friend score data from the friend VS pages, combines it with external constant tables, and generates `B50` and `AP50` images or text results.

- Added `AP50`, which filters charts by `ALL PERFECT / ALL PERFECT+` before calculating `New15 + Old35`.
- `B50` and `AP50` share the same login, friend validation, scraping, and parsing pipeline to reduce duplicated logic.
- Binding information is now stored using `platform + UID + server`, allowing the same user to bind different accounts on different platforms.
- Constant tables support switching between `INT / JP`, with administrator commands for manual refresh.
- Discord-specific image sending compatibility was added to avoid failures caused by directly sending internal URLs.

## Preview

### B50

![B50 Preview](https://raw.githubusercontent.com/Determination-X/astrbot_plugin_maib50/master/docs/b50.jpg)

### AP50

Currently unavailable because the developer has skill issues and does not even have half a song with AP yet (((

## Installation

Install using the repository URL in the AstrBot WebUI:

`https://github.com/Determination-X/astrbot_plugin_maib50.git`

The plugin is not yet available in the AstrBot plugin marketplace.

Python dependencies are automatically managed by AstrBot using the provided `requirements.txt`.

## Features

- `/mai b50`  
  Query the international server `Best 50` for the currently bound friend code.

- `/mai ap50`  
  Query the international server `AP50`, including both `AP` and `AP+` charts.

- `/mai bind <server> <friend_code>` / `/mai 绑定 <server> <friend_code>`  
  Bind a friend code.

- `/mai unbind [server]` / `/mai 解绑 [server]`  
  Unbind the friend code on the current platform. If no server is specified, all bindings on the current platform are removed.

- `/mai search <keyword>` / `/mai 搜索 <keyword>`  
  Search songs and constants in the currently loaded constant table by title or version.

- `/mai view-all-binds [--force|-f]`  
  Administrator command to view all bindings. By default, this can only be used in private chats.

- `/mai reload-constant-table [JP|INT]`  
  Administrator command to forcibly refresh the constant table and optionally switch versions.

- `/mai help`  
  Show help information.

The plugin uses standard AstrBot command groups and does not support plain text triggers. Whether `/` or other prefixes are required depends on your AstrBot configuration.

## Server Support

Currently, only the international server `INT` is fully functional.

`CN / JP / Rin / MuNET` servers only retain parameter parsing and name normalization. Binding and query logic for those servers is not yet implemented.

Recognized aliases for the international server include:

- `INT`
- `int`
- `国际服`
- `國際服`
- `International`

## B50 / AP50 Details

The plugin scrapes data from all five difficulty pages and parses:

- Song title
- Difficulty
- Level
- Chart type (`STD / DX`)
- Achievement percentage
- Clear icon

The results are then matched against the constant table to retrieve chart constants, version numbers, and jacket images for rendering.

Both `B50` and `AP50` follow:

- `New15 + Old35`
- Automatically infer `VERSION_FLOOR_THRESHOLD` if left empty
- Use manual threshold when configured

`AP50` filtering rules:

- Icon contains `ap`
- Or icon contains `app`

Meaning both `ALL PERFECT` and `ALL PERFECT+` are included.

## Friend and Query Workflow

The plugin logs into the international server website using the configured Bot SEGA ID.

If the target friend code is already in the Bot account’s friend list, scores are fetched directly.

If not, the plugin will attempt to search for the player and send a friend request, then stop the current query and ask the user to accept the request on [DX NET](https://maimaidx-eng.com/maimai-mobile/home/).

This means:

- The bot account must have valid `BOT_SID` and `BOT_PASSWORD` configured.
- The target player must accept the friend request before `B50 / AP50` queries can work.

## Constant Table Details

The plugin does not fetch constants directly from the official site.

Instead, it uses external constant table data sources:

- JP: `https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex.json`
- INT: `https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex-intl.json`

Current support includes:

- Choosing default table version (`JP` or `INT`)
- Temporary switching and refreshing through admin command
- Title normalization matching
- Some known alias mappings

If chart titles do not perfectly match the constant table, the plugin attempts to match through normalization and aliases. Unmatched charts will not be included in rating calculations.

Song alias support is still under development and may integrate existing alias libraries in the future.

## Image Rendering

The plugin uses built-in HTML templates to render result images.

Configurable options:

- `BACKGROUND_IMAGE`  
  Custom background image

Jacket images are loaded from local files under `static/jacket`.

If a jacket image is missing, the result image can still be generated, but the chart cover will appear empty.

On Discord, rendered images are additionally downloaded as binary data and converted to Base64 before sending to avoid failures caused by inaccessible internal URLs.

## Configuration

Plugin configuration is located under the `INT` section in AstrBot plugin settings:

- `BOT_SID`  
  SEGA ID used by the bot

- `BOT_PASSWORD`  
  Bot account password

- `VERSION_FLOOR_THRESHOLD`  
  Manually specify the `New15` version cutoff. Leave empty for automatic detection.

- `CONSTANT_TABLE_SELECTION`  
  Default constant table version (`JP` or `INT`)

- `BACKGROUND_IMAGE`  
  Background image for result rendering

## Data Storage

Plugin data is stored in the standard AstrBot plugin data directory, mainly including:

- `bindings.db`
- `cookies.pkl`
- `static/jacket/*`

(Jacket resources must be manually provided. Source: [otoge-db](https://github.com/zvuc/otoge-db/tree/master/maimai/jacket))

Details:

- `bindings.db` uses SQLite and stores:
  `uid + platform_name + server + friend_code`

- `cookies.pkl` stores login cookies to reduce repeated logins.

The plugin does not persist previous `B50 / AP50` query results or cache historical player snapshots.

Constant tables are only cached in memory and are re-fetched when administrators run the refresh command.

## Runtime Environment

The plugin has no standalone startup mode and runs inside the AstrBot environment.

Deployment requirements:

- Internet access to the international server website and GitHub Raw constant table URLs
- A valid international server bot account
- Proxy configuration for platforms such as Discord and Telegram

If using custom backgrounds or local jackets, AstrBot must also have read permission for the plugin data directory.

## Tested Platforms

- Discord
- QQ Official (WebSocket)
- Telegram

> This does not mean other platforms are unsupported.  
> It only means the developer has not tested them yet.
>
> Feedback from testing on other platforms is welcome.

## Limitations

- Currently only supports the international server `INT`
- Queries depend on friendship status between the Bot account and target player
- Charts that fail constant table matching are excluded from rating calculations

## Troubleshooting

### `BOT_SID` or `BOT_PASSWORD` not configured

The bot account has not been configured yet.

Fill in the international server bot account credentials in the AstrBot plugin configuration page and try again.

### Friend not added, friend request sent

The target friend code is not in the Bot account’s friend list.

Accept the friend request on [DX NET](https://maimaidx-eng.com/maimai-mobile/home/) and retry `/mai b50`.

### Failed to parse token on friend search page

The Bot account may have already sent a friend request that has not yet been accepted.

Check pending friend requests on [DX NET](https://maimaidx-eng.com/maimai-mobile/home/).

### Scores found, but some songs are missing from B50 / AP50

Common reasons:

- The chart was never played
- Achievement percentage is too low, resulting in a rating of 0
- Chart title failed to match the constant table
- In `AP50`, the chart is not `AP / AP+`

### Incorrect new/old version classification

You can manually configure `VERSION_FLOOR_THRESHOLD`.

If the constant table is outdated, automatic detection may classify newer charts incorrectly.

Version reference:

(From the MURASAKi version onward, PLUS versions use the base major version number +500, while major updates increase by +1000.)

(Before MURASAKi, every major version increased by +1000, and PLUS versions were also treated as major updates.)

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

#### Legacy

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

### Search command results differ from the official website

`/mai search` searches the currently loaded external constant table, not the official API.

Please verify:

- Whether the current table is `JP` or `INT`
- Whether `/mai reload-constant-table` has been executed

### Discord image sending failed

Additional compatibility logic already exists.

If issues persist, check:

- Whether a Discord proxy is required
- Whether the Bot has permission to send messages
- Whether the rendered image URL is accessible from the AstrBot environment
- Whether the image is too large or blocked by the network

## TODO

- [x] INT B50
- [x] INT AP50
- [x] Discord image sending compatibility
- [ ] CN server support
- [ ] MuNET server support
- [ ] Alias library
- [ ] Multi-language support

## Credits

### Constant Table Sources

- [otoge-db JP](https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex.json)
- [otoge-db INT](https://raw.githubusercontent.com/zvuc/otoge-db/master/maimai/data/music-ex-intl.json)

### Jacket Resources

- [otoge-db jacket](https://github.com/zvuc/otoge-db/tree/master/maimai/jacket)

### Most importantly

Thanks to all players using this plugin and everyone who provided feedback and suggestions.
