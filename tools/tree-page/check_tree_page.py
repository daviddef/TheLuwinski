#!/usr/bin/env python3
"""The gate. Fails (exit 1) rather than warning, because a tree page that lies is worse than none.

    check_tree_page.py --tree build/tree.json --atlas-data build/atlas-data.json [--page site/public/roots/index.html]
"""
import argparse, json, sys, datetime, re
NOW = datetime.date.today().year
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--tree', required=True); ap.add_argument('--atlas-data', required=True); ap.add_argument('--page')
    a = ap.parse_args()
    t = json.load(open(a.tree)); at = json.load(open(a.atlas_data))
    P = {p['id']: p for p in t['people']}; places = {p['n'] for p in at['places']}
    errs = []; warn = []
    pol = (t.get('meta') or {}).get('living', 'omit')
    for p in P.values():
        for k in ('bp', 'dp'):
            if p.get(k) and p[k] not in places: errs.append('%s: place %r is not in atlas-data' % (p['id'], p[k]))
        for st in (p.get('route') or []):
            if st[0] not in places: errs.append('%s: route stop %r is not in atlas-data' % (p['id'], st[0]))
        if not p.get('bp'): errs.append('%s has no birth place' % p['id'])
        if p.get('by') is None: errs.append('%s has no birth year' % p['id'])
        if p.get('dy') is not None and p['by'] is not None and not (p['by'] <= p['dy'] <= p['by'] + 125): errs.append('%s: impossible life %s-%s' % (p['id'], p['by'], p['dy']))
        if p['by'] and p['by'] > NOW: errs.append('%s born in the future' % p['id'])
        for k in ('father', 'mother'):
            if p.get(k) and p[k] not in P: errs.append('%s: %s %s missing' % (p['id'], k, p[k]))
            elif p.get(k) and p['id'] not in P[p[k]]['kids']: errs.append('%s: %s does not list them as a child' % (p['id'], p[k]))
        for c in p['kids']:
            if c not in P: errs.append('%s: child %s missing' % (p['id'], c))
        if p.get('dy') is None:   # living
            if pol == 'omit': errs.append('%s is living but the policy is omit' % p['id'])
            if p.get('given') or p.get('occ') or p.get('srcs') or p.get('dp'): errs.append('%s is living and carries personal details' % p['id'])
        elif p['by'] and p['by'] > NOW - 100 and p['dy'] is None: errs.append('%s recent birth without death' % p['id'])
    if t.get('focus') not in P: errs.append('focus person %r is not in the tree' % t.get('focus'))
    gaps = [p['n'] for p in at['places'] if not p['id']]
    if gaps: warn.append('places not in the Atlas yet: ' + ', '.join(gaps))
    if a.page:
        h = open(a.page, encoding='utf-8').read()
        for ph in ('/*ATLAS_DATA*/null', '/*TREE_DATA*/null', '<!--EXT:', '/*EXT:'):
            if ph in h: errs.append('page still contains placeholder ' + ph)
        if len(h.encode()) > 12_000_000: errs.append('page is over 12 MB')
        living_given = [p for p in t['people'] if p.get('dy') is None and p.get('given')]
        if living_given: errs.append('living given names are in the page')
    for w in warn: print('warn:', w)
    for e in errs[:40]: print('FAIL:', e)
    print('%d people, %d places, %d problems' % (len(P), len(places), len(errs)))
    sys.exit(1 if errs else 0)
if __name__ == '__main__': main()
