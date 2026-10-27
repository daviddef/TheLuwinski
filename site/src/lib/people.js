/* THE ADAPTER FROM THIS ARCHIVE'S DATA TO THE KIT'S PERSON OBJECT (PERSON-PAGE-SPEC.md, section 2).
   Used only by src/pages/people/[slug].astro. Pilot of the shared people page, 17 October 2026.

   WHAT IT DOES NOT DO, deliberately: it sets no `living` or `presumedLiving` flag (the kit does not read
   one), it passes no pre-formatted date to a relative (the kit ignores `dates`), and it derives no
   address from a name (every `href` is the id of that very person, from register.json's slug).

   WHO IS LIVING. The decision is made where it always has been: tools/build-register.py asks
   tools/people_decisions.py, which asks the kit's one definition (kit/tools/living_rule.py), with the
   private harvest in hand, and writes the answer into register.json as `living` (four people) or `bare`
   (the subject). That is the generator's output, not a hand-set flag. The page cannot recompute it,
   because the register withholds a living person's birth year BY DESIGN (it is a date of birth). So, for
   those five records only, the adapter passes the kit rule's own `saidLiving: true` (the JavaScript twin
   of living_rule.py's `said_living`): the archive's statement, from its generator, that the person is
   living. No year is invented. See `agreeWithGenerator` below, which is the safety net.

   FOR EVERYONE ELSE the adapter passes only fields the register publishes (born, died, dead,
   citations, the children's birth years) and `agreeWithGenerator` runs the kit's rule over them at
   build time and THROWS if it calls any of them living or held out. A person the generator published
   as not living must be not living by the kit's JavaScript rule too; if they are not, the build fails
   instead of drawing the wrong page. (tools/check-living.py re-applies the Python rule to the same
   public fields in CI and still does.) */
import evidence from '../data/evidence.json';
import PS from '@daviddef/archive-kit/data/public-sources.json';
import { parseDate, isLiving, isHeldOut } from '@daviddef/archive-kit/lib/person.js';
import { edgesOf, pageOf } from './kin.js';
import register from '../data/register.json';
import { u } from './url.js';

export const NOW = new Date().getFullYear();
const BY_ID = new Map(register.people.map((p) => [String(p.id), p]));

/* The generator's classification: `living` (four people) or `bare` (the subject, named with his
   parents and nothing else). `bare` is the archive's one exception, set by tools/people_decisions.py
   NAMED_BARE; nothing here widens it. */
export const isLivingRecord = (r) => r.living === true || r.bare === true;

/* A date the kit can print, or undefined. The register holds some dates the kit's parser cannot read
   (prose after a comma, a bound such as «Before 1955», «June 28 1877?», a bare «MAY 1942, at ...»):
   those stay in the record section as the register wrote them, and the header and chart print none.
   The kit prints an unparseable string as written, which would put «not documented; deported» where a
   date goes. */
export function kitDate(text) {
  const t = String(text ?? '').trim();
  if (!t) return undefined;
  if (parseDate(t).ok) return t;
  const head = t.split(',')[0].trim();
  if (parseDate(head).ok) return head;
  let m;
  if ((m = /^Q[1-4] (\d{4})$/.exec(head))) return m[1];                 // a quarter's index entry: the year
  if ((m = /^c\.(\d{4})$/.exec(head))) return `c. ${m[1]}`;
  return undefined;
}

/* Has a recorded death or burial (dated or not): the source tree marks them deceased, or a death date
   is given. The register keeps `no_death_recorded` for people the tree does not mark deceased. */
const deadRecorded = (r) => !r.no_death_recorded;

const citationsOf = (r) =>
  (r.facts || []).filter((f) => !String(f.t || '').trim().endsWith(':'))
    .flatMap((f) => [f.c, f.ac]).filter(Boolean);

/* What the kit's rule needs from a record that is not living, all of it published. */
function publicFields(r) {
  return {
    born: kitDate(r.born), died: kitDate(r.died), dead: deadRecorded(r),
    birthYear: r.by ?? undefined, citations: citationsOf(r),
  };
}

const livingParent = (r) => {
  const e = edgesOf(r.id);
  return !!e && e.parents.some((x) => isLivingRecord(x.other));
};
const youngestChildYear = (r) => {
  const e = edgesOf(r.id);
  const ys = e ? e.children.map((x) => x.other.by).filter(Boolean) : [];
  return ys.length ? Math.max(...ys) : undefined;
};

