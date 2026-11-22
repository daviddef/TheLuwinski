# The menu, and what can still be reached (estate clean-up, 23 November 2026)

Proof that no page was lost from reach when Roots & Routes was retired and the People and Research menus were simplified. Method: the kit's
`menu_inventory.py` through `tools/menu-inventory-kit.py` (this archive's wrapper), run on the build of `origin/main` (before) and the build of
this branch (after), each built with the CI chain; `check:pages` was run with `--estate` pointing at the estate root, because an isolated worktree
cannot see its sibling archives.

## Header menu links, before and after (distinct addresses linked from the home page's menu)

| Menu | Before | After |
|---|---:|---:|
| Start | 2 | 2 |
| Our line | 7 | 7 |
| People | 6 | 3 |
| Places & families | 9 | 9 |
| The name | 1 | 1 |
| Research | 13 | 14 |
| **Total** | **38** | **36** |

Labels now follow the estate's (Booyzen's): The archive is **Home**, All the people is **The People**, The register is **The Register**, Her names is
**The Name**, Atlas is **The Atlas**, The lines of the name is **The Lines**. Where a page was already listed under a group heading ("The families"), that
heading now carries an explicit **All the families** link beside Luwinski, Leibholz and Wear. People holds the two lists and one link, **Drawn**
(`/drawn/`). Research keeps the eight core pages in the three groups and ends with one **Deep dives** sub-group whose heading links to
`/research/deep-dives/`.

## Where each page that left a menu is reached from

| Page | Left | Reached from |
|---|---|---|
| `/tree/` | People > Drawn (4 links) | `/drawn/` (card "Our line, drawn"), the book, `/families/` |
| `/bloodline/` | People > Drawn | `/drawn/` (card "Blood relatives, drawn"), the book |
| `/timeline/` | People > Drawn | `/drawn/` (card "The Timeline"), the book |
| `/roots/` | People > Drawn | retired on purpose: now a redirect stub to `/tree/` (noindex, not in the sitemap); its text is not kept (see below) |
| the nine smaller family pages | left the menu on 12 November | `/families/` (linked from the menu as "All the families"); unchanged since |

Every address that answered before still answers: 354 pages before, 356 after, none gone, `/drawn/` and `/research/deep-dives/` new
(`menu_inventory.py sitediff`). Every in-scope old URL still resolves (`menu_inventory.py compare`). Every text block that stood on an in-scope page stands somewhere on the new site,
except the 71 blocks of `/roots/` (the retired page's own viewer text; the viewer itself is still served bare at `/roots/view.html`) and two counters on
`/changes/` that moved from 235 to 236 entries. Each changed page is declared with its reason in `docs/menu-text-changes.json`.

## Addresses the 22 November crawl reported as 404

`/trees/`, `/direct-line/` and `/contents/`. This archive's menu never linked any of them: they are the estate's shared routes, which the crawl
tried on every archive. `/contents/` does exist and answers 200 (the book's table of contents). `/trees/` and `/direct-line/` are pages this archive
does not have and does not need (its tree is `/tree/`); none was created.

## Estate pages this archive does not have (not created; each would need a decision)

About, Every Name, Households, Marriages, The trees, Places (an index of places). `/atlas/` and the three place pages stand in for the last.
