"""Per-component layouts, normalised to the unit disk, cached in local.json."""
import json, sys, collections, math
import networkx as nx

RESEARCH, BIOS, OUT = sys.argv[1:4]
rows = {json.loads(l)['id']: json.loads(l) for l in open(f'{RESEARCH}/data/characters.jsonl')}
nodes = {json.loads(l)['id'] for l in open(BIOS)}
region_of_tag = json.load(open(f'{OUT}/tag_region.json'))
MACRO = {
    'west_europe': ['france', 'british_isles', 'iberia', 'italy', 'lowlands', 'north_germany', 'south_germany', '_scandinavia'],
    'east_europe': ['poland', 'baltics', 'carpathia', 'balkans', 'russia'],
    'near_east': ['anatolia', 'caucasus', 'arabia', 'crescent', 'egypt', 'maghreb', 'persia'],
    'steppe': ['steppes', 'siberia'],
    'east_asia': ['east_asia'],
    'south_asia': ['india', 'bengal', 'south_east_asia', 'indonesia'],
    'africa': ['west_africa', 'east_africa', 'horn_of_africa', 'kongo', 'south_africa'],
}
macro_of = {r: m for m, rs in MACRO.items() for r in rs}


def ids(v):
    if not v:
        return []
    return [s.split(' ')[0] for s in (v if isinstance(v, list) else [v])]


def region(i):
    g = rows[i].get('game', {})
    if (g.get('dynasty') or '').startswith('Borjigin'):
        return 'steppe'  # the Golden Family reads as one people wherever they ruled
    return macro_of.get(region_of_tag.get((g.get('country') or '').split(' ')[0], ''), 'other')


G = nx.Graph()
for i in nodes:
    G.add_node(i, region=region(i))
for i in nodes:
    g = rows[i].get('game', {})
    for k in ('father', 'mother', 'children', 'spouse'):
        for j in ids(g.get(k)):
            if j in nodes and j != i:
                G.add_edge(i, j, kind='spouse' if k == 'spouse' else 'parent')

H = G.subgraph([n for n in G if G.degree(n) > 0])
comps = []
for c in sorted(nx.connected_components(H), key=len, reverse=True):
    sub = H.subgraph(c)
    n = len(c)
    if n > 2:
        p = nx.spring_layout(sub, k=2.2 / math.sqrt(n), iterations=400 if n > 500 else 200, seed=11)
    else:
        p = {v: (k * 1.0 - 0.5, 0.0) for k, v in enumerate(sorted(c))}
    xs = [q[0] for q in p.values()]; ys = [q[1] for q in p.values()]
    mx, my = sum(xs) / n, sum(ys) / n
    span = max(max(math.hypot(x - mx, y - my) for x, y in p.values()), 1e-6)
    comps.append({'n': n, 'region': collections.Counter(G.nodes[v]['region'] for v in c).most_common(1)[0][0],
                  'pos': {v: ((x - mx) / span, (y - my) / span) for v, (x, y) in p.items()}})

json.dump({'comps': comps, 'region': {v: G.nodes[v]['region'] for v in H},
           'deg': {v: H.degree(v) for v in H},
           'edges': [(a, b, d['kind']) for a, b, d in H.edges(data=True)],
           'total': G.number_of_nodes(), 'isolated': G.number_of_nodes() - H.number_of_nodes()},
          open(f'{OUT}/local.json', 'w'))
print(len(comps), 'components', collections.Counter(c['region'] for c in comps))
