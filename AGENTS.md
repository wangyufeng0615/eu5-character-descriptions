# 所有历史人物的描述（Descriptions for Every Historical Character）：发布工程

这里把研究工程写好的人物介绍构建成 EU5 模组，装进本机游戏做实验，也从这里发布到创意工坊。模组 ID `character_descriptions`，工坊条目 [3833397845](https://steamcommunity.com/sharedfiles/filedetails/?id=3833397845)（2026-11-04 建，1.0.0，**私密**，改公开由作者在网页上做）。正文、身份判断和写作规则都在研究工程，这里不改正文。

## 三处位置

| | 位置 | 管什么 |
|---|---|---|
| 研究工程 | Mac mini `~/personal/paradox-mods/eu5-characters/research`（主副本，GitHub 私有库 `wangyufeng0615/eu5-character-bios-research`）；MacBook 克隆在同一路径 | 8,715 个人物的身份卡、介绍、写作规则、批量写作调度器 |
| 发布工程 | 本目录，Windows `V:\paradox-mods\eu5-characters\workshop`（GitHub 公开库 `wangyufeng0615/eu5-character-descriptions`，2026-11-12 建；Windows 连不上 GitHub，经 MacBook 转推） | 构建、装进游戏、以后的工坊文案和发布 |
| 旧数据 | `V:\paradox-mods\eu5-characters\archive\eu5-character-biographies` | 2026-11-01 第一轮人物清点的产物，只作追溯 |

## 数据怎么流动

只单向：研究工程 `tools/export_workshop.py` 把通过自检的 `written`、`stub` 导出到本目录的 `data/bios.jsonl`，这里只读不改。改正文回研究工程改，再重新同步。

日常在 MacBook 上一步做完（MacBook 能同时连 Mac mini 和 Windows）：

```bash
cd ~/personal/paradox-mods/eu5-characters/research && tools/sync_workshop.sh             # 导出、拷到这里、构建、装进游戏
tools/sync_workshop.sh --only-written                                                    # 只放 written
```

只在 Windows 上重新构建并装进游戏（不更新数据）：

```bat
cd /d V:\paradox-mods\eu5-characters\workshop
python -B tools\build.py --install [--only-written]    :: 构建到 dist\dev 并装进 文档\Paradox Interactive\Europa Universalis V\mod
```

同步脚本会把新数据提交到本目录的 Git，方便回退。2026-11-03 起模组 ID 从测试期的 `eu5_character_bios` 改为 `character_descriptions`，装到 `mod\character_descriptions`；旧的测试副本 `mod\eu5_character_bios_test` 还在，两个不要同时启用。

## 检查与构建

```bat
python -B -m unittest discover -s tests -v
python -B tools\build.py --check [--game-root "C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V"]
python -B tools\build.py --output dist\<新目录>
python -B tools\build.py --verify dist\<新目录>
```

只用 Python 标准库（3.10+）。`--check` 校验数据（每人要有中英文正文和资料来源、没有换行和游戏指令字符）、配置和生成结果；带 `--game-root` 时再核对原版人物浮窗有没有随游戏更新变化、当前 Steam 构建号。正式构建输出模组文件夹、ZIP 和 `build_receipt.json`；输出目录必须是新的。

## 发布

1. **更新数据**：研究工程质量流程跑完后，在 MacBook 上 `tools/sync_workshop.sh` 导出最新正文并装进游戏，进游戏看几个人物的浮窗（中英文各看），顺便看浮窗有没有变卡（几千条可定制本地化的性能还没实测）。
2. **准备版本**：`python -B tools\release.py 1.0.0 --note "First public release." --install --commit`。它升版本号、写 `CHANGELOG.md`、跑测试和检查、构建到 `dist\release-1.0.0\`、核对、装进游戏并提交。失败会把版本号和 CHANGELOG 改回去。`--dry-run` 只检查和构建。
3. **第一次上传（已做过）**：2026-11-04 用 `tools/steam_create.py 1.0.0` 建了条目（私密、英文页面、主封面、标签），Steam 一返回编号就写进 `project.json`；接着 `steam_page.py --descriptions` 补中文标题描述、`--assets` 补中文封面。都用计划任务在桌面会话里跑（`schtasks /create ... /ru nsh2o /it` 再 `/run`，跑完删任务），记录在 `dist/create-1.0.0.*`。`steam_create.py` 在已有编号时直接拒绝。
4. **之后的更新**：先 `release.py <新版本>`，再在登录了 Steam 的桌面会话里 `python -B tools\steam_upload.py <版本> --upload --notes-file workshop\changenotes.en.txt --output dist\upload-<版本>.json`；页面文案和封面用 `tools\steam_page.py`。这两个工具改自 EU5 地块发布工程，只更新已有条目，不建条目、不改可见性、不接受条款；远程触发的办法见 EU5 地块发布工程 `docs/PUBLISHING.md`。
5. **更新说明**：`workshop/changenotes.*.txt` 第一行写版本号，`description.*.txt` 的「更新记录」加一行，不写确切篇数（会被文案数量检查拦）。`steam_upload.py` 只带英文说明，上传后用 `steam_page.py --descriptions` 推页面文案（同样用 `schtasks /it` 放进桌面会话）。中文更新说明由 agent 在 MacBook 上用 Claude in Chrome（已登录 Steam）补，作者不操作：打开 `https://steamcommunity.com/sharedfiles/filedetails/changelog/3833397845`，点该版本的“编辑”，语言下拉选“简体中文”（页面带 `?language=6` 重载，文本框预填英文），换成 `changenotes.zh-CN.txt` 的内容后保存，回改动说明页确认中文显示。MacBook 的内置浏览器打不开 steamcommunity.com；核对上传结果可用公开接口 `ISteamRemoteStorage/GetPublishedFileDetails`（看 `time_updated`、`file_size`、`description`）。
6. **推到 GitHub**：在 MacBook 上运行研究工程 `tools/push_public.sh`（把本目录 main 打成 bundle、经本机快进推到 GitHub，再对齐这里的 `origin/main`）；发版时加 `--tag <版本>`，推送 `v<版本>` 标签后 `.github/workflows/release.yml` 从该提交构建、核对，并把 ZIP 附到 GitHub Release（说明由 `tools/release_notes.py` 从 CHANGELOG 生成）。每次推送 `check.yml` 在 Ubuntu 和 Windows 上跑检查、测试和构建。核对 Release 时比 ZIP 里各文件的哈希和本地构建回执，不比整包哈希。

**还要作者确认的事**：是否兼容成就（模组加了 `in_game/common` 下的可定制本地化，EU5 地块模组只有本地化和界面文件，情况不同，没实测）；浮窗性能；427 个没有固定脚本 ID 的事件人物还挂不上（研究工程 `AGENTS.md` 里的 `on_character_created` 方案未实测）；改公开前进游戏实看中英文浮窗、补截图。

## 文件

| 路径 | 内容 |
|---|---|
| `project.json` | 模组名（中英）、模组 ID、版本、游戏和工坊编号、`steam_api64.dll` 路径、简介、标签、许可、`only_written`、原版人物浮窗的哈希和核对过的 Steam 构建号 |
| `data/bios.jsonl` | 研究工程导出的介绍，一行一人：`id`、`verdict`、`en`、`zh`、`displayable`、`sources` |
| `mod_template/in_game/gui/zz_cb_character_tooltips.gui` | 改写原版人物浮窗（`in_game/gui/shared/character_tooltips.gui`）加上生平一块；`.metadata` 由 `build.py` 按 `project.json` 生成 |
| `tools/build.py` | 检查、构建、核对、装进游戏，只用标准库 |
| `tools/release.py` | 准备一个版本，两个发布工程相同 |
| `tools/steam_create.py` | 只用一次：建私密工坊条目 |
| `tools/steam_upload.py`、`tools/steam_page.py` | 更新已有工坊条目的内容和页面 |
| `tools/cover.py` | 从生图母版导出封面和缩略图 |
| `workshop/` | 工坊页面中英文案（BBCode）、更新说明、模组里附带的玩家说明、`page.json` |
| `workshop/assets/` | 封面母版 `cover-master.*.png`（Codex 生图模型按 EU5 地块封面的风格画成，提示词在 `cover-prompt.*.txt`）、导出的 `cover.jpg`、`cover.zh-CN.jpg`、`thumbnail.png` |
| `LICENSE`、`LICENSES/`、`CREDITS.md` | 工具 MIT、正文 CC BY-SA 4.0（照 EU5 地块模组的选择），署名和第三方说明；都会打进模组 |
| `CHANGELOG.md` | 版本记录，由 `release.py` 写 |
| `README.md`、`.github/workflows/`、`.gitattributes` | GitHub 公开页的中英文说明；推送时检查构建（`check.yml`），推 `vX.Y.Z` 标签时发布 Release（`release.yml`）；`* -text` 保证文件逐字节不变 |
| `tools/release_notes.py` | GitHub Release 说明：CHANGELOG 条目 ＋ 安装步骤 ＋ ZIP 的 SHA-256 |

## 技术要点

- 可定制本地化 `cb_character_bio` 按 `this = character:<ID>` 给每人一条文本，加一个空字符串兜底；浮窗模板用 `StringIsEmpty` 判断，没有介绍的人不显示这块。
- `displayable` 为假的是没有固定脚本 ID 的事件人物，游戏里挂不上，构建时跳过。挂接方案（`on_character_created` 钩子）见研究工程 `AGENTS.md`，还没实测。
- **游戏开着时不要直接覆盖模组文件**：游戏会监视文件并自动重载，读到写了一半的文件会让人物侧栏失效。`build.py --install` 先写到 `mod\.<目录名>.new`、核对哈希，再整体改名替换。出问题时冷启动游戏可以恢复。
- 浮窗模板改写的是原版 `in_game/gui/shared/character_tooltips.gui`；游戏更新改了这个文件（`--check --game-root` 会报 `tooltip_unchanged: false`），要重新合并，再更新 `project.json` 里的哈希和构建号。
- 几千条介绍对浮窗性能的影响还没在游戏里测过，装好全量后要看一下浮窗有没有变卡。
