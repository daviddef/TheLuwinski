/* THE COUPLES AND THE HOUSEHOLDS this archive's own data holds, for /marriages/ and /households/ (23 November 2026).
 *
 * TWO SOURCES, KEPT APART. The register (data/register.json: the source family tree's people, each with a `rel` list of parents,
 * spouses, children and siblings, read by lib/kin.js) and the English line (data/english-people.json: hand-written ancestors, each
 * with a `kin` block; lib/englishKin.js gives the relatives that line names and never wrote a page for a page of their own). No
 * register person shares a name with an English-line person, so no couple is drawn twice. NOTHING IS JOINED: a couple is two people
 * whom one of this archive's records names as spouses, and a household is the children a record names under the same parents.
 *
 * WHAT IS NOT WRITTEN, because the data does not hold it. The register's marriage events (`MARR`) read «Marriage to:» and leave the
 * partner's name out, so a date belongs to a couple only where the data ties it:
 *   - the same date stands among BOTH partners' own marriage events (Kurt's 19 June 1948 is also Ivone's), or
 *   - one partner has exactly one spouse in the register and exactly one dated marriage event.
 * Anything else prints no date. A couple whose two single events disagree prints none, and says so.
 *
 * THE LIVING. A couple or household with a living person in it is drawn with names and nothing else: no date, no place, no note.
 * A household with a living child prints no date for anybody in it, because a parent's or a sibling's years beside a living
 * child's name are that child's age worked backwards. Pure of Astro; imports only data and this archive's own libraries. */
import register from '../data/register.json';
import english from '../data/english-people.json';
import { edgesOf, isoDate } from './kin.js';
import { isLivingRecord } from './people.js';
import { STUBS, stubFor } from './englishKin.js';

const BY_ID = new Map(register.people.map((r) => [String(r.id), r]));
const norm = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();
const yearOf = (s) => { const m = /\b(\d{4})\b/.exec(String(s ?? '')); return m ? Number(m[1]) : null; };
const pair = (a, b) => [String(a), String(b)].sort().join('|');

/* where a household comes from: the register's links, or the English line's. (The register's own `kind` field says which block of the register
   a PERSON is listed in, not how well a household is known, so it is not used as a «known from».) */
export const REG_WORD = 'The register';
export const EN_WORD = 'The English line';

/* the vocabulary a couple's row says how it is known in: key, label, chip class, note (the kit's Marriages draws the chips) */
export const CHIPS = [
  { k: 'cited', label: 'A record is cited', cls: 'doc', note: 'the register names a record for the marriage.' },
  { k: 'read', label: 'A record read here', cls: 'doc', note: 'the English line read the record.' },
  { k: 'inferred', label: 'Inferred', cls: 'inf', note: 'reasoned from other records, not stated in one.' },
  { k: 'tree', label: 'The family tree only', cls: 'lore', note: 'a source tree says so and names no record.' },
];

/* Who a line on the English line names, by an id: the page's own slug, a register person's slug (a few kin entries point at one), an address
   the line gave in `href` (/leonard/), or a stub's slug. `href` is where a card links; none for a person with no page. */
const REG_BY_SLUG = new Map(register.people.map((r) => [r.slug, r]));
const ENGLISH = new Map(english.people.map((p) => [p.slug, { name: p.name, slug: p.slug, href: `/people/${p.slug}/`, dates: p.dates || '' }]));
for (const s of STUBS) ENGLISH.set(s.slug, { name: s.name, slug: s.slug, href: `/people/${s.slug}/`, dates: s.dates || '' });
const kinId = (k) => {
  if (k.s) {
    if (!ENGLISH.has(k.s) && REG_BY_SLUG.has(k.s)) {
      const r = REG_BY_SLUG.get(k.s);
      ENGLISH.set(k.s, { name: r.name, slug: k.s, href: isLivingRecord(r) ? '' : `/people/${k.s}/` });
    }
    return k.s;
  }
  if (k.href) {
    const id = `href:${k.href}`;
    if (!ENGLISH.has(id)) ENGLISH.set(id, { name: norm(k.n), slug: id, href: k.href });
    return id;
  }
  return stubFor(k);
};

/* ============================================ the register's households ============================================ */
const spousesOf = (r) => (edgesOf(r.id) || { spouses: [] }).spouses;

/* THE PARKING NODES. The source tree hangs about a hundred surname-index people off nodes literally named «Germany Luwinski» and «UNKNOWN
   PLACEHOLDERS Luwinski» (pages/register.astro says so under "The surname index"), and gives each a placeholder wife («Unknown Luwinski»). They
   are not couples, and what hangs from them is not their children (the tree even makes Sally Leibholz a son of the second), so no couple and no
   household with one of them in it is drawn. A node is READ, not listed: a placeholder with ten or more children recorded under it, then any
   placeholder that is their spouse or has such a node among its children. «Unknown de Witt», with one daughter, is a real gap in a real
   household and stays. */
