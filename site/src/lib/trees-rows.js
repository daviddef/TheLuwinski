/* THE ROWS OF /trees/ (23 November 2026). Written from the data this archive already holds and counted from it (data/tree.json, data/lines.json,
   data/family-lines.json); every sentence is the archive's own, taken from those files or from the cover page. This archive has no trees.json and
   invents none. They live here, not in the page, so the page holds no hand-written list of evidence (check:inline). Pure of Astro. */
import { u } from "./url.js";
import tree from "../data/tree.json";
import lines from "../data/lines.json";
import familyLines from "../data/family-lines.json";

const lanes = lines.sets.flatMap((s) => s.lanes);
const closed = lanes.filter((l) => l.parallel);
const kept = lanes.length - closed.length;
const sets = lines.sets.map((s) => `${s.name[0]}${s.name.slice(1).toLowerCase()}`);
const luw = familyLines.families.find((f) => f.id === "luwinski");
const leib = familyLines.families.find((f) => f.id === "leibholz");
const dnaGens = tree.generations.filter((g) => /^\d+$/.test(String(g.n)));

export const rows = [
  {
    name: "The line of record", ours: true, state: "drawn",
    depth: `documented ${leib.span[0]}–${luw.span[1]}`,
    what: "Kurt's family, carried on a name and documented from the 1870s: the Leibholz of Hammerstein and Schubin and the Luwinski and Thimm of the Ermland. The tree draws it as the other line, Derrick's by name and by upbringing, not by blood.",
    gap: "Joachim Luwinski's parents are known to nobody, and the Leibholz line begins at Hammerstein, not Schubin.",
    href: u("/tree/"), cta: "Open the tree →",
  },
  {
    name: "The line the DNA points to", ours: false, state: "drawn",
    depth: `${dnaGens.length} generations, Derrick at the foot`,
    what: "Derrick's ancestry as it now stands, every person graded on the five-word ladder: a Hertfordshire household called Wear, a Castle family at Baldock, and on his mother's side Figueiredo and Mota, from Portugal and Mozambique.",
    gap: "The last joint is not documented. No document yet joins the Wear line to him; only the DNA arithmetic does, and the tree marks that link inferred.",
    href: u("/tree/"), cta: "Open the tree →",
  },
  {
    name: "The lines of the name", ours: false, state: "web",
    depth: `${kept} lanes of ${sets.join(" and ")}, kept apart`,
    what: "Households that bear one of the family's two surnames, each on a lane of its own and joined to nothing until a document joins it. Drawn as what it is: a web of households, not a pedigree.",
    gap: "Real households of the name that belong to no lane yet are listed under each figure with the fact that would move them onto one.",
    href: u("/lines/"), cta: "Open the lanes →",
  },
  {
    name: "Households of the name that are not ours", ours: false, state: "closed",
    depth: `${closed.length} lanes: ${closed.map((l) => l.label.replace(/ — .*$/, "").replace(/\s*—.*$/, "")).join(", ")}`,
    what: "Followed, tested and shown not to belong: each is drawn on the lanes so that the next person who finds the name does not have to make the mistake again.",
    href: u("/lines/"), cta: "See why each is closed →",
  },
];
export const doors = [
  [u("/tree/"), "The tree", "Derrick's ancestry, graded on the five-word ladder, and the other line beside it."],
  [u("/lines/"), "The lines of the name", "Households kept apart on lanes until a document joins them."],
  [u("/bloodline/"), "Blood relatives", "Everyone one person is related to, drawn around a chosen person."],
  [u("/families/"), "The families", "A page for each surname line, with who bears the name and how well each link is known."],
];
