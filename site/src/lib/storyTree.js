/* STORY MODE FOR THE PERSON PAGES (kit PERSON-PAGE-SPEC.md section 2a, ruled 4 November 2026; this archive 5 November 2026).

   WHAT IT DOES. Maps this archive's three kinds of person page (the register, the English line's twenty-six, the stubs for the line's
   other relatives) into the tree shape the kit's story functions read (kit lib/personstory.js: familyOf, ancestryOf, storyOf), and returns
   the stages of a life: where they came from, birth (with brothers and sisters), life, death, what they left behind, about the record.

   WHAT IT DOES NOT DO.
   - It writes no word about anyone. A chapter is a line of the English line's own hand-written life (data/english-people.json `facts`),
     moved as it stands: its date, its heading, its detail, the grade the line gave it. The register has no written life, so a register
     page's story is only its family (parents, grandparents, brothers and sisters, children, who they married) from the register's own
     relationship edges. Nothing is inferred, summarised or softened.
   - It sets no sex. A parent whose sex the record does not hold is a «Parent», not a Father or a Mother.
   - It never draws a living person's life. Who is living is the kit's rule (isLiving, isHeldOut) and the generator's flag, whichever is stricter;
     `storyFor` returns null for a living page, and a living relative inside a story is a name and a relationship (kit famNode).
     At build time `assertAgree` fails the build if the kit's rule, run over this tree, disagrees with the register's own flags.
   - A death year is shown only where the register's `died` is itself a date. «not documented; deported to Auschwitz 26 February 1943»
     is not a death year, so the card prints the register's words as they stand and no year of its own.

   THE LINKS. Every card links to the person's own page at /people/<slug>/ (the slug is the id of that very person, never derived from a name),
   and carries the kit's link mark with the word the chart used: «family tree, unverified» for a register edge; «a record read here» or
   «inferred» for an English-line edge, as the line wrote it. The line's own wording of a link («banns read», «probably the other couple's»,
   «half-brother») follows the dates on the card, because the chart's note, where it was kept, is not drawn in story mode. */
import register from '../data/register.json';
import english from '../data/english-people.json';
import PS from '@daviddef/archive-kit/data/public-sources.json';
import { isLiving, placeIsAddressLike } from '@daviddef/archive-kit/lib/person.js';
import { familyOf, ancestryOf, famNode, storyOf, hasStory, livingOf, heldOutOf } from '@daviddef/archive-kit/lib/personstory.js';
import { registerPerson, englishPerson, isLivingRecord, kitDate, NOW } from './people.js';
import { STUBS, stubPerson, parseLine } from './englishKin.js';
import rootsLinks from '../../public/roots-links.json';

export const RULE = { now: NOW, sources: PS, heldIds: [] };
export const GRADE_SAY = { doc: 'Documented', inf: 'Read with care', disp: 'Corrected' };
const NEVER = /$^/;                         // storyOf's «about the archive» test: nothing here is sorted into it by its words

const yearOf = (s) => { const m = /\b(\d{4})\b/.exec(String(s || '')); return m ? Number(m[1]) : null; };
const circa = (s) => /^c\.? ?\d/.test(String(s || '').trim());
const rawHref = (slug) => `/people/${slug}/`;

/* ------------------------------------------------------------------------------------------------
   THE NODES: one per page, keyed by slug (the slugs are unique across the register, the line and the stubs).
   ------------------------------------------------------------------------------------------------ */
const NODE = Object.create(null);        // slug -> kit tree node
const KIND = Object.create(null);        // slug -> 'register' | 'english' | 'stub'
const EDGES = Object.create(null);       // slug -> { parents, spouses, children, siblings }: [{ slug, source, note }]
const ROOTS_ID = Object.create(null);    // slug -> the id Roots & Routes uses for the person
const DATES = Object.create(null);       // slug -> the card's dates as the source states them, where the kit's years would add or lose something
const OTHER_PARENTS = Object.create(null);

/* the place of birth the register gives, unless it is a street address or an institution (the kit's own test): a card names a place, not a house */
const birthPlace = (r) => { const f = (r.facts || []).find((x) => x.t === 'Birth' && x.place); return f && !placeIsAddressLike(f.place) ? f.place : ''; };
/* a placeholder (register.json `placeholder`) stands for nobody: the tree held a record for someone it could not name. It is still a relative the
   register names, so it is still linked (tools/check-living.py), but its card says what it is, in the words its own page uses, and it does not by
   itself make a page worth telling as a story. */