const kidsOf = (r) => (edgesOf(r.id) || { children: [] }).children;
const PARKING = new Set(register.people.filter((r) => r.placeholder && kidsOf(r).length >= 10).map((r) => String(r.id)));
for (let grew = true; grew;) {
  grew = false;
  for (const r of register.people) {
    if (!r.placeholder || PARKING.has(String(r.id))) continue;
    const linked = [...spousesOf(r), ...kidsOf(r)].some((x) => PARKING.has(String(x.other.id)));
    if (linked) { PARKING.add(String(r.id)); grew = true; }
  }
}
export const LEFT_OUT = { couples: 0, households: 0 };
const nSpouses = new Map(register.people.map((r) => [String(r.id), spousesOf(r).length]));

/* a child's parents are the people who list it as a child, and the parents it lists itself */
const regParents = new Map();
{
  const add = (c, p) => { if (!regParents.has(c)) regParents.set(c, new Set()); regParents.get(c).add(p); };
  for (const r of register.people) {
    const e = edgesOf(r.id); if (!e) continue;
    for (const c of e.children) add(String(c.other.id), String(r.id));
    for (const p of e.parents) add(String(r.id), String(p.other.id));
  }
}
const regKids = new Map();   // "idA|idB" or "idA" -> [child records]
for (const [cid, ps] of regParents) {
  const key = [...ps].sort().join('|');
  if (!regKids.has(key)) regKids.set(key, []);
  regKids.get(key).push(BY_ID.get(cid));
}

/* ============================================ the English line's households ============================================ */
const enParents = new Map(); const enInfo = new Map();
{
  const add = (c, p) => { if (!enParents.has(c)) enParents.set(c, new Set()); enParents.get(c).add(p); };
  for (const p of english.people) {
    for (const k of p.kin.children) {
      const s = kinId(k); if (!s) continue;
      add(s, p.slug); enInfo.set(s, { dates: norm(k.dates), mark: norm(k.mark) });
    }
    for (const k of p.kin.parents) { const s = kinId(k); if (s) add(p.slug, s); }
  }
}
const enKids = new Map();    // "slugA|slugB" or "slugA" -> [child slugs]
for (const [cs, ps] of enParents) {
  const key = [...ps].sort().join('|');
  if (!enKids.has(key)) enKids.set(key, []);
  enKids.get(key).push(cs);
}

/* ============================================ the couples ============================================ */
const dateKey = (d) => isoDate(d) || norm(d).toLowerCase();
const dated = (r) => (r.facts || []).filter((f) => f.ty === 'MARR' && norm(f.date));
const cited = (f) => !!(norm(f.c) || norm(f.ac));

function marriageOf(a, b) {
  const da = dated(a), db = dated(b);
  const ka = new Map(da.map((f) => [dateKey(f.date), f]));
  const both = [...new Set(db.map((f) => dateKey(f.date)).filter((k) => ka.has(k)))];
  const take = (f, g) => ({ when: norm(f.date), where: norm(f.place) || norm(g && g.place), cited: cited(f) || (g ? cited(g) : false) });
  if (both.length === 1) return take(ka.get(both[0]), db.find((f) => dateKey(f.date) === both[0]));
  const solo = (r) => (nSpouses.get(String(r.id)) === 1 && new Set(dated(r).map((f) => dateKey(f.date))).size === 1 ? dated(r)[0] : null);
  const sa = solo(a), sb = solo(b);
  if (sa && sb && dateKey(sa.date) !== dateKey(sb.date)) return { when: '', where: '', cited: false, conflict: true };
  const f = sa || sb;
  return f ? take(f) : { when: '', where: '', cited: false };
}

const regCouples = [];
{
  const seen = new Map();
  for (const r of register.people) {
    for (const { other, rel, mark } of spousesOf(r)) {
      const key = pair(r.id, other.id);
      if (PARKING.has(String(r.id)) || PARKING.has(String(other.id))) { if (!seen.has(key)) { seen.set(key, null); LEFT_OUT.couples++; } continue; }
      const ended = /ex-/.test(rel), partner = mark === 'partner';
      if (seen.has(key)) { const c = seen.get(key); if (c) { c.ended ||= ended; c.partner ||= partner; } continue; }
      const c = { key, a: r, b: other, ended, partner }; seen.set(key, c); regCouples.push(c);
    }
  }
}
const coupleOf = new Map(regCouples.map((c) => [c.key, c]));

/* the wording of the register's own relationship, for a note */
const noteOf = (c) => (c.partner ? 'Recorded as partners, not as married.' : c.ended ? 'The register calls the partner an ex-spouse.' : '');

const shapeRegister = (c) => {
  const [x, y] = c.a.sex === 'F' && c.b.sex === 'M' ? [c.b, c.a] : [c.a, c.b];
  const lx = isLivingRecord(x), ly = isLivingRecord(y), live = lx || ly;
  const m = live ? { when: '', where: '', cited: false } : marriageOf(c.a, c.b);
  const notes = live ? [] : [noteOf(c), m.conflict ? 'The two partners’ records each give one marriage date and the dates differ, so none is printed.' : ''].filter(Boolean);
  const kids = live ? [] : (regKids.get(c.key) || []);
  return {
    a: { name: x.name, slug: lx ? undefined : x.slug, living: lx },
    b: { name: y.name, slug: ly ? undefined : y.slug, living: ly },
    when: m.when, where: m.where, note: notes.join(' '), kids: kids.length || '',
    vias: live ? [] : [m.cited ? 'cited' : 'tree'],
    year: live ? null : yearOf(m.when),
    ended: !live && c.ended, living: live,
  };
};

