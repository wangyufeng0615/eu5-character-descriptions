"""把 data/bios.jsonl 构建成 EU5 模组，可选装进本机游戏的模组目录。只用标准库，在 Windows 上运行。

python -B tools\\build.py                 # 构建到 dist\\<mod_dir>
python -B tools\\build.py --install       # 构建并装进 Documents\\Paradox Interactive\\Europa Universalis V\\mod，逐文件核对哈希
python -B tools\\build.py --only-written  # 只放 written，不放一句话的 stub

数据由研究工程导出（研究工程 tools/sync_workshop.sh 在 MacBook 上一步做完导出、拷贝、构建、安装）。
模组目录名、显示名、版本在 project.json；浮窗界面和元数据模板在 mod_template/。

游戏开着时会监视模组文件并自动重载，直接覆盖可能让它读到写了一半的文件（2026-11-02 出过 fopen() failed: 13，
人物侧栏随之失效）。所以安装时先完整写到同一个盘上的临时目录，核对哈希后再整体改名替换。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD_ROOT = Path.home() / 'Documents' / 'Paradox Interactive' / 'Europa Universalis V' / 'mod'
SPECIAL = set('[]$#"\\')


def loc_line(key, text):
    return f' {key}: "{text}"\n'


def load(only_written):
    rows, hidden = [], 0
    with open(ROOT / 'data' / 'bios.jsonl', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            if r['verdict'] not in ('written', 'stub') or (only_written and r['verdict'] != 'written'):
                continue
            if not r.get('displayable'):
                hidden += 1  # 没有固定脚本 ID 的事件人物，游戏里暂时挂不上
                continue
            for lang in ('en', 'zh'):
                t = r[lang]
                if not t.strip() or '\n' in t or SPECIAL & set(t):
                    sys.exit(f'{r["id"]} 的 {lang} 正文为空、换行或含游戏指令字符，先回研究工程修')
            rows.append(r)
    return rows, hidden


def build(cfg, rows, out):
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / 'mod_template', out)
    meta = out / '.metadata' / 'metadata.json'
    m = json.loads(meta.read_text(encoding='utf-8'))
    m['name'], m['version'] = cfg['metadata_name'], cfg['version']
    meta.write_text(json.dumps(m, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    cl = ['cb_character_bio = {', '\ttype = character']
    for r in rows:
        cl += ['\ttext = {', f'\t\tlocalization_key = cb_bio_{r["id"]}', f'\t\ttrigger = {{ this = character:{r["id"]} }}',
               '\t}']
    cl += ['\ttext = {', '\t\tlocalization_key = cb_bio_none', '\t\tfallback = yes', '\t}', '}', '']
    d = out / 'in_game' / 'common' / 'customizable_localization'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'cb_character_bios.txt').write_text('\n'.join(cl), encoding='utf-8-sig', newline='\n')
    for lang, key in (('english', 'en'), ('simp_chinese', 'zh')):
        d = out / 'in_game' / 'localization' / lang
        d.mkdir(parents=True, exist_ok=True)
        with open(d / f'cb_character_bios_l_{lang}.yml', 'w', encoding='utf-8-sig', newline='\n') as fh:
            fh.write(f'l_{lang}:\n')
            fh.write(loc_line('cb_bio_none', ''))
            for r in rows:
                fh.write(loc_line(f'cb_bio_{r["id"]}', r[key].strip()))


def digests(d):
    return {str(p.relative_to(d)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob('*')) if p.is_file()}


def game_running():
    if os.name != 'nt':
        return False
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq eu5.exe'], capture_output=True, text=True, errors='replace')
    return 'eu5.exe' in r.stdout.lower()


def install(cfg, out):
    name = cfg['mod_dir']
    dst, tmp, old = MOD_ROOT / name, MOD_ROOT / f'.{name}.new', MOD_ROOT / f'.{name}.old'
    for p in (tmp, old):
        if p.exists():
            shutil.rmtree(p)
    shutil.copytree(out, tmp)
    if digests(out) != digests(tmp):
        sys.exit('临时目录哈希不一致，没有替换')
    if dst.exists():
        os.replace(dst, old)
    os.replace(tmp, dst)
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
    n = len(digests(dst))
    print(f'已装进 {dst}，{n} 个文件哈希一致。' + ('游戏正在运行，会自动重载，等它读完；不行就冷启动。'
                                                if game_running() else '下次启动游戏生效。'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, help='构建目录，默认 dist\\<mod_dir>')
    ap.add_argument('--only-written', action='store_true')
    ap.add_argument('--install', action='store_true')
    a = ap.parse_args()
    cfg = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
    rows, hidden = load(a.only_written or cfg.get('only_written'))
    out = a.out or ROOT / 'dist' / cfg['mod_dir']
    build(cfg, rows, out)
    print(f'构建 {len(rows)} 人到 {out}' + (f'；{hidden} 人没有固定脚本 ID，游戏里暂时挂不上，未放入' if hidden else ''))
    if a.install:
        install(cfg, out)


if __name__ == '__main__':
    main()
