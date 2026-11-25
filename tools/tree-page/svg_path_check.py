"""Is an SVG path's data well formed? Browsers stop drawing at the first bad command and log an error each time the
drawing is rendered. scan(d) returns (True, None) or (False, index where the first malformed command group begins).
Used by scripts/check-data.py to stop a flag drawing whose numbers a minifier has fused or dropped from shipping."""
import re
AR={'m':2,'l':2,'h':1,'v':1,'c':6,'s':4,'q':4,'t':2,'a':7,'z':0}
NUM=re.compile(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?')
def scan(d):
    """return (ok, cut) — cut = index where the first malformed command group begins"""
    i=0;n=len(d);cmd=None;cmdpos=0
    skip=lambda i:(i+1 if False else i)
    def ws(i):
        while i<n and d[i] in ' ,\t\r\n': i+=1
        return i
    while True:
        i=ws(i)
        if i>=n: return True,None
        if d[i].isalpha():
            cmd=d[i].lower();cmdpos=i;i+=1
            if cmd not in AR: return False,cmdpos
            if cmd=='z': continue
            first=True
        else:
            if cmd is None or cmd=='z': return False,i
            first=False
        gstart=cmdpos if first else i
        j=ws(i)
        need=AR[cmd]
        for k in range(need):
            j=ws(j)
            if cmd=='a' and k in (3,4):
                if j<n and d[j] in '01': j+=1; continue
                return False,gstart
            m=NUM.match(d,j)
            if not m: return False,gstart
            j=m.end()
        i=j
def trunc(d):
    ok,cut=scan(d)
    return d if ok else d[:cut].rstrip(' ,')

def bad_paths(svg):
    """character offsets (inside each d attribute) of the first malformed command in every <path d> of an SVG string; [] when all parse.
    Added for the family-tree-page skill (build_atlas_data.py and check_tree_page.py); the scanner above is the Atlas's own, unchanged."""
    out = []
    for m in re.finditer(r'\sd="([^"]+)"', svg):
        d = m.group(1)
        if re.match(r'^[Mm]', d):
            ok, cut = scan(d)
            if not ok: out.append(cut)
    return out
