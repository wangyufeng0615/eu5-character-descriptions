"""Place clusters by world region (a rough map orientation) and render light-theme images."""
import json, sys, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib import font_manager as fm
from matplotlib.patches import Circle
import numpy as np

D = sys.argv[1]
L = json.load(open(f'{D}/local.json'))
comps, region, deg = L['comps'], L['region'], L['deg']

# region anchors, x = east, y = north
ANCHOR = {'west_europe': (-6, 1.5), 'east_europe': (3.5, 9.5), 'near_east': (3, -6), 'steppe': (10, 8.5),
          'east_asia': (11.2, -0.5), 'south_asia': (8.5, -10.5), 'africa': (-5, -11.5), 'other': (-13.5, -9)}
GAP = 0.08


def radius(n):
    return 0.135 * math.sqrt(n) + 0.2


def squash(c):
    d = sorted(math.hypot(x, y) for x, y in c['pos'].values())
    ref = d[int(0.8 * (len(d) - 1))] or 1.0
    out = {}
    for v, (x, y) in c['pos'].items():
        r = math.hypot(x, y) / ref
        k = r if r <= 0.85 else 0.85 + 0.15 * math.tanh((r - 0.85) / 0.6)
        out[v] = (x / (r * ref) * k, y / (r * ref) * k) if r else (0.0, 0.0)
    c['pos'] = out


for c in comps:
    if c['n'] > 30:
        squash(c)

placed = []
for c in comps:
    r = radius(c['n'])
    ax_, ay_ = ANCHOR[c['region']]
    ang, rad = 0.0, 0.0
    while True:
        cx, cy = ax_ + rad * math.cos(ang), ay_ + rad * math.sin(ang)
        if all(math.hypot(cx - x, cy - y) > r + rr + GAP for x, y, rr in placed):
            break
        ang += 0.5 / max(1.0, rad)
        rad += 0.02
    placed.append((cx, cy, r))
    c['cx'], c['cy'], c['r'] = cx, cy, r
pos = {v: (c['cx'] + x * c['r'], c['cy'] + y * c['r']) for c in comps for v, (x, y) in c['pos'].items()}

BG = '#f4f6f9'
COLORS = {'west_europe': '#2d6cdf', 'east_europe': '#7c4ddb', 'near_east': '#d9870a', 'steppe': '#d7402a',
          'east_asia': '#0d9b72', 'south_asia': '#c33583', 'africa': '#5f8f1c', 'other': '#7a8391'}
TEXT = {
    'zh': {'title': '8,209 位历史人物，其中 6,859 位有血缘或婚姻相连',
           'sub': '每个点是一位有生平的人物，连线是父母、子女和配偶关系\n聚团按地区大致摆在世界地图的方位上',
           'clusters': ['欧洲联姻大网', '日本：藤原氏、皇室、平氏、源氏', '蒙古黄金家族'],
           'people': '{n:,} 人',
           'legend': {'west_europe': '西欧', 'east_europe': '东欧与巴尔干', 'near_east': '中东与北非', 'steppe': '草原与蒙古',
                      'east_asia': '东亚', 'south_asia': '南亚与东南亚', 'africa': '撒哈拉以南非洲', 'other': '其他'},
           'foot': '所有历史人物的描述 · 欧陆风云5 MOD'},
    'en': {'title': '8,209 historical characters, 6,859 of them linked by blood or marriage',
           'sub': 'Each dot is a character with a biography; lines are parent, child and spouse links\nClusters sit roughly where their region is on the map',
           'clusters': ['The European marriage web', 'Japan: Fujiwara, Taira, Minamoto\nand the imperial house', 'The Mongol Golden Family'],
           'people': '{n:,} people',
           'legend': {'west_europe': 'Western Europe', 'east_europe': 'Eastern Europe & Balkans', 'near_east': 'Middle East & N. Africa',
                      'steppe': 'Steppe & Mongols', 'east_asia': 'East Asia', 'south_asia': 'South & Southeast Asia', 'africa': 'Sub-Saharan Africa', 'other': 'Other'},
           'foot': 'Descriptions for Every Historical Character · EU5 mod'},
}
ZH = fm.FontProperties(fname='/System/Library/Fonts/Hiragino Sans GB.ttc')
EN = fm.FontProperties(family='Helvetica Neue')
ids = list(pos)
xy = np.array([pos[i] for i in ids])
ext = [min(c['cx'] - c['r'] for c in comps), max(c['cx'] + c['r'] for c in comps),
       min(c['cy'] - c['r'] for c in comps), max(c['cy'] + c['r'] for c in comps)]


