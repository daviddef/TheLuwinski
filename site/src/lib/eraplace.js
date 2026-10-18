/* THE ONE DATED PLACE A FREE-TEXT LINE CAN GIVE: «11 September 1969, Johannesburg» -> { date: "11 September 1969", place: "Johannesburg" }.
   The English line's born / died strings are prose («Q1 1890, St Olave Southwark, aged 31», «1957, registered at Hitchin as ...»). Only a
   plain date, a comma and ONE place is read as a dated place-event for the «at the time» note (src/pages/people/[slug].astro); anything
   longer is left alone and gets no note. tools/build-era.py holds the SAME pattern (ENGLISH_LIFE) and `--check` fails if the two differ.

   The register's month-first dates («Nov 12 1807», the way the tree writes them) are turned into the day-first form the kit's plainYear
   reads. A date the page marks uncertain, or that is not one plain date, gives no year (plainYear refuses it). */
export const ENGLISH_LIFE = /^(\d{1,2} [A-Z][a-z]+ \d{4}|\d{4}),\s+([A-Z][A-Za-z' -]+)$/;

export function lifePlace(text) {
  const m = ENGLISH_LIFE.exec(String(text ?? ''));
  return m ? { date: m[1], place: m[2] } : null;
}

const MONTH_FIRST = /^([A-Za-z]{3,9})\.?\s+(\d{1,2})\s+(\d{4})$/;
export const dayFirst = (d) => {
  const t = String(d ?? '').trim().replace(/\s+/g, ' ');
  const m = MONTH_FIRST.exec(t);
  return m ? `${m[2]} ${m[1]} ${m[3]}` : t;
};
export const yearOf = (d) => {
  const m = /(\d{4})$/.exec(String(d ?? '').trim());
  return m ? Number(m[1]) : null;
};
