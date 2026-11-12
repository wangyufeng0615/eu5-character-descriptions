"""python -B -m unittest discover -s tests -v"""
import json
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'tools'))
import build  # noqa: E402
import release  # noqa: E402


def tiny_png():
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\xff\xff')) + chunk(b'IEND', b''))


SRC = ['https://en.wikipedia.org/wiki/Edward_III_of_England']
ROWS = [
    {'id': 'eng_edward_iii', 'verdict': 'written', 'en': 'Edward III was king of England.', 'zh': '爱德华三世是英格兰国王。',
     'displayable': True, 'sources': SRC},
    {'id': 'fra_minor', 'verdict': 'stub', 'en': 'A minor noble.', 'zh': '一位小贵族。', 'displayable': True, 'sources': SRC},
    {'id': 'event_only', 'verdict': 'written', 'en': 'Event person.', 'zh': '事件人物。', 'displayable': False, 'sources': SRC},
]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / 'repo'
        for rel in ('project.json', 'LICENSE', 'CREDITS.md', 'LICENSES', 'mod_template', 'workshop/player-readme.en.md',
                    'workshop/player-readme.zh-CN.md'):
            src, dst = REPO / rel, self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if src.is_dir() else shutil.copyfile)(src, dst)
        cfg = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        (self.root / cfg['thumbnail_file']).parent.mkdir(parents=True, exist_ok=True)
        (self.root / cfg['thumbnail_file']).write_bytes(tiny_png())
        self.write_rows(ROWS)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_rows(self, rows):
        (self.root / 'data').mkdir(exist_ok=True)
        (self.root / 'data' / 'bios.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                                                      encoding='utf-8')


class TestBuild(Fixture):
    def test_build_verify_and_contents(self):
        out = self.tmp / 'dist' / 'r'
        r = build.build(self.root, out)
        self.assertEqual((r['characters'], r['not_attachable']), (2, 1))
        cfg = build.load_config(self.root)
        mod = out / cfg['mod_id']
        meta = json.loads((mod / '.metadata' / 'metadata.json').read_text(encoding='utf-8'))
        self.assertEqual((meta['id'], meta['name'], meta['version']), (cfg['mod_id'], cfg['name'], cfg['version']))
        for name in ('.metadata/thumbnail.png', build.GUI, 'sources/sources.jsonl', 'LICENSE', 'README.md',
                     'in_game/localization/simp_chinese/cb_character_bios_l_simp_chinese.yml'):
            self.assertTrue((mod / name).is_file(), name)
        cl = (mod / 'in_game/common/customizable_localization/cb_character_bios.txt').read_text(encoding='utf-8-sig')
        self.assertIn('exists = character:eng_edward_iii this = character:eng_edward_iii', cl)
        self.assertNotIn('event_only', cl)
        build.verify(self.root, out)
        with self.assertRaises(FileExistsError):
            build.build(self.root, out)

    def test_match_rules_attach_event_person_last(self):
        (self.root / 'data' / 'match_rules.json').write_text(json.dumps(
            {'_说明': 'x', 'event_only': ['character_name = name_john', 'birth_location ?= location:calw']}), encoding='utf-8')
        out = self.tmp / 'dist' / 'm'
        r = build.build(self.root, out)
        self.assertEqual((r['characters'], r['not_attachable']), (3, 0))
        cl = (out / build.load_config(self.root)['mod_id'] / 'in_game/common/customizable_localization/cb_character_bios.txt'
              ).read_text(encoding='utf-8-sig')
        self.assertIn('trigger = { character_name = name_john birth_location ?= location:calw }', cl)
        self.assertLess(cl.index('cb_bio_fra_minor'), cl.index('cb_bio_event_only'))
        (self.root / 'data' / 'match_rules.json').write_text(json.dumps({'event_only': ['x = "y"']}), encoding='utf-8')
        with self.assertRaises(ValueError):
            build.build(self.root, self.tmp / 'dist' / 'm2')

    def test_verify_detects_tampering(self):
        out = self.tmp / 'dist' / 'r'
        build.build(self.root, out)
        p = out / build.load_config(self.root)['mod_id'] / build.GUI
        p.write_bytes(p.read_bytes() + b'#')
        with self.assertRaises(ValueError):
            build.verify(self.root, out)

    def test_paragraphs_become_loc_newlines(self):
        self.write_rows([{**ROWS[0], 'en': 'First part.\n\nSecond part.', 'zh': '第一段。\n\n第二段。'}])
        rows, _ = build.load_rows(self.root)
        files = build.payload(self.root, build.load_config(self.root), rows)
        en = files['in_game/localization/english/cb_character_bios_l_english.yml'].decode('utf-8-sig')
        zh = files['in_game/localization/simp_chinese/cb_character_bios_l_simp_chinese.yml'].decode('utf-8-sig')
        self.assertIn(' cb_bio_eng_edward_iii: "First part.\\n\\nSecond part."\n', en)
        self.assertIn(' cb_bio_eng_edward_iii: "第一段。\\n\\n第二段。"\n', zh)

    def test_only_written(self):
        rows, hidden = build.load_rows(self.root, only_written=True)
        self.assertEqual([r['id'] for r in rows], ['eng_edward_iii'])

    def test_rejects_bad_rows(self):
        for bad in ({**ROWS[0], 'sources': []}, {**ROWS[0], 'en': 'has [brackets]'}, {**ROWS[0], 'zh': '两行\n文字'},
                    {**ROWS[0], 'verdict': 'unidentified'}, {**ROWS[0], 'en': 'Three\n\n\nnewlines.'},
                    {**ROWS[0], 'en': 'Two\n\nparagraphs.'}):
            self.write_rows([bad])
            with self.assertRaises(ValueError):
                build.load_rows(self.root)

    def test_links_use_rich_text_only_when_on(self):
        en = 'Son of Edward II, king of England.'
        zh = '爱德华二世之子，英格兰国王。'
        en_rich = ("Son of #TOOLTIP:CHARACTER,[GetCharacter('eng_edward_ii').GetID],X #L Edward II#!#!, king of "
                   "[GetCountry('ENG').GetName].")
        zh_rich = "#TOOLTIP:CHARACTER,[GetCharacter('eng_edward_ii').GetID],X #L 爱德华二世#!#!之子，[ShowLocationName('england')]国王。"
        self.write_rows([{**ROWS[0], 'en': en, 'zh': zh, 'en_rich': en_rich, 'zh_rich': zh_rich}])
        cfg = build.load_config(self.root)
        rows, _ = build.load_rows(self.root)
        self.assertEqual(rows[0]['_text'], {'en': en, 'zh': zh})
        rows, _ = build.load_rows(self.root, links=True)
        en_loc = build.payload(self.root, cfg, rows)['in_game/localization/english/cb_character_bios_l_english.yml']
        self.assertIn(en_rich.encode('utf-8'), en_loc)
        # 链接改了正文、链接写法不认识、开了链接却没有 *_rich，都要拦下
        for bad in ({'en_rich': en_rich.replace('Edward II#!', 'Edward the Second#!')},
                    {'en_rich': en_rich.replace(', king', ' king')},
                    {'en_rich': en_rich.replace('GetName', 'GetLongName')},
                    {'zh_rich': zh_rich.replace("[ShowLocationName('england')]", '[ShowLocationName("england")]')},
                    {'zh_rich': None}):
            self.write_rows([{**ROWS[0], 'en': en, 'zh': zh, 'en_rich': en_rich, 'zh_rich': zh_rich, **bad}])
            with self.assertRaises(ValueError, msg=bad):
                build.load_rows(self.root, links=True)

    def test_install_replaces_only_own_copy(self):
        out = self.tmp / 'dist' / 'r'
        build.build(self.root, out)
        cfg = build.load_config(self.root)
        mods = self.tmp / 'mod'
        build.install(cfg, out / cfg['mod_id'], mods)
        build.install(cfg, out / cfg['mod_id'], mods)
        (mods / cfg['mod_id'] / '.metadata' / 'metadata.json').write_text('{"id": "other"}', encoding='utf-8')
        with self.assertRaises(ValueError):
            build.install(cfg, out / cfg['mod_id'], mods)


class TestRelease(unittest.TestCase):
    def test_versions_and_changelog(self):
        self.assertEqual(release.parse_version('1.2.3'), (1, 2, 3))
        with self.assertRaises(ValueError):
            release.parse_version('1.2')
        cl = release.add_changelog_entry('# Changelog\n\n', '1.0.0', '2026-11-03', ['First.'])
        self.assertIn('## 1.0.0 — 2026-11-03', cl)


if __name__ == '__main__':
    unittest.main()
