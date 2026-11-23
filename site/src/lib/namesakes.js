/* THE OTHER PEOPLE WHO CARRY THE SAME NAME, as a person's page draws them (one page per person; 23 November 2026).
 *
 * David's rule: one page per person, and each person's page links to the other people who carry the same name. This
 * archive never had /who/<name>/ pages, so it needs the one half of the rule: the section "Others of the same name"
 * (#others-of-this-name) on the pages of people whose name another page also carries. This file is the one place that
 * says who shares a name; src/components/OthersOfThisName.astro draws it; tools/checknamesakes.py checks the BUILT pages
 * against it from the pages' own headings, not from this file.
 *
 * WHO IS COMPARED: every person who has a page (the register, the English line, and the relatives the English line
 * names and has no page for, src/lib/englishKin.js). A NAME is the full name with accents and case folded and every
 * run of other characters read as one space ("Johannes Antonie Oelofse De Witt" and "... de Witt" are the one name).
 *
 * WHO IS LEFT OUT, both ways (a page neither lists anyone nor is listed):
 *   - a PLACEHOLDER ("Unknown", "Unknown Luwinski", "Unknown de Witt"): the source tree holds a record for someone it could
 *     not name, so there is no name to share. Linking nine of them as "people of this name" would say something false.
 *   - a LIVING person (the generator's `living` or `bare` flag, as lib/people.js isLivingRecord): a living person is named
 *     with their relationships and a town and nothing more, their page draws no section, and no page links to theirs
 *     that did not before. Nobody living shares a name with anybody today; the rule is kept so that it stays true.
 *
 * NOTHING IS JOINED. A shared name is no evidence of one person (the English line keeps two Thomas Fields, three Mary
 * Hawkinses, and says so); the section lists the others as different pages and says this archive joins two only on a record.
 * The one pair the register itself calls ONE person entered twice (Johannes Antonie Oelofse de Witt, corrected 9500160 ->
 * 9500005) carries a note saying so, read from that correction and not written here.
 *
 * Pure of Astro; imports only data. */
import register from '../data/register.json';
import english from '../data/english-people.json';
import { STUBS } from './englishKin.js';
import { isLivingRecord } from './people.js';
import { u } from './url.js';

export const SECTION_ID = 'others-of-this-name';

export const slugify = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^A-Za-z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();

const KIND = {
  family: 'In the family tree this archive was built from',
  index: 'Listed in the register’s surname index',
  document: 'Found in a register, in nobody’s tree',
};

const yearOf = (s) => { const m = /\b(\d{4})\b/.exec(String(s ?? '')); return m ? Number(m[1]) : null; };

/* "NOT A SECOND PERSON — the same man as 9500005, duplicated": the register's own identity correction names the other entry */
const SAME = /same (?:man|woman|person) as (\d+)/i;
const sameAs = new Map();   // register id -> Set of the register ids a correction reads as the same person
for (const r of register.people) {
  for (const c of r.corrections || []) {
    const m = c.field === 'identity' && SAME.exec(String(c.now || ''));
    if (!m) continue;
    for (const [a, b] of [[String(r.id), m[1]], [m[1], String(r.id)]]) {
      if (!sameAs.has(a)) sameAs.set(a, new Set());
      sameAs.get(a).add(b);
    }
  }
}

/* every person with a page who can share a name: { slug, name, life, how, rid } */
export const PEOPLE = [
  ...register.people
    .filter((r) => !r.placeholder && !isLivingRecord(r))
    .map((r) => ({
      slug: r.slug, name: r.name, rid: String(r.id),
      life: [r.born, r.died].filter(Boolean).join(' – '),
      how: KIND[r.kind] || '',
    })),
  ...english.people.map((p) => ({ slug: p.slug, name: p.name, rid: null, life: p.dates || '', how: 'On the English line, with a page of its own' })),
  ...STUBS.map((s) => ({ slug: s.slug, name: s.name, rid: null, life: s.dates || '', how: 'Named on the English line' })),
];

/* name key -> the people who carry it */
export const SETS = new Map();
for (const p of PEOPLE) {
  const k = slugify(p.name);
  if (!k) continue;
  if (!SETS.has(k)) SETS.set(k, []);
  SETS.get(k).push(p);
}

/* oldest first (the first four-digit year of the life), those with no year after, then slug order */
const byAge = (a, b) => (yearOf(a.life) ?? 99999) - (yearOf(b.life) ?? 99999) || (a.slug < b.slug ? -1 : a.slug > b.slug ? 1 : 0);

/* the others of the page `slug`: [] when nobody shares its name (and for a living person, a placeholder, or a slug with no entry) */
export function othersFor(slug) {
  const me = PEOPLE.find((p) => p.slug === slug);
  if (!me) return [];
  const same = me.rid ? sameAs.get(me.rid) : null;
  return (SETS.get(slugify(me.name)) || [])
    .filter((q) => q.slug !== slug)
    .sort(byAge)
    .map((q) => ({
      name: q.name, slug: q.slug, href: u(`/people/${q.slug}/`), life: q.life, how: q.how,
      note: same && q.rid && same.has(q.rid) ? 'A correction on the register reads this entry and the one on this page as one person, entered twice.' : '',
    }));
}

/* the figures the pull request quotes: shared names, and the pages that carry the section */
export const sharedSets = () => [...SETS.values()].filter((v) => v.length > 1);
