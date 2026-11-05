#!/usr/bin/env python3
"""GEDCOM -> tree.json for the family-tree-page template.

    gedcom_to_tree.py family.ged --out build/tree.json --place-map build/place_map.json \
        [--living omit|redact] [--focus I123] [--line-surnames "Blazevic,Lerena"] \
        [--line-host "Blazevic=blazevic.defranceski.com"] [--slugs people-slugs.json] \
        [--atlas "<path to Record Atlas>"] [--strict] [--title "Roots & Routes"]

What it does, in order: parse, decide who is living, fill in missing years (flagged), resolve every place
through place_map.json (never guessed), drop or redact the living, and write tree.json plus a report.
It never prints a living person's name. See references/data-contract.md for the output shape.
"""
import argparse, json, re, sys, unicodedata, datetime, os

NOW = datetime.date.today().year

def fold(s):
    return unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()

def slugify(s):
    s = unicodedata.normalize('NFD', str(s or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'^-+|-+$', '', re.sub(r'[^a-zA-Z0-9]+', '-', s)).lower()[:60]

# ---------- parse ----------
LINE = re.compile(r'^\s*(\d+)\s+(?:(@[^@]+@)\s+)?([A-Za-z_0-9]+)(?:\s(.*))?$')

class Node:
    __slots__ = ('tag', 'val', 'xref', 'kids')
    def __init__(self, tag, val, xref): self.tag, self.val, self.xref, self.kids = tag, (val or '').strip(), xref, []
    def get(self, tag): return next((k for k in self.kids if k.tag == tag), None)
    def all(self, tag): return [k for k in self.kids if k.tag == tag]
    def text(self):
        out = self.val
        for k in self.kids:
            if k.tag in ('CONC',): out += k.val
            elif k.tag == 'CONT': out += '\n' + k.val
        return out

def parse(path):
    recs, stack = [], []
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        for raw in f:
            m = LINE.match(raw.rstrip('\r\n'))
            if not m: continue
            lvl, xref, tag, val = int(m.group(1)), m.group(2), m.group(3), m.group(4)
            n = Node(tag, val, xref)
            while len(stack) > lvl: stack.pop()
            if lvl == 0: recs.append(n)
            elif stack: stack[-1].kids.append(n)
            stack.append(n)
    return recs

def year_of(s):
    m = re.search(r'(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)', s or '')
    return int(m.group(1)) if m else None

def clean_name(n):
    given = surn = ''
    if n is None: return '', ''
    g, s = n.get('GIVN'), n.get('SURN')
    m = re.match(r'^(.*?)\s*/(.*?)/', n.val)
    if m: given, surn = m.group(1).strip(), m.group(2).strip()
    else: given = n.val.strip()
    if g and g.val: given = g.val.strip()
    if s and s.val: surn = s.val.strip()
    return re.sub(r'\s+', ' ', given), re.sub(r'\s+', ' ', surn)

def ev(node, *tags):
    for t in tags:
        e = node.get(t)
        if e:
            d, p = e.get('DATE'), e.get('PLAC')
            return year_of(d.val if d else ''), (p.val.strip() if p and p.val.strip() else None), e
    return None, None, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('gedcom'); ap.add_argument('--out', required=True)
    ap.add_argument('--place-map', required=True, help='JSON: raw GEDCOM place -> {name,lat,lon,country,iso,atlas_id?,region?,type?}; created/extended with TODO entries')
    ap.add_argument('--living', choices=['omit', 'redact'], default='omit')
    ap.add_argument('--focus'); ap.add_argument('--lines', type=int, default=8)
    ap.add_argument('--line-surnames', help='comma list of surnames that get their own colour (max lines-1)')
    ap.add_argument('--line-host', action='append', default=[], help='Surname=host (repeatable): the family site that holds that surname')
    ap.add_argument('--slugs', help='JSON id->slug (or name->slug) from the site, so People links match its real pages')
    ap.add_argument('--atlas', help='Record Atlas checkout: used to SUGGEST places for unresolved strings')
    ap.add_argument('--accept-unique', action='store_true', help='auto-accept an Atlas suggestion only when it is the single match AND the string names its country')
    ap.add_argument('--unplaced', choices=['parent', 'drop'], default='parent')
    ap.add_argument('--strict', action='store_true', help='exit 1 while any place used by a kept person is unresolved')
    ap.add_argument('--title'); ap.add_argument('--subtitle')
    a = ap.parse_args()

    recs = parse(a.gedcom)
    srcrec = {r.xref: r for r in recs if r.tag == 'SOUR'}
    fams = {r.xref: r for r in recs if r.tag == 'FAM'}
    P = {}
    for r in recs:
        if r.tag != 'INDI': continue
        given, sur = clean_name(r.get('NAME'))
        by, bp, _ = ev(r, 'BIRT', 'CHR', 'BAPM')
        dy, dp, dnode = ev(r, 'DEAT', 'BURI', 'CREM')
        res = []
        for e in r.all('RESI'):
            d, p = e.get('DATE'), e.get('PLAC')
            if p and p.val.strip(): res.append((year_of(d.val if d else ''), p.val.strip()))
        occ = r.get('OCCU')
        srcs = []
        for node in [r] + [k for k in r.kids if k.tag in ('BIRT', 'DEAT', 'MARR', 'CHR', 'BURI', 'RESI')]:
            for s in node.all('SOUR'):
                t, u = None, None
                if s.val.startswith('@') and s.val in srcrec:
                    sr = srcrec[s.val]; tt = sr.get('TITL') or sr.get('ABBR')
                    t = tt.text() if tt else s.val
                    blob = ' '.join(k.text() for k in sr.kids)
                    m = re.search(r'https?://\S+', blob); u = m.group(0) if m else None
                else:
                    t = s.text()
                if t and not any(x['t'] == t for x in srcs): srcs.append({'t': t[:140], **({'u': u} if u else {})})
        has_death = bool(r.get('DEAT') or r.get('BURI') or r.get('CREM'))
        P[r.xref.strip('@')] = dict(id=r.xref.strip('@'), sex=(r.get('SEX').val[:1].lower() if r.get('SEX') and r.get('SEX').val else 'u'),
            given=given, sur=sur, by=by, bp_raw=bp, dy=dy, dp_raw=dp, resi=res, occ=occ.val if occ else None, srcs=srcs[:6],
            death_known=has_death, father=None, mother=None, spouse=[], kids=[])
    for fx, f in fams.items():
        h = f.get('HUSB'); w = f.get('WIFE')
        h = h.val.strip('@') if h and h.val else None; w = w.val.strip('@') if w and w.val else None
        h = h if h in P else None; w = w if w in P else None
        if h and w: P[h]['spouse'].append(w); P[w]['spouse'].append(h)
        for c in f.all('CHIL'):
            cid = c.val.strip('@')
            if cid not in P: continue
            if h: P[cid]['father'] = h; P[h]['kids'].append(cid)
            if w: P[cid]['mother'] = w; P[w]['kids'].append(cid)
    for p in P.values():
        p['spouse'] = list(dict.fromkeys(p['spouse'])); p['kids'] = list(dict.fromkeys(p['kids']))

    # ---------- fill in missing birth years (flagged) ----------
    est = set()
    for _ in range(4):
        for p in P.values():
            if p['by'] is not None: continue
            c = None
            if p['father'] and P[p['father']]['by']: c = P[p['father']]['by'] + 30
            elif p['mother'] and P[p['mother']]['by']: c = P[p['mother']]['by'] + 28
            elif p['kids']:
                ks = [P[k]['by'] for k in p['kids'] if P[k]['by']]
                if ks: c = min(ks) - 28
            if c is None and p['spouse']:
                ss = [P[s]['by'] for s in p['spouse'] if P[s]['by']]
                if ss: c = ss[0]
            if c: p['by'] = c; est.add(p['id'])

    # ---------- who is living ----------
    for p in P.values():
        p['liv'] = (not p['death_known']) and (p['by'] is None or p['by'] > NOW - 110)
        if not p['liv'] and p['dy'] is None and p['by'] is not None:
            p['dy'] = min(p['by'] + 75, NOW - 1); est.add('d' + p['id'])

    # ---------- places: resolved through the map only ----------
    pm = json.load(open(a.place_map)) if os.path.exists(a.place_map) else {}
    used = {}
    def want(raw):
        if raw: used[raw] = used.get(raw, 0) + 1
    for p in P.values():
        if p['liv'] and a.living == 'omit': continue
        want(p['bp_raw']); want(p['dp_raw'])
        for _, rp in p['resi']: want(rp)
    ok = lambda k: pm.get(k) and pm[k].get('lat') is not None and pm[k].get('name')
    sugg = {}
    if a.atlas and any(not ok(k) for k in used):
        pj = json.load(open(os.path.join(a.atlas, 'data/places.json')))['places']
        cj = json.load(open(os.path.join(a.atlas, 'data/countries.json')))['countries']
        idx = {}
        for x in pj:
            for nm in [x['name']] + [n['n'].split(',')[0] for n in x.get('names', [])]:
                idx.setdefault(fold(nm.strip()), {})[x['id']] = x
        for k in used:
            if ok(k): continue
            segs = [t.strip() for t in k.split(',')]
            cands = list(idx.get(fold(segs[0]), {}).values())
            sugg[k] = cands
            named = [c for c in cands if fold(cj.get(c['country'], {}).get('name', '')) in fold(k) or fold(c['country']) == fold(segs[-1])]
            if a.accept_unique and len(cands) >= 1 and len(named) == 1:
                c = named[0]; pm[k] = {'name': c['name'], 'lat': c['lat'], 'lon': c['lon'], 'country': cj.get(c['country'], {}).get('name', c['country']), 'iso': c['country'], 'atlas_id': c['id']}
    unresolved = {k: v for k, v in used.items() if not ok(k)}
    todo = dict(pm)
    for k in unresolved:
        todo.setdefault(k, {'name': None, 'lat': None, 'lon': None, 'country': None, 'iso': None, 'atlas_id': None,
            'note': 'TODO: copy one suggestion (or give coordinates) once you have checked the country; never guessed',
            'suggest': [{'atlas_id': c['id'], 'name': c['name'], 'country': c['country'], 'lat': c['lat'], 'lon': c['lon']} for c in sugg.get(k, [])[:4]]})
    json.dump(todo, open(a.place_map, 'w'), indent=1, ensure_ascii=False)
    def pname(raw): return pm[raw]['name'] if ok(raw) else None

    # ---------- keep / drop ----------
    keep = {}
    for p in P.values():
        if p['liv'] and a.living == 'omit': continue
        if p['by'] is None: continue
        keep[p['id']] = p
    unplaced = 0
    for p in keep.values():
        p['bp'] = pname(p['bp_raw'])
    for _ in range(3):
        for p in keep.values():
            if p['bp']: continue
            for rid in [p['father'], p['mother']] + p['spouse'] + p['kids']:
                if rid in keep and keep[rid].get('bp') and a.unplaced == 'parent': p['bp'] = keep[rid]['bp']; unplaced += 1; break
    dropped_unplaced = [i for i, p in keep.items() if not p['bp']]
    for i in dropped_unplaced: del keep[i]
    for p in keep.values():
        p['dp'] = pname(p['dp_raw']) or p['bp']
        # a move: a later residence in another place, else (estimated) the gap between birth and death place
        p['my'] = None; p['mye'] = False
        if not p['liv']:
            for y, rp in sorted(p['resi'], key=lambda t: (t[0] is None, t[0] or 0)):
                n = pname(rp)
                if n and n != p['bp'] and y and y > p['by'] + 14: p['my'] = y; p['dp'] = n; break
            if p['my'] is None and p['dp'] != p['bp'] and p['dy'] and p['dy'] - p['by'] > 24:
                p['my'] = p['by'] + int((p['dy'] - p['by']) * .6); p['mye'] = True
            if p['dp'] == p['bp']: p['my'] = None
    for p in keep.values():
        for k in ('father', 'mother'):
            if p[k] not in keep: p[k] = None
        p['spouse'] = [s for s in p['spouse'] if s in keep]; p['kids'] = [k for k in p['kids'] if k in keep]

    # ---------- lines (surname colours) ----------
    counts = {}
    for p in keep.values():
        if p['sur']: counts[fold(p['sur'])] = counts.get(fold(p['sur']), [0, p['sur']]); counts[fold(p['sur'])][0] += 1
    if a.line_surnames: order = [fold(s.strip()) for s in a.line_surnames.split(',') if s.strip()][:a.lines - 1]
    else: order = [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1][0])][:a.lines - 1]
    hosts = {fold(x.split('=')[0]): x.split('=', 1)[1] for x in a.line_host if '=' in x}
    lines = [{'sur': counts.get(k, [0, k.title()])[1], 'host': hosts.get(k, '')} for k in order]
    slugs = json.load(open(a.slugs)) if a.slugs else {}

    # ---------- focus ----------
    def desc(i, seen=None):
        seen = seen if seen is not None else set()
        for k in keep[i]['kids']:
            if k not in seen: seen.add(k); desc(k, seen)
        return seen
    def anc(i, seen=None):
        seen = seen if seen is not None else set()
        for k in (keep[i]['father'], keep[i]['mother']):
            if k and k not in seen: seen.add(k); anc(k, seen)
        return seen
    focus = a.focus if a.focus in keep else None
    if not focus:
        best = -1
        for i, p in keep.items():
            if p['liv']: continue
            sc = min(len(desc(i)), 30) + min(len(anc(i)), 30)
            if sc > best: best, focus = sc, i

    people = []
    for i, p in keep.items():
        li = order.index(fold(p['sur'])) if fold(p['sur']) in order else a.lines - 1   # everyone else shares the last colour
        given = '' if p['liv'] else p['given']
        by = p['by'] if not p['liv'] else (p['by'] // 10 * 10 if a.living == 'redact' else p['by'])
        people.append({'id': i, 'sex': p['sex'], 'given': given, 'sur': p['sur'], 'line': min(li, a.lines - 1), 'by': by,
            'bp': p['bp'], 'dy': None if p['liv'] else p['dy'], 'dp': None if p['liv'] else p['dp'], 'my': p['my'],
            'occ': None if p['liv'] else p['occ'], 'father': p['father'], 'mother': p['mother'], 'spouse': p['spouse'], 'kids': p['kids'],
            'srcs': [] if p['liv'] else p['srcs'], 'bye': p['id'] in est, 'dye': ('d' + p['id']) in est, 'slug': slugs.get(i) or slugs.get(slugify(p['given'] + ' ' + p['sur'])) or (None if p['liv'] else slugify(p['given'] + ' ' + p['sur']))})
    # the page pads the line list to the number of colours it has
    out = {'meta': {k: v for k, v in {'title': a.title, 'sub': a.subtitle, 'living': a.living, 'generated': datetime.date.today().isoformat(), 'source': os.path.basename(a.gedcom)}.items() if v},
           'lines': lines, 'focus': focus, 'people': people}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, separators=(',', ':'))
    rep = {'individuals': len(P), 'kept': len(people), 'living': sum(1 for p in P.values() if p['liv']), 'living_policy': a.living,
           'undated_dropped': sum(1 for p in P.values() if p['by'] is None), 'birth_year_estimated': len([e for e in est if not e.startswith('d')]),
           'death_year_estimated': len([e for e in est if e.startswith('d')]), 'placed_from_relative': unplaced, 'dropped_unplaced': len(dropped_unplaced),
           'unresolved_places': dict(sorted(unresolved.items(), key=lambda kv: -kv[1])[:40]), 'focus': focus}
    json.dump(rep, open(os.path.splitext(a.out)[0] + '.report.json', 'w'), indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != 'unresolved_places'}))
    if unresolved:
        print('%d place strings are not resolved yet (see %s):' % (len(unresolved), a.place_map)); [print('  %4d  %s' % (v, k)) for k, v in list(rep['unresolved_places'].items())[:15]]
        if a.strict: sys.exit(1)

if __name__ == '__main__': main()
