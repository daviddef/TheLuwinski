/* THE WHOLE MENU, one list. 12 November 2026 (the menu regroup, PR A, MENU ONLY; the model is TheDefranceski PR #6): the six menus are still six,
   but the five other than Research are re-cut: Start, Our line, People, Places & families, The name. Research (lib/research-menu.js) is the sixth.
   The header menu and the drawer (layouts/Base.astro) both read THIS list, so there is one place to change a label or move a page.
   23 NOVEMBER 2026 (the estate clean-up, task C): the estate's labels, and the drawn pages behind one link. The labels are Booyzen's: Home, The People,
   The Register, The Name, The Atlas, The Lines, Blood relatives and Our line drawn on the Drawn page. "Roots & Routes" is gone (the Tree Canvas on
   recordatlas.org replaced it; /roots/ redirects to /tree/). People holds the two lists and ONE link, Drawn, to the hub /drawn/ (DRAWN below, which
   draws that page too). Places & families holds the places, "All the families" (the /families/ index) and the three families named in the menu.
     a menu is  [label, items]
     items     a flat list of [href, label]                          (a short menu: one column)
               or a list of groups { head, href?, items }            (a group is a column; `href` makes its heading a link)
     an item   [href, label], or { sub, href? } for a small sub-head inside a column (a link when it has an href)
   Hrefs are written without the trailing slash, as Base.astro writes them; "" is the home page.
   WHERE THE OLD ENTRIES WENT (docs/menu-a-moves.md is the 12 November proof, docs/menu-reach.md the 23 November one):
     Start       The archive is now Home. The tree, The Timeline, Blood relatives -> People > Drawn (the hub /drawn/). Nineteen forty-eight -> Our line.
                 What's new left Start: it is the head of the "What's new" group of Research (and the pulse button's page).
                 The DNA -> Research > Deep dives (a sub-group whose heading links to /research/deep-dives/).
     The families  "All the families" (the /families/ index) and Luwinski, Leibholz, Wear stay (Places & families). Thimm, Castle, Hawkins, Giddins,
                 Larkin, Figueiredo, Schmul, Bloom and Wallis left the menu on 12 November; the /families/ index links every one of them.
     Places      -> Places & families.   People & names: The register, All the people -> People; The lines of the name -> Places & families;
                 Her names -> The name.  Research is unchanged but for the Deep dives sub-group. */
import { navGroups, DEEP_DIVES } from "./research-menu.js";

/* Research, as lib/research-menu.js has it, with the Deep dives sub-group added to the last column: its heading links to the hub, and the
   hub lists the same items. This is the menu only: the /research/ hub and its group pages read RESEARCH directly. */
const research = navGroups.map((g, i) =>
  i === navGroups.length - 1
    ? { ...g, items: [...g.items, { sub: DEEP_DIVES.head, href: DEEP_DIVES.href }, ...DEEP_DIVES.items.map((x) => [x.href, x.label])] }
    : g);

/* THE DRAWN PAGES: what /drawn/ lists and the People menu reaches with one link. `blurb` is the one line each page gets on the hub. */
export const DRAWN = [
  { href: "/tree/", label: "Our line, drawn", blurb: "The ancestry as it now stands, every person graded on the five-word ladder." },
  { href: "/trees/", label: "The trees", blurb: "The lines this archive follows, each in the form its evidence supports: drawn as a line, drawn as a web, or followed and closed." },
  { href: "/bloodline/", label: "Blood relatives, drawn", blurb: "People joined by what this archive has read, drawn around a chosen person." },
  { href: "/timeline/", label: "The Timeline", blurb: "Every dated event in the archive's own record files, in order." },
];

export const MENU = [
  ["Start", [["", "Home"], ["/story", "The story"], ["/about", "About"]]],
  ["Our line", [
    ["/derrick", "Derrick"], ["/leonard", "Leonard Wear"], ["/wear-line", "Where the Wear line stands"], ["/kurt", "Kurt"],
    ["/ivone", "Ivone"], ["/leibholz", "The Leibholz brothers"], ["/1948", "Nineteen forty-eight"],
  ]],
  ["People", [
    { head: "Lists", items: [["/people", "The People"], ["/who", "Every Name"], ["/register", "The Register"], ["/households", "Households"], ["/marriages", "Marriages"]] },
    { head: "Drawn", href: "/drawn", items: [] },
  ]],
  ["Places & families", [
    { head: "Places", items: [["/east-prussia", "East Prussia"], ["/mozambique", "Mozambique"], ["/australia", "Australia"], ["/lines", "The Lines"], ["/atlas", "The Atlas"]] },
    { head: "The families", items: [["/families", "All the families"], ["/families/luwinski", "Luwinski"], ["/families/leibholz", "Leibholz"], ["/families/wear", "Wear"]] },
  ]],
  ["The name", [["/names", "The Name"]]],
  ["Research", research],
];
