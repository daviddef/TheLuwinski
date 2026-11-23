/* THE RESEARCH MENU: one list, read by the header menu and the drawer (layouts/Base.astro), the hub page /research/ and its two group
   pages. 12 November 2026 (the research-menu pattern, as trialled on the Defranceski archive): the "Evidence" and "Investigations"
   menus became one "Research" menu with three groups, as David chose. NOTHING IS RENAMED AND NO ADDRESS MOVED: every item keeps the
   address it had, and the labels of the eight pages the estate's Evidence canon names (site/menu-canon.json) are unchanged.
   Addresses are written without the trailing slash, as Base.astro's own menu writes them. `asks` is the canon's question for the
   page; `atlas` marks the pages whose records are also on the Record Atlas, which carry an AtlasNote at the top.
   The group "What's new" is headed by /whats-new/, the page the kit already gives this archive. */
export const RESEARCH = [
  { id: "to-do", head: "To do", href: "/research/to-do",
    dek: "What is not known yet, what has been asked of other people, and what is being worked on.",
    items: [
      { href: "/open-questions", label: "Open Questions", asks: "What is not known, and what would settle it?" },
      { href: "/errands", label: "Errands", asks: "What has been asked of other people, or needs someone standing in a place?" },
      { href: "/worklist", label: "The work list", asks: "What is being done, by whom, since when?" },
    ] },
  { id: "whats-new", head: "What's new", href: "/whats-new",
    dek: "What was read, found and taken back lately, newest first, and the same record in full.",
    items: [
      { href: "/searched", label: "What Has Been Read", asks: "What was looked at, and what did it not turn up?", atlas: true },
      { href: "/corrections", label: "Corrections", asks: "What did this archive get wrong?" },
      { href: "/changes", label: "What changed", asks: "What happened, most recent first?" },
    ] },
  { id: "sources-and-method", head: "Sources & method", href: "/research/sources-and-method",
    dek: "What this archive stands on, how it reads a record, where every open thread stands, and the one study it has made of its own, the DNA.",
    items: [
      { href: "/sources", label: "Sources", asks: "What does this stand on, and where do I check?", atlas: true },
      { href: "/method", label: "Method", asks: "What would make you believe or not believe this?" },
      { href: "/status", label: "Status", asks: "Where does every open thread stand, and when did it last move?" },
      { href: "/dna", label: "The DNA", asks: "What the DNA says: a test the paper record set for itself, and failed." },
    ] },
];
/* the header menu's shape: [{ head, href, items: [[href, label]] }] */
export const navGroups = RESEARCH.map((g) => ({ head: g.head, href: g.href, items: g.items.map((x) => [x.href, x.label]) }));

/* THE DNA, AND NO "DEEP DIVES" HUB (23 November 2026, the leftovers). Earlier the same day the estate clean-up gave this menu a "Deep dives"
   sub-group whose heading linked to a hub page, /research/deep-dives/, listing the archive's own studies. It had ONE entry, The DNA, which is the
   only study this archive has built as a page of its own; a hub that lists one thing is not a hub. The kit's convention (kit/docs/menus.md) is one
   sub-group over a hub "listing every local study", and with one study that is the study itself: The DNA is an item of Sources & method, like any
   other page, and the old address /research/deep-dives/ still answers (astro.config.mjs sends it to /dna/). When a second study of this
   archive's own is built, the sub-group and the hub come back: put them here as { sub, href, items } and read them from lib/site-menu.js. */
