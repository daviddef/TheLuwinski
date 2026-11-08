/* THE RELATIVES THE ENGLISH LINE NAMES AND HAS NO PAGE FOR, GIVEN ONE (4 November 2026).

   data/english-people.json holds twenty-six hand-written people, and each lists their kin: a parent, a spouse, a
   child, a brother or a sister, with the dates the line gives and how the link is known (`via`: a record read, or
   inferred). Seventy-nine of those names have no page of their own (the line never wrote one), and the kit's chart
   draws no card that goes nowhere, so until now they were listed as «not drawn». Every person the archive names has
   a page (living standard, item 7), so each of them gets one here.

   WHAT A PAGE CAN HONESTLY SAY. Only what the line wrote: the name, the dates as it gave them, and each link to a
   person it did name, with how that link is known and the line's own wording («same household in 1851», «probably
   the other couple's», «half-brother»). Nothing is added: no sex, no place, no event, no record. A page of this
   kind is a stub and says so.

   WHO IS THE SAME PERSON. A relative named on several pages (a child on the page of each parent, and a sibling on
   the page of each brother or sister) is one person when the name AND the dates the line gave are the same, and
   never on the name alone: two Thomas Fields (a sibling baptised 1793, a father who died 1803) are two people, and
   so are the three Mary Hawkinses (born 1805, 1812 and 1861). A relative named with no dates on two pages is one
   person only when the same name is undated on both, which is the only case in the data.

   NO LINK IS INFERRED. A stub is linked to the people whose pages name it, by the link that page wrote, and to
   nobody else: a sibling is not given the sibling's other siblings, a child is not given a second parent that no
   page names. (The line lists a child on the page of each parent, so a child usually has both.) */
import english from '../data/english-people.json';
import register from '../data/register.json';
import { u } from './url.js';

const norm = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();
export const kinKey = (k) => `${norm(k.n).toLowerCase()}|${norm(k.dates).toLowerCase()}`;
const slugify = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^A-Za-z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();

const Y = '(c\\.? ?\\d{4}|\\d{4})';
const cy = (s) => s.replace(/^c\.? ?/, 'c. ');
/* The line's date strings: «1859–1890», «c.1783–1827», «b. 1883», «b. c.1823», «bapt. 1797», «bapt. 1783–1833», «d. 1803».
   A baptism is not a birth, so it is `baptised` and the chart prints no birth for it. Anything else is left as written, undated. */
export function parseLine(s) {
  const t = norm(s);
  let m;
  if ((m = new RegExp(`^${Y}[–-]${Y}$`).exec(t))) return { born: cy(m[1]), died: cy(m[2]) };
  if ((m = new RegExp(`^b\\. ${Y}$`).exec(t))) return { born: cy(m[1]) };
  if ((m = new RegExp(`^bapt\\. ${Y}[–-]${Y}$`).exec(t))) return { baptised: cy(m[1]), died: cy(m[2]) };
  if ((m = new RegExp(`^bapt\\. ${Y}$`).exec(t))) return { baptised: cy(m[1]) };
  if ((m = new RegExp(`^d\\. ${Y}$`).exec(t))) return { died: cy(m[1]) };
  return {};
}
const yearOf = (s) => { const m = /\d{4}/.exec(String(s || '')); return m ? Number(m[0]) : undefined; };

const BANDS = [['parents', 'parent'], ['spouses', 'spouse'], ['children', 'child'], ['siblings', 'sibling']];
/* what the page names the stub AS, for the table; and which of the stub's own bands that person goes in */
const INVERSE = { parents: 'children', spouses: 'spouses', children: 'parents', siblings: 'siblings' };
const AS = { parents: 'a parent', spouses: 'a spouse', children: 'a child', siblings: 'a brother or sister' };

const byKey = new Map();
for (const p of english.people) {
  for (const [band] of BANDS) {
    for (const k of p.kin[band]) {
      if (k.s || k.href) continue;
      const key = kinKey(k);
      if (!byKey.has(key)) byKey.set(key, { name: norm(k.n), dates: norm(k.dates), edges: [] });
      byKey.get(key).edges.push({
        of: { slug: p.slug, name: p.name, dates: p.dates }, band, via: k.via, mark: k.mark || undefined, mar: k.mar || undefined,
      });
    }
  }
}

/* A slug that no other page has: the register's, the English line's, and the other stubs'. */
const taken = new Set([...register.people.map((r) => r.slug), ...english.people.map((p) => p.slug)]);
export const STUBS = [...byKey.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([key, s]) => {
  const y = yearOf(s.dates);
  const base = `${slugify(s.name)}-${y ?? 'undated'}`;
  let slug = base, n = 2;
  while (taken.has(slug)) slug = `${base}-${n++}`;
  taken.add(slug);
  return { ...s, key, slug, parsed: parseLine(s.dates) };
});
const BY_KEY = new Map(STUBS.map((s) => [s.key, s]));
export const stubFor = (k) => (BY_KEY.get(kinKey(k)) || {}).slug;

/* The kit's person object for a stub. The relatives are the people whose pages name it, by the band the page put it in. */
export function stubPerson(stub) {
  const rel = { parents: [], spouses: [], children: [], siblings: [] };
  for (const e of stub.edges) {
    rel[INVERSE[e.band]].push({
      id: `english:${e.of.slug}`, name: e.of.name, href: u(`/people/${e.of.slug}/`), slug: e.of.slug, source: e.via,
      ...parseLine(e.of.dates), mar: e.mar, half: /half/i.test(e.mark || ''),
    });
  }
  const by = yearOf(stub.parsed.born);
  const lede = (() => {
    const names = (band) => stub.edges.filter((e) => e.band === band).map((e) => e.of.name);
    const nm = (a) => [...new Set(a)].join(' and ');
    if (names('children').length) return `Named on the English line as a child of ${nm(names('children'))}.`;
    if (names('spouses').length) return `Named on the English line as a spouse of ${nm(names('spouses'))}.`;
    if (names('parents').length) return `Named on the English line as a parent of ${nm(names('parents'))}.`;
    return `Named on the English line as a brother or sister of ${nm(names('siblings'))}.`;
  })();
  return {
    id: `english-kin:${stub.slug}`, name: stub.name, lede,
    born: stub.parsed.born, died: stub.parsed.died, birthYear: by,
    relations: rel,
  };
}

/* The wording a link carried that the chart cannot draw, for the note under it. */
export function stubNotes(stub) {
  return stub.edges.filter((e) => e.mark).map((e) => ({ name: e.of.name, text: e.mark }));
}
export const stubAs = (e) => AS[e.band];
export const VIA_WORD = { read: 'a record read', inferred: 'inferred, not stated' };
