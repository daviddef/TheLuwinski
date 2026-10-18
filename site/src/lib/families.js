/* THE FAMILY PAGES, DRAWN FROM DATA THIS ARCHIVE ALREADY HOLDS. Added 17 October 2026.

   Nothing here is research. A family is a SURNAME LINE: this module collects the people of the name out of
   the register (src/data/register.json) and the English line (src/data/english-people.json), reads the tree's
   own entries for the name (src/data/tree.json), the marriages that join the name to other names, the lanes
   the work already keeps (src/data/lines.json), and counts. src/data/families.json only DECLARES which
   people, which tree entries and which pages belong to which name (see its _why); tools/check-families.py
   reads the built pages and fails if any of that is wrong.

   THE LIVING STANDARD (version 2). A family page counts the living and names none of them: `nLiving` is a
   number. Who is living is the register's flag (`living`, `bare`), which the generator took from the kit's one
   definition (kit/tools/living_rule.py); this module has no test of its own. A person the register holds as a
   placeholder (a name the source tree could not give) is counted and never listed. An English-line relative is
   listed only if the data gives a birth year of 1940 or earlier, or no birth year at all; anyone born later is
   counted in `nHeld` and left off, so a future row cannot reach a page by being added.

   NOTHING IS MATCHED BY NAME THAT CAN BE DECLARED. A name is not a person (this archive learned that the hard
   way: Emma Hawkins and her mother share one). People reach a family by surname, which is a membership test
   and not an identity; the tree entries are linked to people by declared id or slug. */
import register from '../data/register.json';
import english from '../data/english-people.json';
import tree from '../data/tree.json';
import evidence from '../data/evidence.json';
import lines from '../data/lines.json';
import names from '../data/names.json';
import cfg from '../data/families.json';
import { u } from './url.js';

export const fold = (s) =>
  String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

const BY_ID = new Map(register.people.map((p) => [String(p.id), p]));
const BY_SLUG = new Map(english.people.map((p) => [p.slug, p]));
const READ = new Map();
for (const e of evidence.people) if (e.register_id) READ.set(String(e.register_id), e.records.length);

/* The surname the register files a person under: `last`, or, where the source tree left it empty (it does for
   about a dozen real people), the last word of the name outside any parenthesis. */
export function surnameOf(p) {
  if (p.last) return p.last;
  const bare = String(p.name || '').replace(/\([^)]*\)/g, ' ').trim().split(/\s+/);
  return bare[bare.length - 1] || '';
}

const qy = (y, q) => (y ? (q ? `${q} ${y}` : String(y)) : '');
const lifeOf = (p) => [qy(p.by, p.byq), qy(p.dy, p.dyq)].filter(Boolean).join(' – ');
const isLiving = (p) => p.living === true || p.bare === true;
const yearsIn = (s) => (String(s || '').match(/\b(1[5-9]\d\d|20[0-4]\d)\b/g) || []).map(Number);

/* A place for a tile and for the places line: the town of the person's own birth, baptism, death or burial
   fact, as the tree writes it (the part before the first comma). A street, a number or a very long string is
   not a town and is left out. */
const PLACE_FACTS = new Set(['BIRT', 'BAPM', 'CHR', 'DEAT', 'BURI']);
function townsOf(p) {
  const out = [];
  for (const f of p.facts || []) {
    if (!PLACE_FACTS.has(f.ty) || !f.place) continue;
    const t = String(f.place).split(',')[0].replace(/\s+Germany$/i, '').trim();
    if (t && !/\d/.test(t) && t.length <= 40) out.push(t);
  }
  return out;
}

