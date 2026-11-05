"""Render the coverage table shown at the top of the Workshop description (2x PNG, en and zh-CN)."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
S = 4                       # internal supersampling; exported at 2x
W = 620                     # logical width, fits Steam's description column
PAD, ROW_H, HEAD_H, TOTAL_H, LEGEND_H, RADIUS = 18, 52, 34, 60, 50, 8
BG, ROW_LINE, TRACK = '#2a2e33', '#3a3f45', '#44494f'
GREEN, BLUE, MUTED, WHITE = '#2ea043', '#1f6feb', '#9aa4ae', '#ffffff'
BOLD = 'C:/Windows/Fonts/msyhbd.ttc'
REG = 'C:/Windows/Fonts/msyh.ttc'
COL_COUNT_R, BAR_X, BAR_W, PCT_R = 365, 385, 128, W - PAD   # right edge of count column, bar, percent

TEXT = {
    'en': {'head': ('Historical characters', 'With biography', 'Coverage'),
           'rulers': ('Rulers', 'Kings, emperors, sultans and regents'),
           'living': ('Others alive in 1337', 'Consorts, children, cadet branches'),
           'ancestors': ('Ancestors', 'Family trees, back to Charlemagne'),
           'events': ('Event figures', 'Newton, Zheng He, Napoleon…'),
           'total': ('All historical characters', None),
           'legend': ('Shown in game', 'Written, attaching in a coming update', 'Too little known to identify'),
           'foot': 'Excludes {n} fictional or placeholder characters'},
    'zh-CN': {'head': ('人物类别', '有生平 / 总数', '覆盖率'),
              'rulers': ('君主与统治者', '国王、皇帝、苏丹、摄政'),
              'living': ('1337 年在世的其他人物', '配偶、子女、旁支'),
              'ancestors': ('先辈', '家族树里的祖先，远至查理曼'),
              'events': ('事件人物', '牛顿、郑和、拿破仑……'),
              'total': ('全部历史人物', None),
              'legend': ('游戏中显示', '已写好，后续版本接入', '资料太少，无法确认身份'),
              'foot': '不含 {n} 位虚构或占位人物'},
}


def font(path, size):
    return ImageFont.truetype(path, round(size * S))


def text(draw, xy, s, f, fill, anchor='ls'):
    draw.text((xy[0] * S, xy[1] * S), s, font=f, fill=fill, anchor=anchor)


def bar(draw, x, y, w, h, shown, pending, total):
    r = h / 2
    draw.rounded_rectangle((x * S, y * S, (x + w) * S, (y + h) * S), r * S, fill=TRACK)
    gx = x + w * (shown + pending) / total
    if pending:
        draw.rounded_rectangle((x * S, y * S, gx * S, (y + h) * S), r * S, fill=BLUE)
    sx = x + w * shown / total
    draw.rounded_rectangle((x * S, y * S, sx * S, (y + h) * S), r * S, fill=GREEN)
    if pending:   # square off the green end where it meets blue
        draw.rectangle(((sx - r) * S, y * S, sx * S, (y + h) * S), fill=GREEN)


def render(lang, data):
    t = TEXT[lang]
    rows = data['rows']
    H = PAD + HEAD_H + ROW_H * (len(rows) - 1) + TOTAL_H + LEGEND_H + PAD // 2
    img = Image.new('RGBA', (W * S, H * S))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W * S - 1, H * S - 1), RADIUS * S, fill=BG)
    f_head, f_name, f_sub = font(REG, 12), font(BOLD, 16), font(REG, 12)
    f_num, f_pct, f_pct_big, f_small = font(BOLD, 15), font(BOLD, 17), font(BOLD, 24), font(BOLD, 12)
    y = PAD
    h1, h2, h3 = t['head']
    text(d, (PAD, y + 18), h1, f_head, MUTED)
    text(d, (COL_COUNT_R, y + 18), h2, f_head, MUTED, 'rs')
    text(d, (PCT_R, y + 18), h3, f_head, MUTED, 'rs')
    y += HEAD_H
    for row in rows:
        total = row['key'] == 'total'
        rh = TOTAL_H if total else ROW_H
        d.line((PAD * S, y * S, (W - PAD) * S, y * S), fill=ROW_LINE if not total else MUTED, width=S * (2 if total else 1))
        name, sub = t[row['key']]
        mid = y + rh / 2
        if sub:
            text(d, (PAD, mid - 3), name, f_name, WHITE)
            text(d, (PAD, mid + 15), sub, f_sub, MUTED)
        else:
            text(d, (PAD, mid + 7), name, font(BOLD, 18), WHITE)
        text(d, (COL_COUNT_R, mid + 6), f"{row['shown']:,} / {row['historical']:,}", f_num, WHITE, 'rs')
        bar(d, BAR_X, mid - (6 if total else 5), BAR_W, 12 if total else 10, row['shown'], row['pending'], row['historical'])
        pct = f"{100 * row['shown'] / row['historical']:.1f}%"
        if row['pending']:
            text(d, (PCT_R, mid + 1), pct, f_pct_big if total else f_pct, GREEN, 'rs')
            text(d, (PCT_R, mid + 17), f"+{100 * row['pending'] / row['historical']:.1f}%", f_small, BLUE, 'rs')
        else:
            text(d, (PCT_R, mid + 8), pct, f_pct_big if total else f_pct, GREEN, 'rs')
        y += rh
    # legend
    y += 18
    x = PAD
    f_leg = font(REG, 12)
    for label, color in zip(t['legend'], (GREEN, BLUE, TRACK)):
        d.rounded_rectangle((x * S, (y - 9) * S, (x + 10) * S, (y + 1) * S), 2 * S, fill=color)
        text(d, (x + 15, y), label, f_leg, MUTED)
        x += 15 + d.textlength(label, font=f_leg) / S + 18
    text(d, (PAD, y + 20), t['foot'].format(n=data['excluded_non_historical']), f_leg, MUTED)
    out = ROOT / f'coverage.{lang}.png'
    img.resize((W * 2, H * 2), Image.Resampling.LANCZOS).save(out, optimize=True)
    return out


if __name__ == '__main__':
    data = json.loads((ROOT / 'coverage.json').read_text(encoding='utf-8'))
    for lang in TEXT:
        p = render(lang, data)
        print(p.name, Image.open(p).size, hashlib.sha256(p.read_bytes()).hexdigest()[:16])
