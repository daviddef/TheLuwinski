#!/usr/bin/env python3
"""Build atlas-data.json (the Record Atlas slice a tree page needs) for the places a tree actually uses.

    build_atlas_data.py --atlas "<Record Atlas repo>" --tree build/tree.json --place-map build/place_map.json \
        --out build/atlas-data.json

Reads only Atlas files that exist in the repo (data/*.json, site/public/*). Nothing is fetched. The output
carries: simplified land outlines, regime colours, regional eras (who ruled each place in each year), mortality
events that cover each place, the flag in force over each place per year (as SVG), and the collections the
Atlas lists for each place. Every number is derived, so re-running it is how the page stays current.
"""
import argparse, json, os, re, sys

RISO = {'habsburg': 'AT', 'galicia': 'AT', 'napo': 'FR', 'italy': 'IT', 'venice': 'IT', 'twosicilies': 'IT', 'yugo': 'RS',
        'croatia': 'HR', 'uruguay': 'UY', 'spain': 'ES', 'portugal': 'PT', 'brazil': 'BR', 'argentina': 'AR', 'britain': 'GB',
        'england': 'GB', 'uk': 'GB', 'ireland': 'IE', 'dutch': 'NL', 'southafrica': 'ZA', 'australia': 'AU', 'slovenia': 'SI',
        'poland': 'PL', 'russia': 'RU', 'german': 'DE', 'prussia': 'DE', 'france': 'FR', 'germany': 'DE', 'netherlands': 'NL',
        'sweden': 'SE', 'norway': 'NO', 'denmark': 'DK', 'finland': 'FI', 'belgium': 'BE', 'canada': 'CA', 'czechoslovakia': 'CZ',
        'hungary': 'HU', 'romania': 'RO', 'serbia': 'RS', 'bosnia': 'BA', 'scotland': 'GB', 'ukraine': 'UA', 'soviet': 'RU'}

# territories the Flag Atlas has no timeline for: the sovereign whose flag flew there
TERRITORY = {'PR': 'US', 'GU': 'US', 'VI': 'US', 'AS': 'US', 'MP': 'US', 'GP': 'FR', 'MQ': 'FR', 'GF': 'FR', 'RE': 'FR', 'PF': 'FR', 'NC': 'FR',
             'HK': 'CN', 'MO': 'PT', 'GI': 'GB', 'JE': 'GB', 'GG': 'GB', 'IM': 'GB', 'BM': 'GB', 'KY': 'GB', 'FK': 'GB'}

def dp_simplify(pts, tol):
    if len(pts) < 3: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True; st = [(0, len(pts) - 1)]
    while st:
        a, b = st.pop(); ax, ay = pts[a]; bx, by = pts[b]; dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy; md = 0; mi = -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = ((px - ax) ** 2 + (py - ay) ** 2) if L == 0 else (lambda t: (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2)(max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L)))
            if d > md: md, mi = d, i
        if md > tol * tol and mi > 0: keep[mi] = True; st.append((a, mi)); st.append((mi, b))
    return [p for p, k in zip(pts, keep) if k]

