#!/usr/bin/env python3
"""One command to rebuild a site's tree page from its config.

    rebuild.py path/to/tree-page.config.json [--only tree|atlas|page|check] [--accept-unique]

Runs gedcom_to_tree -> build_atlas_data -> build_page -> check_tree_page, in that order, stopping at the first failure.
Paths in the config are relative to the config file. See assets/tree-page.config.example.json.
"""
import argparse, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('config'); ap.add_argument('--only', choices=['tree', 'atlas', 'page', 'check']); ap.add_argument('--accept-unique', action='store_true')
    a = ap.parse_args()
    base = os.path.dirname(os.path.abspath(a.config)); c = json.load(open(a.config))
    P = lambda k: os.path.normpath(os.path.join(base, os.path.expanduser(c[k]))) if c.get(k) else None
    work = P('work'); os.makedirs(work, exist_ok=True)
    tree, at, pm = os.path.join(work, 'tree.json'), os.path.join(work, 'atlas-data.json'), os.path.join(work, 'place_map.json')
    atlas = os.path.expanduser(c['atlas']); page = P('page')
    py = sys.executable
    def run(args):
        print('$', ' '.join(args)); r = subprocess.run(args)
        if r.returncode: sys.exit(r.returncode)
    steps = [a.only] if a.only else ['tree', 'atlas', 'page', 'check']
    if 'tree' in steps:
        cmd = [py, os.path.join(HERE, 'gedcom_to_tree.py'), P('gedcom'), '--out', tree, '--place-map', pm, '--atlas', atlas, '--living', c.get('living', 'omit'), '--lines', str(c.get('lines', 8)), '--strict']
        if a.accept_unique or c.get('accept_unique'): cmd.append('--accept-unique')
        if c.get('focus'): cmd += ['--focus', c['focus']]
        if c.get('line_surnames'): cmd += ['--line-surnames', ','.join(c['line_surnames'])]
        for s, h in (c.get('line_hosts') or {}).items(): cmd += ['--line-host', '%s=%s' % (s, h)]
        if c.get('slugs'): cmd += ['--slugs', P('slugs')]
        if c.get('title'): cmd += ['--title', c['title']]
        if c.get('subtitle'): cmd += ['--subtitle', c['subtitle']]
        run(cmd)
    if 'atlas' in steps: run([py, os.path.join(HERE, 'build_atlas_data.py'), '--atlas', atlas, '--tree', tree, '--place-map', pm, '--out', at])
    if 'page' in steps:
        cmd = [py, os.path.join(HERE, 'build_page.py'), '--tree', tree, '--atlas-data', at, '--out', page, '--atlas-url', c.get('atlas_url', 'https://recordatlas.org')]
        if c.get('title'): cmd += ['--title', c['title']]
        if c.get('subtitle'): cmd += ['--subtitle', c['subtitle']]
        if c.get('back_url'): cmd += ['--back-url', c['back_url'], '--back-label', c.get('back_label', 'Back to the archive')]
        run(cmd)
    if 'check' in steps: run([py, os.path.join(HERE, 'check_tree_page.py'), '--tree', tree, '--atlas-data', at, '--page', page])
if __name__ == '__main__': main()