const BAND_SPOUSE = new Set(['His wife', 'Her husband', 'His ex-wife', 'Her ex-husband', 'Partner', 'Her partner', 'His partner']);
function relsOf(p) {
  const v = p && p.rel;
  if (Array.isArray(v)) return v;
  if (typeof v !== 'string' || !v.trim()) return [];
  try { return JSON.parse(v.replace(/'/g, '"')); } catch { return []; }
}

/* ------------------------------------------------------------------------------------------------ membership */
const FAMS = cfg.families;
const memberKeys = (f) => ({
  reg: new Set((f.register || []).map(fold)),
  ids: new Set((f.register_ids || []).map(String)),
  eng: new Set((f.english || []).map(fold)),
});
const KEYS = new Map(FAMS.map((f) => [f.slug, memberKeys(f)]));

function regMembers(f) {
  const k = KEYS.get(f.slug);
  return register.people.filter((p) => !p.placeholder && (k.ids.has(String(p.id)) || k.reg.has(fold(surnameOf(p)))));
}
function engMembers(f) {
  const k = KEYS.get(f.slug);
  return english.people.filter((p) => k.eng.has(fold(p.name.split(/\s+/).pop())));
}
/* Which family page, if any, a surname belongs to. */
const FAMILY_OF_SURNAME = new Map();
for (const f of FAMS) {
  for (const s of [...(f.register || []), ...(f.english || [])]) FAMILY_OF_SURNAME.set(fold(s), f);
}
const pageOfFamily = (f) => u(`/families/${f.slug}/`);

/* ------------------------------------------------------------------------------------------------ tree entries */
const ENTRIES = [];
for (const g of tree.generations) {
  for (const e of g.people) {
    if (e.dates === 'Living') continue;          // the subject's own entry: a family page does not repeat it
    ENTRIES.push({ gen: g, e });
  }
}
function linkTarget(spec) {
  const [kind, val] = String(spec).split(/:(.*)/s);
  if (kind === 'id') { const p = BY_ID.get(val); return p ? { name: p.name, href: u(`/people/${p.slug}/`), id: val } : null; }
  if (kind === 'slug') { const p = BY_SLUG.get(val); return p ? { name: p.name, href: u(`/people/${p.slug}/`), slug: val } : null; }
  if (kind === 'href') return { name: null, href: u(val) };
  return null;
}
const STATUS_TAG = { documented: 'doc', probable: 'inf', inferred: 'inf', family: 'open', disputed: 'disp', unknown: 'open', excluded: 'disp' };
const STATUS_LABEL = Object.fromEntries(tree.legend.map((l) => [l.k, l.label]));
const STATUS_WHAT = Object.fromEntries(tree.legend.map((l) => [l.k, l.what]));

function treeGroups(f) {
  const toks = (f.tree || []).map(fold);
  const groups = [];
  for (const { gen, e } of ENTRIES) {
    const nm = ' ' + fold(e.name) + ' ';
    if (!toks.some((t) => nm.includes(' ' + t + ' '))) continue;
    let grp = groups.find((x) => x.gen === gen);
    if (!grp) { grp = { gen, label: gen.label, n: gen.n || '', entries: [] }; groups.push(grp); }
    grp.entries.push({
      name: e.name, dates: e.dates, place: e.place,
      status: e.status, statusLabel: STATUS_LABEL[e.status] || e.status, statusWhat: STATUS_WHAT[e.status] || '', tag: STATUS_TAG[e.status] || 'open',
      say: cfg.say[e.name] || [],
      links: (cfg.tree_links[e.name] || []).map(linkTarget).filter(Boolean),
    });
  }
  return groups;
}

/* ------------------------------------------------------------------------------------------------ the family */
const KIND = cfg.kind_labels;
function modelOf(f) {
  const reg = regMembers(f);
  const eng = engMembers(f);
  const livingReg = reg.filter(isLiving);
  const deadReg = reg.filter((p) => !isLiving(p));
  const placeholders = register.people.filter((p) => p.placeholder && fold(surnameOf(p)) === fold(f.name)).length;

  /* the tree's declared people, so the people list can say who is on the tree and who is elsewhere */
  const groups = treeGroups(f);
  const onTree = new Set();
  for (const g of groups) for (const en of g.entries) for (const l of en.links) { if (l.id) onTree.add(l.id); if (l.slug) onTree.add(l.slug); }

  const tile = (p) => {
    const towns = townsOf(p);
    const nread = READ.get(String(p.id)) || 0;
    return {
      name: p.name, href: `/people/${p.slug}/`, life: lifeOf(p),
      place: [towns[0], nread ? `${nread} record${nread === 1 ? '' : 's'} read` : ''].filter(Boolean).join(' · '),
      kind: p.kind, id: String(p.id), by: p.by, dy: p.dy,
    };
  };
  const regTiles = deadReg.map(tile);
  const regOnTree = regTiles.filter((t) => onTree.has(t.id));
  const regElsewhere = regTiles.filter((t) => !onTree.has(t.id));
  const elsewhereByKind = ['family', 'index', 'document']
    .map((k) => ({ kind: k, label: KIND[k], people: regElsewhere.filter((t) => t.kind === k) }))
    .filter((x) => x.people.length);

  const engRows = eng.map((p) => ({
    name: p.name, href: u(`/people/${p.slug}/`), dates: p.dates, grade: p.grade, why: p.why, slug: p.slug, gen: p.gen,
    gaps: p.gaps || [],
  }));

  /* years and places of the people who have died */
  const years = [];
  for (const p of deadReg) { if (p.by) years.push(p.by); if (p.dy) years.push(p.dy); }
  for (const p of eng) years.push(...yearsIn(p.dates));
  const born = [], died = [];
  for (const p of deadReg) { if (p.by) born.push(p.by); if (p.dy) died.push(p.dy); }
  for (const p of eng) { const ys = yearsIn(p.dates); if (ys.length) born.push(ys[0]); if (ys.length > 1) died.push(ys[ys.length - 1]); }
  const earliest = years.length ? Math.min(...years) : null;
  const latest = years.length ? Math.max(...years) : null;
  const townCount = new Map();
  for (const p of deadReg) for (const t of townsOf(p)) townCount.set(t, (townCount.get(t) || 0) + 1);
  const towns = [...townCount.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 6).map(([t, n]) => ({ town: t, n }));
  const treePlaces = groups.flatMap((g) => g.entries.map((en) => en.place)).filter(Boolean);

  /* the English line's relatives who have no page of their own: named in the archive's charts of a published
     person's kin (children, brothers and sisters, and parents of the name; spouses carry another name and are
     shown under the marriages that join the names). Born after 1940 (none is) would be counted and left off. */
  const have = new Set(eng.map((p) => p.slug));
  const surnameKeys = KEYS.get(f.slug).eng;
  const kin = new Map();
  let nHeld = 0;
  for (const p of english.people) {
    for (const rel of ['children', 'siblings', 'parents']) {
      for (const k of p.kin[rel] || []) {
        if (k.s && have.has(k.s)) continue;
        if (!surnameKeys.has(fold(String(k.n).split(/\s+/).pop()))) continue;
        const ys = yearsIn(k.dates);
        if (ys.length && ys[0] > 1940) { nHeld += 1; continue; }
        const key = k.n + '|' + (k.dates || '');
        const rl = (rel === 'children' ? 'child of ' : rel === 'parents' ? 'parent of ' : 'brother or sister of ') + p.name;
        const cur = kin.get(key) || { name: k.n, dates: k.dates || '', mark: k.mark || '', href: k.href ? u(k.href) : (k.s ? u(`/people/${k.s}/`) : null), rels: [] };
        if (!cur.rels.includes(rl)) cur.rels.push(rl);
        kin.set(key, cur);
      }
    }
  }
  const kinRows = [...kin.values()].sort((a, b) => (yearsIn(a.dates)[0] || 9999) - (yearsIn(b.dates)[0] || 9999) || a.name.localeCompare(b.name));

  /* the marriages that join this name to other names */
  const joins = new Map();
  const addJoin = (surname, a, b, note, line) => {
    const key = fold(surname);
    const fam = FAMILY_OF_SURNAME.get(key);
    if (fam && fam.slug === f.slug) return;
    const cur = joins.get(key) || { surname, family: fam ? { name: fam.name, href: pageOfFamily(fam) } : null, pairs: [] };
    const sig = [a.name, b.name].join('|');
    if (!cur.pairs.some((x) => x.sig === sig)) cur.pairs.push({ sig, a, b, note, line });
    joins.set(key, cur);
  };
  const myIds = new Set(reg.map((p) => String(p.id)));
  for (const p of deadReg) {
    for (const r of relsOf(p)) {
      if (!BAND_SPOUSE.has(String(r.rel))) continue;
      const o = BY_ID.get(String(r.id));
      if (!o || isLiving(o) || o.placeholder || myIds.has(String(o.id))) continue;
      const s = surnameOf(o);
      if (!s) continue;
      addJoin(s, { name: p.name, href: u(`/people/${p.slug}/`) }, { name: o.name, href: u(`/people/${o.slug}/`) },
        /ex-/.test(r.rel) ? 'the marriage ended' : '', onTree.has(String(p.id)));
    }
  }
  for (const p of eng) {
    for (const k of p.kin.spouses || []) {
      const s = String(k.n).split(/\s+/).pop();
      if (surnameKeys.has(fold(s))) continue;
      addJoin(s, { name: p.name, href: u(`/people/${p.slug}/`) },
        { name: k.n, href: k.s ? u(`/people/${k.s}/`) : null },
        [k.mar, k.mark].filter(Boolean).join(' · '), true);
    }
  }
  /* A marriage between two people the tree entries are about, or on the English line, is shown in full. A
     marriage among the other people of the name in the register (the surname index's Polish and German
     spouses) is counted and kept apart, under a heading that says what it is, so a long list of surnames
     cannot read as a list of families this one joined. */
  const split = (flag) => [...joins.values()]
    .map((j) => ({ ...j, pairs: j.pairs.filter((x) => !!x.line === flag) }))
    .filter((j) => j.pairs.length)
    .sort((a, b) => b.pairs.length - a.pairs.length || a.surname.localeCompare(b.surname));
  const joinRows = split(true);
  const joinOther = split(false);
  const nJoinOther = joinOther.reduce((n, j) => n + j.pairs.length, 0);

  /* spellings: declared, or the ones the names page already lists for a person */
  let forms = (f.forms || []).map((x) => ({ form: x, where: '' }));
  if (f.forms_from_names) {
    const pp = names.people.find((x) => x.canonical === f.forms_from_names.person);
    forms = (pp ? pp.forms : []).filter((x) => x.kind === f.forms_from_names.kind).map((x) => ({ form: x.form, where: x.where }));
  }

  if (f.forms_from_other) {
    const o = names.others.find((x) => x.name === f.forms_from_other);
    forms = (o ? String(o.forms).split(' \u00b7 ') : []).map((x) => ({ form: x.trim(), where: '' }));
  }

  /* the lanes this archive already keeps for the name */
  const set = f.lanes ? lines.sets.find((s) => s.name === f.lanes) : null;
  const lanes = set ? set.lanes.map((l) => ({ label: l.label, conf: l.conf, read: l.read, href: u(l.href) })) : [];

  const gradeCount = {};
  for (const g of groups) for (const en of g.entries) gradeCount[en.status] = (gradeCount[en.status] || 0) + 1;
  const nTree = groups.reduce((n, g) => n + g.entries.length, 0);
  const ORDER = ['documented', 'probable', 'inferred', 'family', 'disputed'];
  const gradeWords = [...ORDER, ...Object.keys(gradeCount).filter((k) => !ORDER.includes(k))]
    .filter((k) => gradeCount[k]).map((k) => `${gradeCount[k]} ${(STATUS_LABEL[k] || k).toLowerCase()}`).join(', ');
  const nDead = deadReg.length + eng.length;
  return {
    f, groups, onTree, regOnTree, regElsewhere, elsewhereByKind, engRows, kinRows, joinRows, joinOther, nJoinOther, forms, lanes,
    nDead, nReg: deadReg.length, nEng: eng.length, nLiving: livingReg.length, nHeld, placeholders,
    nDated: deadReg.filter((p) => p.by || p.dy).length + eng.filter((p) => yearsIn(p.dates).length).length,
    earliest, latest, towns, treePlaces, gradeCount, nTree, gradeWords,
    pages: (f.pages || []).map(([label, href]) => ({ label, href: u(href) })),
  };
}

const CACHE = new Map();
export function familyModel(slug) {
  if (!CACHE.has(slug)) CACHE.set(slug, modelOf(FAMS.find((x) => x.slug === slug)));
  return CACHE.get(slug);
}
export const familySlugs = () => FAMS.map((f) => f.slug);

/* Other surnames the register holds three or more people of, with no family page here. Counts only: nothing
   about the people. The living are not counted. */
export function otherSurnames(min = 3) {
  const have = new Set([...FAMILY_OF_SURNAME.keys()]);
  const c = new Map();
  for (const p of register.people) {
    if (p.placeholder || isLiving(p)) continue;
    const s = surnameOf(p);
    const k = fold(s);
    if (!k || have.has(k)) continue;
    const cur = c.get(k) || { surname: s, n: 0 };
    cur.n += 1;
    c.set(k, cur);
  }
  return [...c.values()].filter((x) => x.n >= min).sort((a, b) => b.n - a.n || a.surname.localeCompare(b.surname));
}

export { cfg, lifeOf };
