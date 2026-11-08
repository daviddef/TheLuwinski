#!/usr/bin/env python3
"""Write a small invented GEDCOM (no real people) for smoke-testing the pipeline: make_sample_gedcom.py out.ged"""
import random, sys
R = random.Random(7)
FAM = [('Marelli', ['Pula, Istria, Croatia', 'Trieste, Italy'], ['Antonio', 'Luigi', 'Pietro'], ['Maria', 'Anna', 'Rosa']),
       ('Kovac', ['Dubrovnik, Croatia', 'Mljet, Croatia'], ['Ivan', 'Marko', 'Luka'], ['Mara', 'Ana', 'Jelena']),
       ('Doyle', ['Cork, Ireland', 'Liverpool, England'], ['John', 'Patrick', 'Thomas'], ['Mary', 'Bridget', 'Ellen'])]
EMIG = ['Sydney, Australia', 'Montevideo, Uruguay']
people, fams, n = [], [], [0]
def person(fi, sex, by, place=None):
    n[0] += 1; s, pl, m, f = FAM[fi]
    p = dict(id='I%d' % n[0], sex=sex, given=R.choice(m if sex == 'M' else f), sur=s, by=by, bp=place or R.choice(pl), fams=[], famc=None)
    age = R.randint(40, 88); p['dy'] = by + age if by + age < 2015 else None
    p['dp'] = p['bp'] if R.random() < .75 else R.choice(pl + EMIG)
    people.append(p); return p
def family(h, w, depth):
    fams.append(dict(id='F%d' % (len(fams) + 1), h=h, w=w, kids=[])); f = fams[-1]
    h['fams'].append(f['id']); w['fams'].append(f['id'])
    b = w['by'] + R.randint(20, 28)
    for _ in range(R.choice([1, 2, 2, 3])):
        if b > 1990: break
        c = person(FAM.index(next(x for x in FAM if x[0] == h['sur'])), R.choice('MF'), b, h['bp'] if R.random() < .8 else R.choice(FAM[0][1] + EMIG))
        c['famc'] = f['id']; f['kids'].append(c['id'])
        if depth < 5 and R.random() < .8:
            sp = person(R.randrange(3), 'F' if c['sex'] == 'M' else 'M', b + R.randint(-3, 4))
            family(*(c, sp) if c['sex'] == 'M' else (sp, c), depth + 1)
        b += R.randint(2, 4)
for fi in range(3):
    h = person(fi, 'M', 1790 + fi * 6); w = person((fi + 1) % 3, 'F', h['by'] + 2); family(h, w, 0)
for _ in range(8): person(R.randrange(3), R.choice('MF'), R.randint(1830, 1950))   # unconnected records
out = ['0 HEAD', '1 CHAR UTF-8', '1 SOUR sample']
for p in people:
    out += ['0 @%s@ INDI' % p['id'], '1 NAME %s /%s/' % (p['given'], p['sur']), '2 GIVN ' + p['given'], '2 SURN ' + p['sur'], '1 SEX ' + p['sex'],
            '1 BIRT', '2 DATE %d' % p['by'], '2 PLAC ' + p['bp']]
    if p['dy']: out += ['1 DEAT', '2 DATE %d' % p['dy'], '2 PLAC ' + p['dp']]
    if p['famc']: out.append('1 FAMC @%s@' % p['famc'])
    out += ['1 FAMS @%s@' % f for f in p['fams']]
    if R.random() < .6: out += ['1 SOUR', '2 PAGE parish register']
for f in fams:
    out += ['0 @%s@ FAM' % f['id'], '1 HUSB @%s@' % f['h']['id'], '1 WIFE @%s@' % f['w']['id']] + ['1 CHIL @%s@' % c for c in f['kids']]
out.append('0 TRLR')
open(sys.argv[1], 'w', encoding='utf-8').write('\n'.join(out) + '\n'); print(len(people), 'invented people,', len(fams), 'families')
