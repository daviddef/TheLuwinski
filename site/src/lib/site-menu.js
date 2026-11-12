/* THE WHOLE MENU, one list. 12 November 2026 (the menu regroup, PR A, MENU ONLY; the model is TheDefranceski PR #6): the six menus are still six,
   but the five other than Research are re-cut: Start, Our line, People, Places & families, The name. Research (lib/research-menu.js) is the sixth.
   The header menu and the drawer (layouts/Base.astro) both read THIS list, so there is one place to change a label or move a page.
   No page was renamed, no address changed, no page was edited: every href below is a page that was already built, only its menu moved.
     a menu is  [label, items]
     items     a flat list of [href, label]                          (a short menu: one column)
               or a list of groups { head, href?, items }            (a group is a column; `href` makes its heading a link)
     an item   [href, label], or { sub } for a small unlinked sub-head inside a column
   Hrefs are written without the trailing slash, as Base.astro writes them; "" is the home page.
   WHERE THE OLD ENTRIES WENT (docs/menu-a-moves.md is built from the two builds and is the proof):
     Start       The archive, The story stay. The tree, Roots & Routes, The Timeline -> People > Drawn. Nineteen forty-eight -> Our line.
                 What's new left Start: it is the head of the "What's new" group of Research (and the pulse button's page).
                 The DNA -> Research > Sources & method > Deep dives (the canon allows a local page there; kit/data/research-menu.json).
     The families  the index and Luwinski, Leibholz, Wear stay (Places & families). Thimm, Castle, Hawkins, Giddins, Larkin, Figueiredo,
                 Schmul, Bloom and Wallis left the menu; the /families/ index links every one of them (docs/menu-a-moves.md proves it).
     Places      -> Places & families.   People & names: The register, All the people, Blood relatives -> People; The lines of the name ->
                 Places & families; Her names -> The name.  Research is unchanged but for the Deep dives entry. */
import { navGroups } from "./research-menu.js";

/* Research, as lib/research-menu.js has it, with the one local deep dive added to the last column. This is the menu only: the /research/ hub and
   its group pages read RESEARCH directly and are not touched. */
const research = navGroups.map((g, i) =>
  i === navGroups.length - 1 ? { ...g, items: [...g.items, { sub: "Deep dives" }, ["/dna", "The DNA"]] } : g);

export const MENU = [
  ["Start", [["", "The archive"], ["/story", "The story"]]],
  ["Our line", [
    ["/derrick", "Derrick"], ["/leonard", "Leonard Wear"], ["/wear-line", "Where the Wear line stands"], ["/kurt", "Kurt"],
    ["/ivone", "Ivone"], ["/leibholz", "The Leibholz brothers"], ["/1948", "Nineteen forty-eight"],
  ]],
  ["People", [
    { head: "Lists", items: [["/people", "All the people"], ["/register", "The register"]] },
    { head: "Drawn", items: [["/tree", "The tree"], ["/roots", "Roots & Routes"], ["/timeline", "The Timeline"], ["/bloodline", "Blood relatives"]] },
  ]],
  ["Places & families", [
    { head: "The families", href: "/families", items: [["/families/luwinski", "Luwinski"], ["/families/leibholz", "Leibholz"], ["/families/wear", "Wear"]] },
    { head: "Places", items: [["/east-prussia", "East Prussia"], ["/mozambique", "Mozambique"], ["/australia", "Australia"], ["/atlas", "Atlas"], ["/lines", "The lines of the name"]] },
  ]],
  ["The name", [["/names", "Her names"]]],
  ["Research", research],
];