const VIA = { read: 'read', inferred: 'inferred', tree: 'tree' };
const enCouples = [];
{
  const seen = new Set();
  for (const p of english.people) {
    for (const k of p.kin.spouses) {
      const slug = kinId(k);
      const key = [p.slug, slug || `${norm(k.n)}|${norm(k.dates)}`].sort().join('|');
      if (seen.has(key)) continue; seen.add(key);
      const other = slug ? ENGLISH.get(slug) : { name: norm(k.n), slug: undefined, href: '' };
      const when = norm(k.mar).replace(/^married\s+/i, '');
      const note = norm(k.mark);
      const kids = slug ? (enKids.get(pair(p.slug, slug)) || []) : [];
      enCouples.push({
        a: { name: p.name, slug: p.slug }, b: { name: other.name, slug: other.href && !String(other.slug).startsWith('href:') ? other.slug : undefined },
        when, where: '', note: note ? note[0].toUpperCase() + note.slice(1) + '.' : '', kids: kids.length || '',
        vias: [VIA[k.via] || 'tree'], year: yearOf(when), ended: false, living: false,
      });
    }
  }
}

export const COUPLES = [...regCouples.map(shapeRegister), ...enCouples];

/* ============================================ the households, drawn ============================================ */
const lifeSpan = (r) => (r.by && r.dy ? `${r.by}–${r.dy}` : r.by ? `b. ${r.by}` : r.dy ? `d. ${r.dy}` : '');
const maleFirst = (a, b) => (a.sex === 'M' ? 0 : 1) - (b.sex === 'M' ? 0 : 1);

const regRows = [...regKids.entries()].filter(([key]) => {
  const parking = key.split('|').some((id) => PARKING.has(id));
  if (parking) LEFT_OUT.households++;
  return !parking;
}).map(([key, kids]) => {
  const ps = key.split('|').map((id) => BY_ID.get(id)).sort(maleFirst);
  const live = ps.some(isLivingRecord) || kids.some(isLivingRecord);
  const [head, spouse] = ps;
  const couple = ps.length === 2 ? coupleOf.get(key) : null;
  const m = couple && !live ? marriageOf(couple.a, couple.b) : { when: '', where: '' };
  const link = (p) => (isLivingRecord(p) ? '' : `/people/${p.slug}/`);
  return {
    head: head.name, headHref: link(head), spouse: spouse ? spouse.name : '', spouseHref: spouse ? link(spouse) : '',
    married: m.when, where: m.where, via: REG_WORD,
    note: live ? '' : ps.length === 1 ? 'Only one parent is named in the register.' : (couple ? noteOf(couple) : ''),
    children: kids.sort((a, b) => (a.by ?? 9999) - (b.by ?? 9999) || a.name.localeCompare(b.name)).map((c) => {
      const lv = isLivingRecord(c);
      return { name: c.name, living: lv, href: lv ? '' : `/people/${c.slug}/`, dates: lv || live ? '' : lifeSpan(c) };
    }),
  };
});

const enRows = [...enKids.entries()].map(([key, kids]) => {
  const ps = key.split('|').map((s) => ENGLISH.get(s)).filter(Boolean);
  const [head, spouse] = ps;
  const couple = ps.length === 2 ? enCouples.find((c) => pair(c.a.slug, c.b.slug) === key) : null;
  return {
    head: head.name, headHref: head.href, spouse: spouse ? spouse.name : '', spouseHref: spouse ? spouse.href : '', _h: head, _s: spouse,
    married: couple ? couple.when : '', where: '', via: EN_WORD,
    note: ps.length === 1 ? 'Only one parent is named on the English line.' : (couple ? couple.note : ''),
    children: kids.map((slug) => ({ name: ENGLISH.get(slug).name, living: false, href: ENGLISH.get(slug).href, dates: (enInfo.get(slug) || {}).dates || '', note: (enInfo.get(slug) || {}).mark || '' }))
      .sort((a, b) => (yearOf(a.dates) ?? 9999) - (yearOf(b.dates) ?? 9999) || a.name.localeCompare(b.name)),
  };
});

/* Two people of one name head two households on the English line (three Joseph Wallises, two William Hawkinses): the dates the line gives
   follow the name where it would otherwise be the same on two cards. Nothing is joined by it; it says which page each card is. */
const nameCount = new Map();
for (const h of enRows) for (const n of [h.head, h.spouse].filter(Boolean)) nameCount.set(n, (nameCount.get(n) || 0) + 1);
const tell = (n, who) => (nameCount.get(n) > 1 && who && who.dates ? `${n} (${who.dates})` : n);
for (const h of enRows) {
  h.head = tell(h.head, h._h); h.spouse = h.spouse ? tell(h.spouse, h._s) : h.spouse;
  delete h._h; delete h._s;
}

export const HOUSEHOLDS = [...regRows, ...enRows];