const PLACEHOLDER = new Set(register.people.filter((r) => r.placeholder === true).map((r) => r.slug));
const PLACEHOLDER_SAY = 'A placeholder: the source tree holds this record for someone it could not name.';
const sexOf = (s) => (s === 'M' ? 'm' : s === 'F' ? 'f' : 'u');
/* the English line's own word for the person («Derrick's great-grandmother»): the only sex it records */
const lineSex = (rel) => (/mother$/.test(String(rel || '')) ? 'f' : /father$/.test(String(rel || '')) ? 'm' : 'u');

function edgesFromRelations(rel) {
  const out = { parents: [], spouses: [], children: [], siblings: [] };
  for (const band of Object.keys(out)) {
    for (const row of rel[band] || []) {
      if (!row.slug) continue;
      const note = [...new Set([row.mark && row.mark !== 'his own page' ? row.mark : '', row.mar || '', row.half && !row.mark ? 'half-sibling' : ''].filter(Boolean))].join(' · ');
      out[band].push({ slug: row.slug, source: row.source, note });
    }
  }
  return out;
}

/* 1. THE REGISTER. The years the kit prints are the register's own, and only where its text is a date. */
for (const r of register.people) {
  const live = isLivingRecord(r);
  const diedOk = !r.died || kitDate(r.died) !== undefined, bornOk = !r.born || kitDate(r.born) !== undefined;
  NODE[r.slug] = {
    id: r.slug, given: r.name, sur: '', sex: sexOf(r.sex), line: null, href: rawHref(r.slug),
    by: live ? null : r.by || null, bye: !live && r.byq === 'circa',
    dy: live || !diedOk ? null : r.dy || null, dye: !live && r.dyq === 'circa',
    bp: live ? '' : birthPlace(r),
    saidLiving: live, dead: !r.no_death_recorded && !live,
    father: null, mother: null, kids: [], spouse: [],
  };
  KIND[r.slug] = 'register';
  ROOTS_ID[r.slug] = String(r.id);
  /* a born or died that is not itself a date is printed as the register wrote it, and no year stands in for it */
  if (!live && (!diedOk || !bornOk)) {
    const b = r.born ? String(r.born).trim() : '', d = r.died ? String(r.died).trim() : '';
    DATES[r.slug] = b ? `${b} – ${d}`.replace(/ – $/, ' –') : `– ${d}`;
  }
  EDGES[r.slug] = edgesFromRelations(registerPerson(r).person.relations);
}

/* 2. THE ENGLISH LINE'S TWENTY-SIX. Their dates are the line's own strings. */
for (const p of english.people) {
  const pl = parseLine(p.dates);
  NODE[p.slug] = {
    id: p.slug, given: p.name, sur: '', sex: lineSex(p.rel), line: null, href: rawHref(p.slug),
    by: yearOf(pl.born), bye: circa(pl.born), dy: yearOf(pl.died), dye: circa(pl.died), bp: '',
    dead: false, father: null, mother: null, kids: [], spouse: [],
  };
  KIND[p.slug] = 'english';
  ROOTS_ID[p.slug] = `E-${p.slug}`;
  DATES[p.slug] = p.dates || '';
  EDGES[p.slug] = edgesFromRelations(englishPerson(p).relations);
}

/* 3. THE STUBS: relatives the line names and gives no page. No sex, no place, only the dates the line gave. */
for (const s of STUBS) {
  NODE[s.slug] = {
    id: s.slug, given: s.name, sur: '', sex: 'u', line: null, href: rawHref(s.slug),
    by: yearOf(s.parsed.born), bye: circa(s.parsed.born), dy: yearOf(s.parsed.died), dye: circa(s.parsed.died), bp: '',
    dead: false, father: null, mother: null, kids: [], spouse: [],
  };
  KIND[s.slug] = 'stub';
  DATES[s.slug] = s.dates || '';
  EDGES[s.slug] = edgesFromRelations(stubPerson(s).relations);
}

