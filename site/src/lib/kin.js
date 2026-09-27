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
 * NO NODE CARRIES AN HREF. This archive has no per-person route, so a name in a
 * chart is a name and not a broken promise of a page.
 */
import register from "../data/register.json";

const BY_ID = new Map(register.people.map((p) => [String(p.id), p]));

const BAND = new Map(Object.entries({
  "His father": "parents", "Her father": "parents",
  "His mother": "parents", "Her mother": "parents", "Her parent": "parents",
  "His wife": "spouses", "Her husband": "spouses",
  "His ex-wife": "spouses", "Her ex-husband": "spouses",
  "Partner": "spouses", "Her partner": "spouses",
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
  "Partner": "partner", "Her partner": "partner",
};

/* { self, parents, spouses, children, siblings, unmapped } for one register id. */
export function familyOf(id, { livingSelf = false } = {}) {
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
    out[band].push({
      name: other.name,
      dates: span(other),
      mark: MARK[String(r.rel)] || undefined,
      title: String(r.rel),
    });
  }
  return {
    self: { name: me.name, dates: livingSelf ? "" : span(me),
            note: livingSelf ? "living — named only" : "", noteCls: livingSelf ? "living" : "" },
    ...out,
  };
}
