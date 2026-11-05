"""把 data/bios.jsonl 构建成 EU5 模组。只用标准库（Python 3.10+），不上传。

python -B tools/build.py --check                      # 只检查数据和配置
python -B tools/build.py --output dist/<新目录>        # 构建模组文件夹、ZIP 和构建回执（目录必须是新的）
python -B tools/build.py --verify dist/<目录>          # 按当前源文件重算，核对已构建的文件夹、ZIP 和回执
python -B tools/build.py --install [--only-written]   # 开发用：构建到 dist/dev 并装进本机 EU5 模组目录
python -B tools/build.py --check --game-root "<EU5 安装目录>"   # 另外核对原版人物浮窗有没有随游戏更新变化

数据由研究工程导出（研究工程 tools/sync_workshop.sh 在 MacBook 上一步做完导出、拷贝、构建、安装）。
模组名、版本等在 project.json；改写过的人物浮窗模板在 mod_template/。

游戏开着时会监视模组文件并自动重载，直接覆盖可能让它读到写了一半的文件（2026-11-02 出过 fopen() failed: 13，
人物侧栏随之失效）。所以安装时先完整写到同一个盘上的临时目录，核对哈希后再整体改名替换。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
MOD_ROOT = Path(os.environ.get('USERPROFILE') or Path.home()) / 'Documents' / 'Paradox Interactive' / 'Europa Universalis V' / 'mod'
LICENSE_FILES = ('LICENSE', 'LICENSES/MIT.txt', 'LICENSES/CC-BY-SA-4.0.txt', 'CREDITS.md')
PLAYER_DOCS = {'README.md': 'workshop/player-readme.en.md', 'README.zh-CN.md': 'workshop/player-readme.zh-CN.md'}
GUI = 'in_game/gui/zz_cb_character_tooltips.gui'
# 游戏按 32 位哈希查本地化键，个别键会和原版撞车（error.log 报 Localization key hash collision），撞了就在这里换名。
KEY_RENAMES = {'dan_sorensen': 'cb_bio_dan_sorensen_b'}
SPECIAL = set('[]$#"\\')
VERSION_RE = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+')


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def project_file(root, rel):
    p = (root / rel).resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file():
        raise ValueError(f'缺少文件或路径在工程外：{rel}')
    return p


def load_config(root):
    cfg = json.loads((root / 'project.json').read_text(encoding='utf-8'))
    if cfg.get('game_id') != 'eu5' or cfg.get('steam_app_id') != 3450310:
        raise ValueError('project.json 的 game_id / steam_app_id 不是 EU5')
    if not re.fullmatch(r'[a-z0-9_]{3,40}', cfg.get('mod_id', '')):
        raise ValueError('mod_id 只能用小写字母、数字和下划线')
    if not VERSION_RE.fullmatch(cfg.get('version', '')):
        raise ValueError('version 必须是 x.y.z')
    for k in ('name', 'name_zh'):
        v = cfg.get(k)
        if not isinstance(v, str) or not 3 <= len(v) <= 60 or len(v.encode('utf-8')) > 128:
            raise ValueError(f'{k} 不合规')
    if not cfg.get('short_description', '').strip():
        raise ValueError('缺 short_description')
    pid = cfg.get('publishedfileid')
    if pid is not None and (type(pid) is not int or pid <= 0):
        raise ValueError('publishedfileid 要么是 null（还没建工坊条目），要么是正整数')
    if cfg.get('licenses') != {'tools': 'MIT', 'descriptions': 'CC-BY-SA-4.0'}:
        raise ValueError('licenses 和 LICENSE 文件不一致')
    return cfg


def load_rows(root, only_written=False):
    """返回 (要放进模组的人, 没有固定脚本 ID 暂时挂不上的人数)。"""
    rows, hidden, seen = [], 0, set()
    rules = load_match_rules(root)
    with open(root / 'data' / 'bios.jsonl', encoding='utf-8') as fh:
        for n, line in enumerate(fh, 1):
            r = json.loads(line)
            cid = r.get('id')
            if not isinstance(cid, str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.\-]*', cid) or cid in seen:
                raise ValueError(f'第 {n} 行：人物 id 不合规或重复：{cid!r}')
            seen.add(cid)
            if r.get('verdict') not in ('written', 'stub'):
                raise ValueError(f'{cid} 的 verdict 不能发布：{r.get("verdict")}')
            if only_written and r['verdict'] != 'written':
                continue
            if not r.get('displayable'):
                if cid not in rules:
                    hidden += 1
                    continue
                r['_match'] = rules[cid]
            for lang in ('en', 'zh'):
                t = r.get(lang)
                if not isinstance(t, str) or not t.strip() or '\n' in t or SPECIAL & set(t) \
                        or any(ord(c) < 32 for c in t):
                    raise ValueError(f'{cid} 的 {lang} 正文为空、换行或含游戏指令字符，先回研究工程修')
            src = r.get('sources')
            if not isinstance(src, list) or not src:
                raise ValueError(f'{cid} 没有资料来源（署名要用）；研究工程重新导出')
            for u in src:
                p = urlsplit(u)
                if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
                    raise ValueError(f'{cid} 的来源网址不合规：{u}')
            rows.append(r)
    # 按属性认人的条目排在最后：可定制本地化取第一条成立的，带固定 ID 的人优先用自己的介绍
    return sorted(rows, key=lambda r: ('_match' in r, r['id'])), hidden


def load_match_rules(root):
    """data/match_rules.json：没有固定脚本 ID 的事件人物，按名字键、出生地等属性认人的条件。"""
    p = root / 'data' / 'match_rules.json'
    if not p.exists():
        return {}
    rules = {k: v for k, v in json.loads(p.read_text(encoding='utf-8')).items() if not k.startswith('_')}
    for cid, conds in rules.items():
        if not isinstance(conds, list) or not conds or not all(
                isinstance(c, str) and c.strip() and re.fullmatch(r'[A-Za-z0-9_:.?=<>{} \-]+', c) for c in conds):
            raise ValueError(f'match_rules.json 里 {cid} 的条件不合规')
    return rules


def trigger_of(r):
    """先判断人物是否存在：事件人物在事件触发前不存在，直接比较 character:ID 会每次悬停都报错。"""
    if '_match' in r:
        return '{ ' + ' '.join(r['_match']) + ' }'
    return f'{{ exists = character:{r["id"]} this = character:{r["id"]} }}'


def check_game(cfg, game_root):
    """游戏更新后，原版人物浮窗变了就要把改动重新合并进 mod_template 里的模板。"""
    g = Path(game_root) / 'game' / cfg['vanilla_tooltip']
    out = {'tooltip_unchanged': sha256(g.read_bytes()) == cfg['vanilla_tooltip_sha256']}
    m = Path(game_root).parents[1] / 'appmanifest_3450310.acf'
    if m.exists():
        b = re.search(r'"buildid"\s+"(\d+)"', m.read_text(encoding='utf-8'))
        out.update(game_build=int(b.group(1)) if b else None, checked_build=cfg.get('game_build_checked'))
    return out


def loc_key(r):
    return KEY_RENAMES.get(r['id'], f'cb_bio_{r["id"]}')


def loc_line(key, text):
    return f' {key}: "{text}"\n'


def payload(root, cfg, rows):
    """模组里每个文件的内容：{相对路径: bytes}。构建和核对都用它，保证两边一致。"""
    files = {}
    meta = {'name': cfg['name'], 'version': cfg['version'], 'game_id': 'eu5',
            'supported_game_version': cfg['supported_game_version'], 'short_description': cfg['short_description'],
            'tags': cfg['tags'], 'id': cfg['mod_id'], 'relationships': [], 'game_custom_data': {}}
    files['.metadata/metadata.json'] = (json.dumps(meta, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    files['.metadata/thumbnail.png'] = project_file(root, cfg['thumbnail_file']).read_bytes()
    files[GUI] = project_file(root, 'mod_template/' + GUI).read_bytes()
    cl = ['cb_character_bio = {', '\ttype = character']
    for r in rows:
        cl += ['\ttext = {', f'\t\tlocalization_key = {loc_key(r)}', f'\t\ttrigger = {trigger_of(r)}',
               '\t}']
    cl += ['\ttext = {', '\t\tlocalization_key = cb_bio_none', '\t\tfallback = yes', '\t}', '}', '']
    files['in_game/common/customizable_localization/cb_character_bios.txt'] = '\n'.join(cl).encode('utf-8-sig')
    for lang, key in (('english', 'en'), ('simp_chinese', 'zh')):
        body = f'l_{lang}:\n' + loc_line('cb_bio_none', '') + ''.join(loc_line(loc_key(r), r[key].strip())
                                                                      for r in rows)
        files[f'in_game/localization/{lang}/cb_character_bios_l_{lang}.yml'] = body.encode('utf-8-sig')
    for name in LICENSE_FILES:
        files[name] = project_file(root, name).read_bytes()
    for name, src in PLAYER_DOCS.items():
        files[name] = project_file(root, src).read_bytes()
    files['sources/sources.jsonl'] = ''.join(json.dumps({'id': r['id'], 'sources': r['sources']}, ensure_ascii=False)
                                             + '\n' for r in rows).encode('utf-8')
    if files['.metadata/thumbnail.png'][:8] != b'\x89PNG\r\n\x1a\n' or len(files['.metadata/thumbnail.png']) >= 1_000_000:
        raise ValueError('thumbnail.png 不是 PNG 或超过 1 MB（工坊上限）')
    for lang in ('english', 'simp_chinese'):
        n = files[f'in_game/localization/{lang}/cb_character_bios_l_{lang}.yml'].decode('utf-8-sig').count('\n cb_bio_')
        if n != len(rows) + 1:
            raise ValueError(f'{lang} 本地化条数不对：{n - 1}/{len(rows)}')
    return files


# ───────────────────────────── 构建、核对、安装

def page_counts(root, n):
    """工坊文案、更新说明和玩家说明里写的数量（如 [b]3,272[/b]、"3,272 个"）要和这次构建的条数一致，不一致的文件列出来。
    链接到其他工坊条目的行（"我的其他 MOD"）写的是那些模组的数量，不算。"""
    bad = []
    for rel in ('workshop/description.en.txt', 'workshop/description.zh-CN.txt', 'workshop/changenotes.en.txt',
                'workshop/changenotes.zh-CN.txt', 'workshop/player-readme.en.md', 'workshop/player-readme.zh-CN.md'):
        p = root / rel
        if p.exists():
            text = '\n'.join(l for l in p.read_text(encoding='utf-8').splitlines() if 'sharedfiles/filedetails' not in l)
            nums = {int(x.replace(',', '')) for x in re.findall(r'\b\d{1,3}(?:,\d{3})+\b', text)}
            if nums and nums != {n}:
                bad.append(f'{rel}: {sorted(nums)}')
    return bad


def write_tree(files, out):
    for name, b in files.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)


def tree_digests(d):
    return {p.relative_to(d).as_posix(): sha256(p.read_bytes()) for p in sorted(d.rglob('*')) if p.is_file()}


def mod_folder_name(cfg):
    return cfg['mod_id']


def zip_name(cfg):
    return f'{cfg["mod_id"]}-{cfg["version"]}.zip'


def _rows(root, cfg):
    return load_rows(root, cfg.get('only_written'))


def build(root, output):
    root, output = root.resolve(), output.resolve()
    cfg = load_config(root)
    rows, hidden = _rows(root, cfg)
    if output.exists():
        raise FileExistsError(f'输出目录已存在，换一个新目录：{output}')
    files = payload(root, cfg, rows)
    write_tree(files, output / cfg['mod_id'])
    archive = output / zip_name(cfg)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(f'{cfg["mod_id"]}/{name}', date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, files[name], compresslevel=9)
    receipt = {'name': cfg['name'], 'mod_id': cfg['mod_id'], 'version': cfg['version'],
               'publishedfileid': cfg.get('publishedfileid'), 'characters': len(rows),
               'verdicts': dict(Counter(r['verdict'] for r in rows)), 'not_attachable': hidden,
               'licenses': cfg['licenses'],
               'built_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
               'files': {k: sha256(v) for k, v in sorted(files.items())},
               'bytes': sum(len(v) for v in files.values()), 'archive_sha256': sha256(archive.read_bytes())}
    (output / 'build_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    verify(root, output)
    return receipt


def verify(root, output):
    root, output = root.resolve(), output.resolve()
    cfg = load_config(root)
    rows, _ = _rows(root, cfg)
    want = {k: sha256(v) for k, v in sorted(payload(root, cfg, rows).items())}
    have = tree_digests(output / cfg['mod_id'])
    if have != want:
        raise ValueError(f'已构建的文件和当前源文件算出的不一致：{sorted(set(have.items()) ^ set(want.items()))[:5]}')
    receipt = json.loads((output / 'build_receipt.json').read_text(encoding='utf-8'))
    if receipt['files'] != want or receipt['version'] != cfg['version'] or receipt['characters'] != len(rows):
        raise ValueError('构建回执和当前源文件不一致')
    archive = output / zip_name(cfg)
    if sha256(archive.read_bytes()) != receipt['archive_sha256']:
        raise ValueError('ZIP 哈希和回执不一致')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or sorted(z.namelist()) != sorted(f'{cfg["mod_id"]}/{k}' for k in want):
            raise ValueError('ZIP 文件清单或校验不对')
        for k, h in want.items():
            if sha256(z.read(f'{cfg["mod_id"]}/{k}')) != h:
                raise ValueError(f'ZIP 里 {k} 和回执不一致')
    return receipt


def game_running():
    if os.name != 'nt':
        return False
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq eu5.exe'], capture_output=True, text=True, errors='replace')
    return 'eu5.exe' in r.stdout.lower()


def install(cfg, src, mod_root=MOD_ROOT):
    """装进 EU5 用户模组目录：先写临时目录、核对哈希，再整体改名替换；只替换本模组自己的旧副本。"""
    name = cfg['mod_id']
    dst, tmp, old = mod_root / name, mod_root / f'.{name}.new', mod_root / f'.{name}.old'
    if dst.exists():
        try:
            mine = json.loads((dst / '.metadata' / 'metadata.json').read_text(encoding='utf-8-sig')).get('id') == name
        except (OSError, ValueError):
            mine = False
        if not mine:
            raise ValueError(f'{dst} 已存在但不是本模组，不替换')
    for p in (tmp, old):
        if p.exists():
            shutil.rmtree(p)
    shutil.copytree(src, tmp)
    if tree_digests(src) != tree_digests(tmp):
        raise RuntimeError('临时目录哈希不一致，没有替换')
    if dst.exists():
        os.replace(dst, old)
    os.replace(tmp, dst)
    shutil.rmtree(old, ignore_errors=True)
    n = len(tree_digests(dst))
    print(f'已装进 {dst}，{n} 个文件哈希一致。' + ('游戏正在运行，会自动重载，等它读完；不行就冷启动。'
                                                if game_running() else '下次启动游戏生效。'))
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='只检查数据和配置')
    mode.add_argument('--verify', type=Path, help='核对已构建的目录')
    mode.add_argument('--install', action='store_true', help='开发用：构建到 dist/dev 并装进本机')
    ap.add_argument('--output', type=Path, help='构建目录（必须是新的）')
    ap.add_argument('--only-written', action='store_true', help='和 --install 一起用：只放 written')
    ap.add_argument('--game-root', type=Path, help='EU5 安装目录，和 --check 一起用')
    a = ap.parse_args()
    cfg = load_config(ROOT)
    if a.only_written:
        if not a.install:
            ap.error('--only-written 只用于 --install；正式构建改 project.json 的 only_written')
        cfg['only_written'] = True
    if a.check:
        rows, hidden = _rows(ROOT, cfg)
        payload(ROOT, cfg, rows)
        out = {'ok': True, 'version': cfg['version'], 'characters': len(rows),
               'verdicts': dict(Counter(r['verdict'] for r in rows)), 'not_attachable': hidden}
        out['page_count_mismatch'] = page_counts(ROOT, len(rows))
        if a.game_root:
            out['game'] = check_game(cfg, a.game_root)
        print(json.dumps(out, ensure_ascii=False))
    elif a.verify:
        r = verify(ROOT, a.verify)
        print(json.dumps({'verified': True, 'version': r['version'], 'files': len(r['files']),
                          'archive_sha256': r['archive_sha256']}, ensure_ascii=False))
    elif a.install:
        rows, hidden = _rows(ROOT, cfg)
        out = ROOT / 'dist' / 'dev' / cfg['mod_id']
        if out.exists():
            shutil.rmtree(out)
        write_tree(payload(ROOT, cfg, rows), out)
        print(f'构建 {len(rows)} 人到 {out}' + (f'；{hidden} 人没有固定脚本 ID，游戏里暂时挂不上，未放入' if hidden else ''))
        install(cfg, out)
    else:
        if not a.output:
            ap.error('正式构建要给 --output dist/<新目录>')
        r = build(ROOT, a.output)
        print(json.dumps({k: r[k] for k in ('version', 'characters', 'verdicts', 'not_attachable', 'bytes',
                                            'archive_sha256')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