/* One relative, as the kit's PersonChart takes it. */
function row(other, rel, mark, { source = 'tree', quiet = false } = {}) {
  const live = isLivingRecord(other);
  return {
    id: other.id, name: other.name, href: pageOf(other.id), slug: other.slug || undefined, source,
    ...(live ? { saidLiving: true } : { ...publicFields(other), parentLiving: livingParent(other) || undefined }),
    /* ON A LIVING PERSON'S PAGE no relative carries a date. This archive's gate (tools/check-living.py) fails
       any year on such a page, because a dead parent's life span beside a living child's name is the child's
       age worked backwards; the kit's chart would print a dead relative's years there. So the fields the
       chart prints are dropped and `birthYear` stays, which only the living rule reads. */
    ...(quiet && !live ? { born: undefined, died: undefined } : {}),
    // «the marriage ended» and «partner» are said above a spouse; a half-sibling goes in the chart's note
    mar: ['His ex-wife', 'Her ex-husband'].includes(rel) ? 'the marriage ended'
       : mark === 'partner' ? 'partner' : undefined,
    half: /^Half /.test(rel),
  };
}

export function registerPerson(r) {
  const live = isLivingRecord(r);
  const e = edgesOf(r.id);
  const rows = (band) => e[band].map(({ other, rel, mark }) => row(other, rel, mark, { quiet: live }));
  const read = [];
  for (const x of evidence.people.filter((q) => q.register_id === r.id))
    for (const rec of x.records) if (!read.some((q) => q.title === rec.title)) read.push(rec);
  const person = {
    id: r.id, name: r.name,
    ...(live ? { saidLiving: true, town: r.town || '', country: r.country || '', place: r.place || '' }
             : { ...publicFields(r), parentLiving: livingParent(r) || undefined, youngestChildYear: youngestChildYear(r) }),
    relations: { parents: rows('parents'), spouses: rows('spouses'), children: rows('children'), siblings: rows('siblings') },
    ...(live ? {} : { events: r.facts || [], sources: read.map((x) => x.title) }),
  };
  return { person, read, unmapped: e.unmapped.length };
}

/* The safety net described at the top. Throws; never returns a verdict to be ignored. */
export function agreeWithGenerator(r, person) {
  if (isLivingRecord(r)) return;
  const rule = { now: NOW, sources: PS };
  if (isLiving(person, rule))
    throw new Error(`people.js: the register publishes id ${r.id} as not living but the kit's rule calls them living; fix the data or the generator, do not draw this page`);
  if (isHeldOut(person, { ...rule, heldIds: [], parentLiving: person.parentLiving === true }))
    throw new Error(`people.js: the kit's rule holds id ${r.id} out, yet the register publishes them`);
}

/* ---------------------------------------------------------------------------------------------
   THE ENGLISH LINE: twenty hand-written ancestors (data/english-people.json), all long dead.
   --------------------------------------------------------------------------------------------- */
const base = import.meta.env.BASE_URL.replace(/\/$/, '');

/* The relatives carry pre-formatted strings («1859–1890», «b. 1883», «b. c.1823»). The kit takes
   fields and ignores strings, so they are read back into born and died; anything else is left undated. */
function datesFromString(s) {
  const t = String(s || '').trim();
  let m;
  if ((m = /^(c\.? ?\d{4}|\d{4})[–-](c\.? ?\d{4}|\d{4})$/.exec(t))) return { born: m[1].replace(/^c\.? ?/, 'c. '), died: m[2].replace(/^c\.? ?/, 'c. ') };
  if ((m = /^b\. (c\.? ?\d{4}|\d{4})$/.exec(t))) return { born: m[1].replace(/^c\.? ?/, 'c. ') };
  return {};
}

export function englishPerson(p) {
  const row = (k, via) => ({
    name: k.n, source: via || k.via,
    href: k.href ? base + k.href : k.s ? u(`/people/${k.s}/`) : undefined,
    slug: k.s || undefined,
    ...datesFromString(k.dates),
    mar: k.mar || undefined,
    mark: k.mark || undefined,
  });
  const k = p.kin;
  const person = {
    id: `english:${p.slug}`, name: p.name, gen: p.gen, lede: `${p.rel}. ${p.dek}`,
    born: kitDate(p.born), died: kitDate(p.died),
    relations: {
      parents: k.parents.map((x) => row(x)), spouses: k.spouses.map((x) => row(x)),
      children: k.children.map((x) => row(x)), siblings: k.siblings.map((x) => row(x)),
    },
  };
  return person;
}

/* The wording an English-line edge carried and the kit's chart cannot draw (it prints only the source
   word): «banns read», «probably the other couple's», «half-brother». Listed under the chart instead of
   dropped, so nothing the page said is lost. «his own page» is a link, which the chart keeps. */
export function lineNotes(person) {
  const out = [];
  for (const [band, label] of [['parents', 'parent'], ['spouses', 'spouse'], ['children', 'child'], ['siblings', 'sibling']])
    for (const r of person.relations[band]) {
      if (r.mark && r.mark !== 'his own page') out.push({ name: r.name, label, text: r.mark });
      else if (r.half) out.push({ name: r.name, label, text: 'half-' + label });
    }
  return out;
}

/* The half-siblings of a register person, for the same note. */
export function halfSiblings(person) {
  return person.relations.siblings.filter((r) => r.half).map((r) => r.name);
}