/* A PAGE WHOSE OWN CORRECTION DENIES A RELATIONSHIP OR AN IDENTITY STAYS A CHART (register.json `corrections`).
   - A correction of a relationship («brother of Jacob»: not a brother, the dates forbid it) means the register's parent and sibling links
     for that person are the very thing the archive has disputed. A story would put the parentage first, as «Where they came from»,
     so that page is not told as a story; it stays the chart, with the correction under it.
   - A correction of identity («NOT A SECOND PERSON — the same man as 9500005, duplicated») means the page is a pointer to one person,
     not a life; it stays the chart.
   THE LINKS ARE NOT REMOVED from the other people's stories: every relative the register names is linked on the page, as the chart links
   them (tools/check-living.py fails a page that names a relative and does not link them). So another person's story still lists them as
   the register does, and this is the register's conflict with its own correction, reported to David, not a choice made here.
   Corrections of a date or an occupation change nothing. */
const REL_CORRECTION = /^(brother|sister|son|daughter|father|mother|parent|child|husband|wife|spouse|cousin|uncle|aunt|nephew|niece|identity)\b/i;
export const NO_STORY = new Set(register.people.filter((r) => (r.corrections || []).some((c) => REL_CORRECTION.test(c.field))).map((r) => r.slug));

/* The parent links. A parent of known sex fills father or mother; a parent of unknown sex is kept apart and shown as a «Parent». */
for (const slug of Object.keys(NODE)) {
  const n = NODE[slug], e = EDGES[slug];
  OTHER_PARENTS[slug] = [];
  for (const x of e.parents) {
    const par = NODE[x.slug];
    if (!par) continue;
    if (par.sex === 'm' && !n.father) n.father = par.id;
    else if (par.sex === 'f' && !n.mother) n.mother = par.id;
    else OTHER_PARENTS[slug].push(x.slug);
  }
  n.kids = e.children.map((x) => x.slug).filter((s) => NODE[s]);
  n.spouse = e.spouses.map((x) => x.slug).filter((s) => NODE[s]);
}

/* THE BUILD FAILS, rather than draw the wrong page, if the kit's rule over this tree disagrees with the register: a person the generator
   published as not living must not be living or held out; a living person must be living; the line and the stubs are long dead. */
function assertAgree() {
  const bad = [];
  for (const r of register.people) {
    const living = livingOf(NODE, r.slug, RULE), live = isLivingRecord(r);
    if (live && !living) bad.push(`${r.slug}: the register says living, the kit's rule over the tree does not`);
    if (!live && (living || heldOutOf(NODE, r.slug, RULE))) bad.push(`${r.slug}: the register publishes this person, the kit's rule over the tree calls them living or held out`);
  }
  for (const slug of Object.keys(NODE)) if (KIND[slug] !== 'register' && (livingOf(NODE, slug, RULE) || heldOutOf(NODE, slug, RULE))) bad.push(`${slug}: a relative of the English line is called living or held out`);
  if (bad.length) throw new Error('storyTree.js: ' + bad.join('; '));
}
assertAgree();

/* ------------------------------------------------------------------------------------------------
   THE FAMILY of one person, from the kit's familyOf, completed from this archive's edges and given the cards' final words.
   ------------------------------------------------------------------------------------------------ */
const byBirth = (a, b) => ((NODE[a.id] && NODE[a.id].by) || 9999) - ((NODE[b.id] && NODE[b.id].by) || 9999);

function dress(n, from) {
  if (!n || n.unknown) return n;
  if (PLACEHOLDER.has(n.id)) n.place = PLACEHOLDER_SAY;
  if (!n.living && DATES[n.id] !== undefined && KIND[n.id] !== 'register') n.dates = DATES[n.id];
  if (!n.living && KIND[n.id] === 'register' && DATES[n.id]) n.dates = DATES[n.id];
  const edge = from && (['parents', 'spouses', 'children', 'siblings'].map((b) => EDGES[from][b].find((x) => x.slug === n.id)).find(Boolean));
  if (edge && !n.living) {
    if (edge.note) n.dates = [n.dates, edge.note].filter(Boolean).join(' · ');
    const grade = edge.source === 'read' ? 'doc' : edge.source === 'inferred' ? 'inf' : edge.source === 'tree' ? 'tree' : null;
    if (grade) n.link = { relation: '', grade };
  }
  return n;
}

