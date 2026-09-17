import json,urllib.request,urllib.parse,re,sys
API="https://digital.zlb.de/viewer/api/v1/index/query"
def q(query,count=50,offset=0):
    body=json.dumps({"query":query,"count":count,"offset":offset}).encode()
    r=urllib.request.Request(API,data=body,headers={'Content-Type':'application/json','Accept':'application/json'})
    return json.load(urllib.request.urlopen(r,timeout=90))
def pagetext(pi,order):
    for u in [f"https://digital.zlb.de/viewer/api/v1/records/{pi}/pages/{order}/text/",
              f"https://digital.zlb.de/viewer/api/v1/records/{pi}/pages/{order}/plaintext/"]:
        try:
            rq=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0','Accept':'text/plain,*/*'})
            return urllib.request.urlopen(rq,timeout=90).read().decode('utf-8','ignore')
        except Exception as e:
            last=e
    return ''

def lines(pi,order):
    """Return the OCR text lines of a page, in reading order."""
    import json as _j
    raw=pagetext(pi,order)
    try:
        d=_j.loads(raw)
    except Exception:
        return [l for l in raw.splitlines() if l.strip()]
    out=[]
    for r in d.get('resources') or []:
        c=r.get('resource') or {}
        v=c.get('chars') or c.get('@value') or ''
        if v.strip(): out.append(v.strip())
    return out
