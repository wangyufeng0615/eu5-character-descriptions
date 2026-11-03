# EU5 人物介绍：发布工程

这里把研究工程写好的人物介绍构建成 EU5 模组，装进本机游戏做实验，以后也从这里发布到创意工坊。正文、身份判断和写作规则都在研究工程，这里不改正文。

## 三处位置

| | 位置 | 管什么 |
|---|---|---|
| 研究工程 | Mac mini `~/personal/paradox-mods/eu5-characters/research`（主副本，GitHub 私有库 `wangyufeng0615/eu5-character-bios-research`）；MacBook 克隆在同一路径 | 8,715 个人物的身份卡、介绍、写作规则、批量写作调度器 |
| 发布工程 | 本目录，Windows `V:\paradox-mods\eu5-characters\workshop`（本地 Git，暂无远端） | 构建、装进游戏、以后的工坊文案和发布 |
| 旧数据 | `V:\paradox-mods\eu5-characters\archive\eu5-character-biographies` | 2026-11-01 第一轮人物清点的产物，只作追溯 |

## 数据怎么流动

只单向：研究工程 `tools/export_workshop.py` 把通过自检的 `written`、`stub` 导出到本目录的 `data/bios.jsonl`，这里只读不改。改正文回研究工程改，再重新同步。

日常在 MacBook 上一步做完（MacBook 能同时连 Mac mini 和 Windows）：

```bash
cd ~/personal/paradox-mods/eu5-characters/research && tools/sync_workshop.sh             # 导出、拷到这里、构建、装进游戏
tools/sync_workshop.sh --only-written                                                    # 只放 written
```

只在 Windows 上重新构建（不更新数据）：

```bat
cd /d V:\paradox-mods\eu5-characters\workshop
python -B tools\build.py --install
```

同步脚本会把新数据提交到本目录的 Git，方便回退。

## 文件

| 路径 | 内容 |
|---|---|
| `project.json` | 模组目录名（装进游戏 `mod\` 下的文件夹名）、播放集里显示的名字、版本 |
| `data/bios.jsonl` | 研究工程导出的介绍，一行一人：`id`、`verdict`、`en`、`zh`、`displayable` |
| `mod_template/` | 固定文件：`.metadata/metadata.json`，以及改写原版人物浮窗的 `in_game/gui/zz_cb_character_tooltips.gui` |
| `tools/build.py` | 构建与安装，只用标准库 |

## 技术要点

- 可定制本地化 `cb_character_bio` 按 `this = character:<ID>` 给每人一条文本，加一个空字符串兜底；浮窗模板用 `StringIsEmpty` 判断，没有介绍的人不显示这块。
- `displayable` 为假的是没有固定脚本 ID 的事件人物，游戏里挂不上，构建时跳过。挂接方案（`on_character_created` 钩子）见研究工程 `AGENTS.md`，还没实测。
- **游戏开着时不要直接覆盖模组文件**：游戏会监视文件并自动重载，读到写了一半的文件会让人物侧栏失效。`build.py --install` 先写到 `mod\.<目录名>.new`、核对哈希，再整体改名替换。出问题时冷启动游戏可以恢复。
- 浮窗模板改写的是原版 `in_game/gui/shared/character_tooltips.gui`；游戏更新改了这个文件，要重新合并。
- 几千条介绍对浮窗性能的影响还没在游戏里测过，装好全量后要看一下浮窗有没有变卡。

## 还没做

工坊页面文案、截图、封面、版本号和更新日志的规矩、其他 9 种官方语言、GitHub 公开仓库。真要发布时照 EU5 地块发布工程（`V:\paradox-mods\eu5-locations\workshop`）补齐。
