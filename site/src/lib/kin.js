/* A person's family, out of register.json, for the kit's PersonTree.
 *
 * WHY THE RELATIONSHIP WORDS ARE READ AND NOT THE SHAPE. register.json gives each
 * person a `rel` list of { id, rel } where rel is the relationship FROM THE
 * SUBJECT'S SIDE and gendered — "His father", "Her son", "Her ex-husband". There
 * are 22 phrasings across 149 people and all 22 are mapped below, so an
 * unrecognised one is a person NOT DRAWN rather than a person drawn in the wrong
 * band. Anything unmapped is counted and returned, so the page can say so.
 *
 * A DATE MUST CONTAIN A DIGIT. Jacob Leibholz's died field reads "not documented;
 * deported" — true, and the prose belongs on the page rather than in a chart node,
 * where it would sit exactly where a date goes and read as one. The same rule cost
 * two other archives a «b. -» and a «b. living» this week.
 *
 * EVERY NODE CARRIES AN HREF, since 16 October 2026: every person in the register has a page of
 * their own at /people/<slug>/ (src/pages/people/[slug].astro), the living included, so a name in a
 * chart leads somewhere. Until then this archive had no per-person route and no node linked.
 */
import register from "../data/register.json";
import { u } from "./url.js";

const BY_ID = new Map(register.people.map((p) => [String(p.id), p]));

const BAND = new Map(Object.entries({
  "His father": "parents", "Her father": "parents",
  "His mother": "parents", "Her mother": "parents", "Her parent": "parents",
  "His wife": "spouses", "Her husband": "spouses",
  "His ex-wife": "spouses", "Her ex-husband": "spouses",
  "Partner": "spouses", "Her partner": "spouses", "His partner": "spouses",
  "His son": "children", "Her son": "children",
  "His daughter": "children", "Her daughter": "children", "Daughter": "children",
  "His brother": "siblings", "Her brother": "siblings",
  "His sister": "siblings", "Her sister": "siblings",
  "Half brother": "siblings", "Half sister": "siblings",
}));

/* The register stores these as Python-repr strings in some rows and as real arrays
   in others. Both are read; neither is guessed at. */
function rels(p) {
  const v = p && p.rel;
  if (Array.isArray(v)) return v;
  if (typeof v !== "string" || !v.trim()) return [];
  try {
    return JSON.parse(v.replace(/'/g, '"'));
  } catch {
    return [];
  }
}

const digit = (s) => /\d/.test(String(s || ""));
/* Several died fields carry a place after the date — "14 March 2010, at home at
   Rua Nova das Marinhas 82, Gulpilhares" — which is the page's business and not a
   chart node's. The date is the part before the first comma, kept only if the
   trimmed head still carries a digit. */
function head(s) {
  const v = String(s || "").trim();
  if (!v) return "";
  const h = v.split(",")[0].trim();
  return digit(h) ? h : (digit(v) ? v : "");
}

function span(p) {
  const b = head(p.born), d = head(p.died);
  if (b && d) return `${b} – ${d}`;
  if (b) return `b. ${b}`;
  if (d) return `d. ${d}`;
  return "";
}

const MARK = {
  "His ex-wife": "the marriage ended", "Her ex-husband": "the marriage ended",
  "Half brother": "half brother", "Half sister": "half sister",
  "Partner": "partner", "Her partner": "partner", "His partner": "partner",
};

/* The address of a register person's own page, or undefined for an id the register does not hold. */
export function pageOf(id) {
  const p = BY_ID.get(String(id));
  return p && p.slug ? u(`/people/${p.slug}/`) : undefined;
}

/* THE EDGES OF ONE REGISTER PERSON, UNDRAWN: [{ other, rel, mark }] per band, for the shared person page
   (src/lib/people.js), which hands them to the kit's PersonChart as rows with fields rather than as
   strings. `familyOf` below is the old shape, kept for /kurt/, /ivone/ and /derrick/, which still draw
   their own chart. Same band table, same reading of `rel`; an edge the table does not know, or to a
   record that is not in the register, is counted in `unmapped` and not drawn. */
export function edgesOf(id) {
  const me = BY_ID.get(String(id));
  if (!me) return null;
  const out = { parents: [], spouses: [], children: [], siblings: [], unmapped: [] };
  for (const r of rels(me)) {
    const band = BAND.get(String(r && r.rel));
    const other = BY_ID.get(String(r && r.id));
    if (!band || !other) { out.unmapped.push({ rel: String(r && r.rel), id: String(r && r.id) }); continue; }
    out[band].push({ other, rel: String(r.rel), mark: MARK[String(r.rel)] });
  }
  return out;
}

/* { self, parents, spouses, children, siblings, unmapped } for one register id.
   `datesOff` draws EVERY node without a date: a living person's own page names their relatives and
   their relationship and nothing else, and a dead parent's life span beside a living child's name is
   the child's age worked backwards. */
export function familyOf(id, { livingSelf = false, datesOff = false } = {}) {
  const me = BY_ID.get(String(id));
  if (!me) return null;
  const out = { parents: [], spouses: [], children: [], siblings: [], unmapped: [] };
  for (const r of rels(me)) {
    const band = BAND.get(String(r && r.rel));
    const other = BY_ID.get(String(r && r.id));
    if (!band || !other) {
      out.unmapped.push({ rel: String(r && r.rel), id: String(r && r.id) });
      continue;
    }
    /* A LIVING RELATIVE IS DRAWN WITH A NAME AND NO DATES, AND SAYS SO. The register
       already holds no dates for them; the explicit test is so that a future row that
       did could not reach a chart. Derrick (`bare`) is drawn exactly as he was. */
    const alive = other.living === true;
    out[band].push({
      name: other.name,
      href: pageOf(other.id),
      dates: alive || datesOff ? "" : span(other),
      mark: (alive ? ["living", MARK[String(r.rel)]].filter(Boolean).join(" · ") : MARK[String(r.rel)]) || undefined,
      title: String(r.rel),
    });
  }
  return {
    self: { name: me.name, dates: livingSelf || datesOff ? "" : span(me),
            note: livingSelf ? "living — named only" : "", noteCls: livingSelf ? "living" : "" },
    ...out,
  };
}

/* An ISO 8601 date (or partial date) from a register date string, or undefined where the string is not a
   plain date: «Mar 11 1941», «15 December 1968», «Mar 1941» and «1941». A bounded or approximate date
   («Before 1955») is never given to structured data; the caller passes nothing for those. */
const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
export function isoDate(s) {
  const v = String(s || "").trim();
  let m;
  const mm = (t) => MONTHS[String(t).slice(0, 3).toLowerCase()];
  const pad = (n) => String(n).padStart(2, "0");
  if ((m = /^(\d{4})$/.exec(v))) return m[1];
  if ((m = /^([A-Za-z]{3,9}) (\d{1,2}) (\d{4})$/.exec(v)) && mm(m[1])) return `${m[3]}-${pad(mm(m[1]))}-${pad(m[2])}`;
  if ((m = /^(\d{1,2}) ([A-Za-z]{3,9}) (\d{4})$/.exec(v)) && mm(m[2])) return `${m[3]}-${pad(mm(m[2]))}-${pad(m[1])}`;
  if ((m = /^([A-Za-z]{3,9}) (\d{4})$/.exec(v)) && mm(m[1])) return `${m[2]}-${pad(mm(m[1]))}`;
  return undefined;
}
