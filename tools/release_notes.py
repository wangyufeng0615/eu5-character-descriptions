"""GitHub Release 说明：CHANGELOG 里这个版本的条目，加安装步骤和 ZIP 的 SHA-256。

python -B tools/release_notes.py 1.0.6 dist/release-1.0.6/character_descriptions-1.0.6.zip
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSHOP = 'https://steamcommunity.com/sharedfiles/filedetails/?id=3833397845'


def notes(version, zip_path):
    text = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    m = re.search(rf'^## {re.escape(version)}\b[^\n]*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not m:
        raise SystemExit(f'CHANGELOG.md 里没有 {version}')
    zip_path = Path(zip_path)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    return f'''{m.group(1).strip()}

### Install / 安装

1. Download **{zip_path.name}** below. / 下载下方的 **{zip_path.name}**。
2. Extract it into `Documents\\Paradox Interactive\\Europa Universalis V\\mod\\`. You should end up with `mod\\character_descriptions\\`, including its hidden `.metadata` folder. / 解压到 `文档\\Paradox Interactive\\Europa Universalis V\\mod\\`，解压后应有 `mod\\character_descriptions\\` 文件夹（含隐藏的 `.metadata` 文件夹）。
3. Start EU5, enable **Descriptions for Every Historical Character** in Mods and DLC, and play in English or Simplified Chinese. / 启动游戏，在“模组和 DLC”里启用 **所有历史人物的描述**，游戏语言选英文或简体中文。

Don't enable this copy and the [Steam Workshop]({WORKSHOP}) copy at the same time. / 不要同时启用这份和创意工坊订阅的那份。

SHA-256 `{digest}`
'''


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(notes(sys.argv[1], sys.argv[2]))
