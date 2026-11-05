#!/usr/bin/env python3
"""Fill the template with a tree and an Atlas slice and write the page.

    build_page.py --tree build/tree.json --atlas-data build/atlas-data.json --out site/public/roots/index.html \
        [--title "Roots & Routes"] [--subtitle "..."] [--atlas-url https://recordatlas.org] [--back-url / --back-label "The Archive"]

The page is one self-contained HTML file: no network calls except links the reader clicks.
"""
import argparse, json, os, re, html
VERSION = '1.6.0'
SCOPE = 'rr'

def _split(sel):
    out, depth, cur = [], 0, ''
    for ch in sel:
        if ch in '([': depth += 1
        elif ch in ')]': depth -= 1
        if ch == ',' and depth == 0: out.append(cur); cur = ''
        else: cur += ch
    return out + [cur]

def _scope_css(css):
    """Prefix every selector with #rr so the page's styles cannot touch the site around it. :root and body become #rr itself."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find('{', i)
        if j < 0: out.append(css[i:]); break
        head = css[i:j].strip(); depth, k = 1, j + 1
        while k < n and depth:
            depth += {'{': 1, '}': -1}.get(css[k], 0); k += 1
        body = css[j + 1:k - 1]
        if head.startswith('@media'): out.append(head + '{' + _scope_css(body) + '}')
        elif head.startswith('@'): out.append(head + '{' + body + '}')
        else:
            sels = []
            for x in _split(head):
                x = x.strip()
                if not x: continue
                if re.match(r':root(?![\w-])', x):   # a theme switch lives on <html>, the variables on #rr
                    rest = x[5:]
                    sels.append('#' + SCOPE if not rest else 'html' + rest + ' #' + SCOPE)
                    continue
                x = re.sub(r'^(body|html)(?![\w-])', '#' + SCOPE, x)
                sels.append(x if x.startswith('#' + SCOPE) else '#' + SCOPE + ' ' + x)
            out.append(','.join(sels) + '{' + body + '}')
        i = k
    return '\n'.join(out)

def embed(t):
    """The page as a fragment for a site layout: scoped styles, no <html>/<head>/<body>, no title block (the layout has its own),
    the same light/dark switch as the site (prefers-color-scheme, or data-theme on <html>), and `.wrap` renamed so the layout's own `.wrap` rules do not reach it."""
    m = re.search(r'<style>(.*?)</style>', t, re.S)
    head, css, body = t[:m.start()], m.group(1), t[m.end():]
    links = ''.join(re.findall(r'<link[^>]*>', head))
    css = re.sub(r'(^|\})\s*body\{[^}]*\}', r'\1 body{background:transparent;color:var(--ink);font:15px/1.5 var(--sans)}', css, count=1)
    css = css.replace('.wrap{', '.rrwrap{')
    css = _scope_css(css) + '\n#rr [hidden]{display:none!important}\n#rr .top>div:first-child{display:none}\n#rr .top{justify-content:flex-end}'
    body = body.replace('<div class="wrap">', '<div class="rrwrap">')
    return links + '<style>' + css + '</style>\n<div id="' + SCOPE + '">\n' + body + '\n</div>\n'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', default=os.path.join(os.path.dirname(__file__), '..', 'assets', 'tree-views.template.html'))
    ap.add_argument('--tree', required=True); ap.add_argument('--atlas-data', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--title'); ap.add_argument('--subtitle'); ap.add_argument('--atlas-url', default='https://recordatlas.org')
    ap.add_argument('--back-url'); ap.add_argument('--back-label', default='Back to the archive')
    ap.add_argument('--embed', action='store_true', help='write a fragment for a site layout (scoped styles, light palette, no title block) instead of a whole document')
    ap.add_argument('--ext', action='append', default=[], help='extension module(s): extra tabs, views, style and script injected at the template markers (see painted-lines.ext.html)')
    ap.add_argument('--check', action='store_true', help='only report whether the existing page was built from an older template')
    a = ap.parse_args()
    if a.check:
        old = open(a.out).read() if os.path.exists(a.out) else ''
        m = re.search(r'name="family-tree-page" content="([^"]+)"', old)
        print('page template: %s, skill template: %s' % (m.group(1) if m else 'none', VERSION)); return
    t = open(a.template, encoding='utf-8').read()
    tree = json.load(open(a.tree)); at = open(a.atlas_data, encoding='utf-8').read()
    if a.title: tree.setdefault('meta', {})['title'] = a.title
    if a.subtitle: tree.setdefault('meta', {})['sub'] = a.subtitle
    for ph in ('/*ATLAS_DATA*/null', '/*TREE_DATA*/null'):
        assert ph in t, 'template is missing ' + ph
    t = t.replace('/*ATLAS_DATA*/null', at).replace('/*TREE_DATA*/null', json.dumps(tree, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
    # optional extension modules: <!--EXT:NAMES a,b--> and <!--EXT:TABS|VIEWS|STYLE|SCRIPT-->...<!--/EXT:...-->. Without one the markers are simply removed.
    ext = {'NAMES': [], 'TABS': '', 'VIEWS': '', 'STYLE': '', 'SCRIPT': ''}
    for f in a.ext:
        x = open(f, encoding='utf-8').read()
        m = re.search(r'<!--EXT:NAMES ([^>]*?)-->', x)
        if m: ext['NAMES'] += [n.strip() for n in m.group(1).split(',') if n.strip()]
        for sec in ('TABS', 'VIEWS', 'STYLE', 'SCRIPT'):
            m = re.search(r'<!--EXT:%s-->(.*?)<!--/EXT:%s-->' % (sec, sec), x, re.S)
            if m: ext[sec] += m.group(1)
    t = t.replace('/*EXT:NAMES*/', ','.join("'%s'" % n for n in ext['NAMES'])).replace('<!--EXT:TABS-->', ext['TABS']).replace('<!--EXT:VIEWS-->', ext['VIEWS']) \
         .replace('/*EXT:STYLE*/', ext['STYLE']).replace('/*EXT:SCRIPT*/', ext['SCRIPT'])
    t = t.replace('https://recordatlas.org', a.atlas_url.rstrip('/'))
    title = (tree.get('meta') or {}).get('title') or 'Roots & Routes'
    t = re.sub(r'<title>.*?</title>', '<title>' + html.escape(title, quote=False) + '</title>\n<meta name="family-tree-page" content="' + VERSION + '">', t, count=1)
    if a.back_url:
        t = t.replace('<div class="wrap">', '<div class="wrap">\n  <p style="margin:0 0 10px;font-size:13px"><a href="' + html.escape(a.back_url) + '">← ' + html.escape(a.back_label) + '</a></p>', 1)
    if a.embed: t = embed(t)
    elif not t.lstrip().lower().startswith('<!doctype'):   # a standards-mode document with the base rules the template relies on
        t = ('<!doctype html>\n<html lang="en">\n<head>\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
             '<style>[hidden]{display:none!important}body{margin:0}img{max-width:100%}</style>\n' + t + '\n</body>\n</html>\n')
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, 'w', encoding='utf-8').write(t)
    print('wrote %s (%.0f KB)' % (a.out, len(t.encode()) / 1024))
if __name__ == '__main__': main()
