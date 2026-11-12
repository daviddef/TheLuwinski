/* One sentence for each Research page: what it asks, and a number the archive can state from its own data. Counted at build time, so
   it cannot go stale. 12 November 2026 (the research-menu pattern). Pages with no honest single number (Method, Status, What changed)
   carry only their question. */
import openQuestions from "../data/open-questions.json";
import letters from "../data/letters.json";
import worklist from "../data/worklist.json";
import searched from "../data/searched.json";
import register from "../data/register.json";
import sources from "../data/sources.json";
import book from "../data/book.json";
import { RESEARCH } from "./research-menu.js";

const nf = (n) => n.toLocaleString("en-GB");
const wl = worklist.rows;
const open = wl.filter((r) => r.state === "next" || r.state === "running").length;
const COUNT = {
  "/open-questions": `${nf(openQuestions.rows.length)} open questions`,
  "/errands": `${nf(letters.rows.length)} letters out, ${nf(letters.drafts.length)} drafts waiting`,
  "/worklist": `${nf(open)} still open, ${nf(wl.filter((r) => r.state === "done").length)} done`,
  "/searched": `${nf(searched.rows.length)} records and files examined`,
  "/corrections": `${nf(register.corrections.length)} claims taken back`,
  "/sources": `${nf(sources.groups.reduce((n, g) => n + g.rows.length, 0))} sources`,
};
const BLURB = Object.fromEntries(
  [book.front, ...book.parts].flatMap((p) => p.chapters).map((c) => [c.path.replace(/\/$/, ""), c.blurb]));
const ASKS = Object.fromEntries(RESEARCH.flatMap((g) => g.items).filter((x) => x.asks).map((x) => [x.href, x.asks]));

export const blurbOf = (x) => {
  const asks = ASKS[x.href] || BLURB[x.href] || "";
  const n = COUNT[x.href];
  return [asks, n ? `<em>${n}.</em>` : ""].filter(Boolean).join(" ");
};
