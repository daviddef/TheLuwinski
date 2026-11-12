# Menu regroup, PR A (menu only): nothing lost

12 November 2026, the Luwinski archive. Only the header menu and the drawer changed (site/src/lib/site-menu.js, read by layouts/Base.astro); no page, address or redirect was touched. The proof is three checks, all run on the build of clean clones of main (before) and of this branch (after), each built with the CI workflow's own steps:

1. **`menu-inventory-kit.py compare docs/menu-a-before.json DIST`**: every in-scope old address still answers and every text block that stood on it stands on the new site. Result: **NOTHING LOST** (48 in-scope pages: every menu address before or after, `/families/`, the Research pages, `/story/`).
2. **`menu-inventory-kit.py sitediff`**: all 354 pages of the site, old build against new: 354 before, 354 after, gone: none, new: none, **no page's text changed** (`docs/menu-text-changes.json` declares none).
3. **`tools/menu-moves.py`** (docs/menu-a-moves.md): every address that left a menu is linked, in its `<main>`, from a page that is still in a menu; every address in the new menu is a built page. 0 problems.

**A local patch of the kit tool, and the kit is not edited.** The kit's `compare` leaves every page whose address starts `/people/`, `/who/` or `/person/` out of its "somewhere on the new site" pool, the `/people/` index included, so the 265 rows of `/people/` read as lost even when a build is compared with itself. `tools/menu-inventory-kit.py` runs the kit's source with that one line changed to keep the `/people/` and `/who/` index pages in the pool (the pages below them stay out, as the kit intends), and asserts the line is still there, as TheMazza's `menus-a` does. With it a build compared with its own snapshot reads NOTHING LOST, and `/people/` is in the scope. The kit will be fixed separately after the rollout.

The table below is the kit's report for the in-scope pages. The "What only this page holds" column is empty where the page was not edited by the earlier Research-menu work.


| Page | Blocks before | after | Rows before | after | Links before | after | Answers now | What only this page holds |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `/` | 93 | 93 | 0 | 0 | 28 | 28 | page |  |
| `/1948/` | 68 | 68 | 29 | 29 | 16 | 16 | page |  |
| `/atlas/` | 36 | 36 | 23 | 23 | 11 | 11 | page |  |
| `/australia/` | 79 | 79 | 9 | 9 | 11 | 11 | page |  |
| `/bloodline/` | 14 | 14 | 5 | 5 | 2 | 2 | page |  |
| `/changes/` | 527 | 527 | 25 | 25 | 49 | 49 | page | The dated log of what was done. Unchanged. |
| `/corrections/` | 90 | 90 | 0 | 0 | 18 | 18 | page | The 23 claims taken back. Unchanged. |
| `/derrick/` | 35 | 35 | 0 | 0 | 7 | 7 | page |  |
| `/dna/` | 541 | 541 | 220 | 220 | 24 | 24 | page |  |
| `/east-prussia/` | 56 | 56 | 6 | 6 | 20 | 20 | page |  |
| `/errands/` | 108 | 108 | 18 | 18 | 10 | 10 | page | The letters out and the drafts. Unchanged. |
| `/families/` | 45 | 45 | 0 | 0 | 16 | 16 | page |  |
| `/families/bloom/` | 23 | 23 | 4 | 4 | 9 | 9 | page |  |
| `/families/castle/` | 48 | 48 | 16 | 16 | 17 | 17 | page |  |
| `/families/figueiredo/` | 33 | 33 | 5 | 5 | 14 | 14 | page |  |
| `/families/giddins/` | 38 | 38 | 10 | 10 | 10 | 10 | page |  |
| `/families/hawkins/` | 60 | 60 | 28 | 28 | 17 | 17 | page |  |
| `/families/larkin/` | 45 | 45 | 17 | 17 | 12 | 12 | page |  |
| `/families/leibholz/` | 91 | 91 | 17 | 17 | 43 | 43 | page |  |
| `/families/luwinski/` | 90 | 90 | 33 | 33 | 94 | 94 | page |  |
| `/families/schmul/` | 29 | 29 | 2 | 2 | 11 | 11 | page |  |
| `/families/thimm/` | 34 | 34 | 2 | 2 | 14 | 14 | page |  |
| `/families/wallis/` | 54 | 54 | 29 | 29 | 14 | 14 | page |  |
| `/families/wear/` | 62 | 62 | 22 | 22 | 20 | 20 | page |  |
| `/ivone/` | 220 | 220 | 31 | 31 | 23 | 23 | page |  |
| `/kurt/` | 304 | 304 | 46 | 46 | 51 | 51 | page |  |
| `/leibholz/` | 420 | 420 | 52 | 52 | 58 | 58 | page |  |
| `/leonard/` | 242 | 242 | 110 | 110 | 28 | 28 | page |  |
| `/lines/` | 101 | 101 | 0 | 0 | 26 | 26 | page |  |
| `/method/` | 113 | 113 | 16 | 16 | 27 | 27 | page | How the archive reads a record, and the rules it keeps. Unchanged. |
| `/mozambique/` | 83 | 83 | 9 | 9 | 5 | 5 | page |  |
| `/names/` | 77 | 77 | 47 | 47 | 14 | 14 | page | The stories of how each spelling hid a file; now headed by an AtlasNote. |
| `/open-questions/` | 42 | 42 | 0 | 0 | 13 | 13 | page | The ten open questions. Unchanged. |
| `/people/` | 267 | 267 | 301 | 301 | 298 | 298 | page |  |
| `/register/` | 163 | 163 | 177 | 177 | 176 | 176 | page |  |
| `/research/` | 14 | 14 | 0 | 0 | 12 | 12 | page |  |
| `/research/sources-and-method/` | 6 | 6 | 0 | 0 | 6 | 6 | page |  |
| `/research/to-do/` | 6 | 6 | 0 | 0 | 6 | 6 | page |  |
| `/roots/` | 71 | 71 | 11 | 11 | 0 | 0 | page |  |
| `/searched/` | 818 | 818 | 668 | 668 | 80 | 80 | page | The full account of each search and the bounded negatives; now headed by an AtlasNote. |
| `/sources/` | 84 | 84 | 0 | 0 | 42 | 42 | page | What was read from each source, and what has only been identified; now headed by an AtlasNote. |
| `/status/` | 139 | 139 | 79 | 79 | 8 | 8 | page | Every open thread and the date it last moved. Unchanged (now listed under Sources & method). |
| `/story/` | 160 | 160 | 0 | 0 | 56 | 56 | page |  |
| `/timeline/` | 160 | 160 | 0 | 0 | 2 | 2 | page |  |
| `/tree/` | 156 | 156 | 7 | 7 | 35 | 35 | page |  |
| `/wear-line/` | 84 | 84 | 5 | 5 | 18 | 18 | page |  |
| `/whats-new/` | 134 | 134 | 0 | 0 | 33 | 33 | page | The kit's What's new page; now also the head page of the What's new group. Unchanged. |
| `/worklist/` | 844 | 844 | 0 | 0 | 57 | 57 | page | The 280-row work list. Unchanged. |

New pages: `/research/` (built), `/research/to-do/` (built), `/research/sources-and-method/` (built), `/research/deep-dives/` (MISSING).

