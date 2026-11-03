"""工坊封面：Codex 生图模型画的母版（workshop/assets/cover-master.*.png，提示词在 cover-prompt.*.txt），
导出 cover.jpg、cover.zh-CN.jpg（1254，JPEG 90）和模组缩略图 thumbnail.png（512）。封面是宣传图，不是游戏截图。

uv run --with pillow python tools/cover.py derive
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'workshop' / 'assets'


def derive():
    files = {}
    for lang, jpg in (('en', 'cover.jpg'), ('zh-CN', 'cover.zh-CN.jpg')):
        m = Image.open(ASSETS / f'cover-master.{lang}.png').convert('RGB')
        side = min(m.size)
        m = m.crop(((m.width - side) // 2, (m.height - side) // 2, (m.width + side) // 2, (m.height + side) // 2))
        m.resize((1254, 1254), Image.LANCZOS).save(ASSETS / jpg, quality=90)
        files[jpg] = f'cover-master.{lang}.png'
        if lang == 'en':
            m.resize((512, 512), Image.LANCZOS).save(ASSETS / 'thumbnail.png', optimize=True)
            files['thumbnail.png'] = 'cover-master.en.png'
    for f in files:
        assert (ASSETS / f).stat().st_size < 1_000_000, f'{f} 超过工坊 1 MB 上限'
    sha = {f: hashlib.sha256((ASSETS / f).read_bytes()).hexdigest()
           for f in sorted(set(files) | set(files.values()) | {'map-reference.png'}) if (ASSETS / f).exists()}
    print(json.dumps(sha, indent=1))
    return sha


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['derive'])
    ap.parse_args()
    derive()


if __name__ == '__main__':
    main()