SPOTS = {'zh': [(0.13, 0.80, 'center'), (0.97, 0.205, 'right'), (0.80, 0.83, 'center')],
         'en': [(0.16, 0.80, 'center'), (0.97, 0.205, 'right'), (0.80, 0.83, 'center')]}
TITLE = {'zh': 27, 'en': 23}
COLS = {'zh': [0.03, 0.27, 0.51, 0.75], 'en': [0.03, 0.27, 0.54, 0.80]}
LEGEND = {'zh': 19, 'en': 16}


def render(lang):
    t = TEXT[lang]; font = ZH if lang == 'zh' else EN
    W, H = 12.0, 12.0
    fig = plt.figure(figsize=(W, H), dpi=180, facecolor=BG)
    box = [0.02, 0.12, 0.96, 0.745]
    ax = fig.add_axes(box, facecolor=BG); ax.set_axis_off()
    bw, bh = box[2] * W, box[3] * H
    scale = max((ext[1] - ext[0]) / bw, (ext[3] - ext[2]) / bh)
    cx, cy = (ext[0] + ext[1]) / 2, (ext[2] + ext[3]) / 2
    ax.set_xlim(cx - bw * scale / 2, cx + bw * scale / 2); ax.set_ylim(cy - bh * scale / 2, cy + bh * scale / 2)

    for c in comps[:3]:  # soft backdrop for the three big clusters
        ax.add_patch(Circle((c['cx'], c['cy']), c['r'] * 1.06, color=COLORS[c['region']], alpha=0.07, lw=0, zorder=0))
    segs = [[pos[a], pos[b]] for a, b, _ in L['edges']]
    cols = [matplotlib.colors.to_rgba(COLORS[region[a]], 0.28) for a, b, _ in L['edges']]
    ax.add_collection(LineCollection(segs, colors=cols, linewidths=0.35, zorder=1))
    s = np.array([deg[i] for i in ids], dtype=float)
    ax.scatter(xy[:, 0], xy[:, 1], s=2.4 + s * 1.3, c=[COLORS[region[i]] for i in ids], alpha=0.9, linewidths=0, zorder=3)

    spots = SPOTS[lang]
    for k, c in enumerate(comps[:3]):
        ax.annotate(f"{t['clusters'][k]}\n{t['people'].format(n=c['n'])}", (c['cx'], c['cy'] + c['r'] * 0.0),
                    xytext=spots[k][:2], textcoords='figure fraction', ha=spots[k][2], va='center',
                    color='#1f2328', fontproperties=font, fontsize=19 if k == 0 else 17, linespacing=1.35, zorder=6,
                    bbox=dict(boxstyle='round,pad=0.45', fc='white', ec=COLORS[c['region']], lw=1.2, alpha=0.95),
                    arrowprops=dict(arrowstyle='-', color='#8c959f', lw=0.9, shrinkA=2, shrinkB=0))

    fig.text(0.03, 0.958, t['title'], color='#1f2328', fontproperties=font, fontsize=TITLE[lang], va='center')
    fig.text(0.03, 0.905, t['sub'], color='#57606a', fontproperties=font, fontsize=15, va='center', linespacing=1.5)
    fig.text(0.97, 0.022, t['foot'], color='#8c959f', fontproperties=font, fontsize=13, va='center', ha='right')
    for k, (key, name) in enumerate(t['legend'].items()):
        x, y = COLS[lang][k % 4], 0.095 - (k // 4) * 0.042
        fig.patches.append(Circle((x + 0.008, y), 0.0085, transform=fig.transFigure, color=COLORS[key], figure=fig))
        fig.text(x + 0.024, y, name, color='#24292f', fontproperties=font, fontsize=LEGEND[lang], va='center')
    out = f'{D}/square.{lang}.png'
    fig.savefig(out, facecolor=BG); plt.close(fig); print(out)


for lang in ('zh', 'en'):
    render(lang)
print('extent', [round(e, 1) for e in ext], 'big', [(c['n'], round(c['cx'], 1), round(c['cy'], 1), round(c['r'], 1)) for c in comps[:3]])