function familyFor(slug) {
  const fam = familyOf(NODE, slug, RULE);
  if (!fam) return null;
  const e = EDGES[slug];
  // a parent whose sex the record does not hold stands as a Parent; the empty Father / Mother cards would then say a gap that is not one
  const others = OTHER_PARENTS[slug].map((id) => famNode(NODE, id, 'Parent', '', RULE)).filter(Boolean);
  if (others.length) fam.parents = [...fam.parents.filter((x) => !x.unknown), ...others];
  /* BROTHERS AND SISTERS, CHILDREN AND SPOUSES ARE ONLY THE LINKS A PAGE STATES (the chart's rule; englishKin.js «NO LINK IS INFERRED»).
     The kit's familyOf also finds a brother or sister as anyone sharing a parent, which would give a stub the brothers and sisters of
     its brother, and would call a half-brother a brother; here they come from the edges alone, in the words the page gave them. */
  const listed = (band, rel) => e[band].filter((x) => NODE[x.slug] && x.slug !== slug)
    .map((x) => famNode(NODE, x.slug, rel, '', RULE)).filter(Boolean);
  fam.siblings = listed('siblings', 'Brother or sister').sort(byBirth);
  fam.children = listed('children', 'Child').sort(byBirth);
  fam.spouses = listed('spouses', 'Married to');
  for (const list of [fam.parents, fam.siblings, fam.children, fam.spouses]) list.forEach((n) => dress(n, slug));
  fam.grand.forEach((n) => dress(n, null));
  return fam;
}

/* Is this page in Roots & Routes? (tools/build-tree-page.py writes public/roots-links.json) */
export const rootsIdOf = (slug) => ROOTS_ID[slug] || null;
export const inRoots = (slug) => !!ROOTS_ID[slug] && (rootsLinks.people || []).includes(ROOTS_ID[slug]);

/* THE ENGLISH LINE'S LIFE, as chapters: each fact is one card, in the line's order and words. The date and the heading lead the card
   and the detail follows as written. A fact the line graded «disp» is a note about the record (a correction, a name once merged,
   a sentence withdrawn), so it goes last and quiet under «About this record», not into the life. */
export function chaptersFromFacts(facts) {
  const life = [], about = [];
  for (const [when, what, detail, g] of facts || []) {
    const card = { title: '', body: `**${when}** · **${what}**\n\n${detail}`, grade: g === 'doc' || g === 'inf' || g === 'disp' ? g : null };
    (g === 'disp' ? about : life).push(card);
  }
  return { life, about };
}

/* THE STAGES for one page, or null when the page does not tell a life: a living page, or one whose story holds nothing but the empty first stop.
   `chapters` are the archive's own (the line's facts); `about` its notes on the record. */
export function storyFor(slug, { chapters = [], about = [] } = {}) {
  const n = NODE[slug];
  if (!n || NO_STORY.has(slug) || n.saidLiving || livingOf(NODE, slug, RULE)) return null;
  const fam = familyFor(slug);
  if (!fam) return null;
  const threads = ancestryOf(NODE, slug, null, RULE);
  threads.forEach((t) => { dress(t.parent, null); dress(t.earliest, null); t.between.forEach((b) => dress(b, null)); });
  // a page whose only relatives are placeholders has nothing to tell: it stays the chart
  const named = (list) => list.some((x) => x && !x.unknown && !PLACEHOLDER.has(x.id));
  if (!chapters.length && !named([...fam.parents, ...fam.grand, ...fam.siblings, ...fam.children, ...threads.map((t) => t.earliest)])) return null;
  const stages = storyOf(chapters, fam, [], {}, threads, { metaRx: NEVER });
  if (!hasStory(stages)) return null;
  // who they married: the kit's story has no stop for it, so it stands as the people of the Life stop (and makes a Life stop where there is none)
  const spouses = fam.spouses.map((s) => ({ name: s.name, dates: s.dates, place: s.place, href: s.href, rel: s.rel, living: s.living, link: s.link }));
  if (spouses.length) {
    let life = stages.find((x) => x.key === 'life');
    if (!life) {
      life = { key: 'life', label: 'Life', when: '', cards: [] };
      const at = Math.max(stages.findIndex((x) => x.key === 'birth'), stages.findIndex((x) => x.key === 'origin')) + 1;
      stages.splice(at, 0, life);
    }
    life.people = spouses; life.plabel = 'Married to';
  }
  if (about.length) {
    let ab = stages.find((x) => x.key === 'about');
    if (!ab) { ab = { key: 'about', label: 'About this record', when: '', cards: [], quiet: true }; stages.push(ab); }
    ab.cards.push(...about);
  }
  return stages;
}