def inside(pt, ring):   # pt = (lat, lon); ring = [[lat, lon], ...]
    y, x = pt; ins = False; j = len(ring) - 1
    for i in range(len(ring)):
        yi, xi = ring[i]; yj, xj = ring[j]
        if (xi > x) != (xj > x) and y < (yj - yi) * (x - xi) / (xj - xi) + yi: ins = not ins
        j = i
    return ins

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--atlas', required=True); ap.add_argument('--tree', required=True); ap.add_argument('--place-map', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--from-year', type=int, default=1700)
    ap.add_argument('--eu-box', default='-13,30,50,62', help='lon0,lat0,lon1,lat1 of the finer European outline')
    a = ap.parse_args()
    A = a.atlas
    need = ['data/countries.json', 'data/regions.json', 'data/places.json', 'data/providers.json', 'site/public/mortality.json', 'site/public/flag-map.json', 'site/public/styles.css', 'site/public/atlas-tokens.css']
    miss = [f for f in need if not os.path.exists(os.path.join(A, f))]
    if miss: sys.exit('Not a Record Atlas checkout (missing %s)' % ', '.join(miss))
    J = lambda f: json.load(open(os.path.join(A, f)))
    tree = json.load(open(a.tree)); pm_all = json.load(open(a.place_map))
    # the stops of a longer route (person.route = [[place, year|null, est], ...]) are places the page draws too
    names = sorted({p['bp'] for p in tree['people'] if p.get('bp')} | {p['dp'] for p in tree['people'] if p.get('dp')} | {st[0] for p in tree['people'] for st in (p.get('route') or [])})
    pm = {}
    for raw, e in pm_all.items():
        if e.get('name') and e.get('lat') is not None: pm.setdefault(e['name'], e)
    bad = [n for n in names if n not in pm]
    if bad: sys.exit('Places used by the tree but not in the place map: %s' % bad[:10])

    # land outlines
    C = J('data/countries.json')['countries']
    box = [float(x) for x in a.eu_box.split(',')]
    def path(tol, dec, bx=None):
        out = []
        for cc, c in C.items():
            for ring in c['rings']:
                lons = [p[0] for p in ring]; lats = [p[1] for p in ring]
                if max(lats) < -60: continue
                if bx and (max(lons) < bx[0] or min(lons) > bx[2] or max(lats) < bx[1] or min(lats) > bx[3]): continue
                r = dp_simplify(ring, tol)
                if len(r) < 4: continue
                f = lambda v: ('%.*f' % (dec, v)).rstrip('0').rstrip('.')
                out.append('M' + ' '.join(f(x) + ' ' + f(-y) for x, y in r) + 'Z')
        return ''.join(out)
    land = {'world': path(0.2, 1), 'eu': path(0.04, 2, box)}

    # regions, regimes, colours
    R = J('data/regions.json'); reg = {g['id']: g for g in R['regions']}
    css = open(os.path.join(A, 'site/public/styles.css')).read() + open(os.path.join(A, 'site/public/atlas-tokens.css')).read()
    cols = {}
    for m in re.finditer(r'--r-([a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6})', css): cols.setdefault(m.group(1), []).append(m.group(2))
    riso = dict(RISO)
    for k, v in R['regimes'].items():
        if k not in riso and v.get('archives'): riso[k] = v['archives'][0]
    FM = J('site/public/flag-map.json')['f']
    def flag_at(iso, y):
        es = FM.get(iso)
        if not es: return None
        c = [(f, t, i) for f, t, i in es if f <= y and (t is None or y < t)]
        if c: return max(c, key=lambda r: r[0])[2]
        p = [(f, t, i) for f, t, i in es if f <= y]
        return max(p, key=lambda r: r[0])[2] if p else None
    def era_regime(rid, y):
        if not rid: return None
        es = reg[rid]['eras']
        for e in es:
            if e['from'] <= y < e['to']: return e['regime']
        return es[-1]['regime'] if y >= es[-1]['to'] else None

    pls = {x['id']: x for x in J('data/places.json')['places']}
    M = J('site/public/mortality.json')['events']
    places, evs = [], {}
    imgs, idx = [], {}
    def img(i):
        if i not in idx: idx[i] = len(imgs); imgs.append(i)
        return idx[i]
    used_reg = set()
    for n in names:
        e = pm[n]; lat, lon = float(e['lat']), float(e['lon'])
        rid = e.get('region') or next((g['id'] for g in R['regions'] if inside((lat, lon), g['ring'])), None)
        frid = rid or e.get('flag_region')
        aid = e.get('atlas_id') if e.get('atlas_id') in pls else None
        hit = []
        for ev in M:
            if ev['t'] < a.from_year or ev['f'] > 2025: continue
            if ev.get('g') or (ev.get('poly') and any(inside((lat, lon), r) for r in ev['poly'])):
                hit.append(ev['id'])
                if ev['id'] not in evs:
                    evs[ev['id']] = [ev['n'], ev['ty'], ev['f'], ev['t'], ev['says'][:190], ev['toll'].get('text', '')[:170]]
        iso0 = e.get('flag_iso') or TERRITORY.get(e.get('iso'), e.get('iso')); fl = []; last = None   # a territory with no flag page of its own flies its sovereign's
        for y in range(a.from_year, 2027):
            rg = era_regime(frid, y); iso = riso.get(rg) if rg else None
            if iso is None or iso not in FM: iso = iso0
            im = flag_at(iso, y) or flag_at(iso0, y)
            if im is None: continue
            k = img(im)
            if k != last: fl.append([y, k]); last = k
        if not fl: sys.exit('No flag timeline for %s: give "iso" (two letters) in the place map' % n)
        if rid: used_reg.add(rid)
        if frid: used_reg.add(frid)
        places.append({'n': n, 'id': aid, 'lat': round(lat, 3), 'lon': round(lon, 3), 'reg': rid, 'cn': e.get('country') or '', 'ev': hit, 'fl': fl,
                       'cols': [[c.get('title', '')[:80], c['url'], c.get('from'), c.get('to'), c.get('provider', '')] for c in (pls[aid].get('collections', []) if aid else []) if c.get('url')][:40],
                       'cat': [[c.get('title', '')[:80], c.get('from'), c.get('to'), c.get('provider', '')] for c in (pls[aid].get('collections', []) if aid else []) if not c.get('url')][:40],
                       **({'type': e['type']} if e.get('type') else {})})
    regions, used = {}, set()
    for k in sorted(used_reg):
        g = reg[k]; es = []
        for e in g['eras']:
            note = re.sub(r'\s+', ' ', e.get('note', '')).split('. ')[0][:170]
            es.append([e['from'], e['to'], e['regime'], e.get('polity', ''), note, e.get('filedUnder', [])]); used.add(e['regime'])
        regions[k] = {'label': g['label'], 'eras': es}
    regimes = {}
    for k in used:
        v = R['regimes'].get(k, {}); c = cols.get(k, ['#7A8790', '#A9B4BB'])
        regimes[k] = {'label': v.get('label', k), 'c': [c[0], c[-1] if len(c) > 1 else c[0]]}
    pm_prov = {x['id']: x for x in J('data/providers.json')['providers']}
    fu = {x for r in regions.values() for e in r['eras'] for x in e[5]}
    tbl = []
    for n, i in enumerate(imgs):
        s = open(os.path.join(A, 'site/public/fl', i + '.svg')).read().strip()
        vb = re.search(r'viewBox="([^"]+)"', s).group(1); inner = re.sub(r'^<svg[^>]*>|</svg>\s*$', '', s)
        inner = re.sub(r'\bid="([^"]+)"', lambda m: 'id="f%d_%s"' % (n, m.group(1)), inner)
        inner = re.sub(r'url\(#([^)]+)\)', lambda m: 'url(#f%d_%s)' % (n, m.group(1)), inner)
        inner = re.sub(r'(xlink:)?href="#([^"]+)"', lambda m: 'href="#f%d_%s"' % (n, m.group(2)), inner)
        tbl.append([vb, inner])
    out = {'land': land, 'regimes': regimes, 'regions': regions, 'places': places, 'events': evs,
           'prov': {k: pm_prov[k]['name'] for k in fu if k in pm_prov}, 'provurl': {k: pm_prov[k].get('url') for k in fu if k in pm_prov and pm_prov[k].get('url')},
           'flags': tbl, 'fid': imgs, 'rlabel': {k: reg[k]['label'] for k in regions}}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, separators=(',', ':'))
    surveyed = sum(1 for p in places if p['id'])
    print(json.dumps({'places': len(places), 'in_atlas': surveyed, 'with_region': sum(1 for p in places if p['reg']), 'events': len(evs), 'flags': len(tbl), 'bytes': os.path.getsize(a.out)}))
    gaps = [p['n'] for p in places if not p['id']]
    if gaps: print('Not in the Atlas yet (report them with the record-atlas-feedback skill):', ', '.join(gaps))

if __name__ == '__main__': main()
