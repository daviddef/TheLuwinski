#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Take the person pages out of site/.linkfloor.json after `checklinks.py --write-floor`.

    python3 ../tools/strip-linkfloor.py        # from site/ (what `npm run floor:links` runs)

kit/tools/checklinks.py writes one number per built page, and a person page's address is the person's name. The person pages
are not linked by the name linker at all (Base.astro's noAutolink puts data-no-autolink on their <main>: a chart of relatives
and the person's own name would otherwise be linked), so each counts 0 and a floor entry would only put the five living
people's page addresses into another committed file. A page absent from the floor is held to the kit's --new-page-max (3),
and a person page counts 0, so nothing is lost. Run after every --write-floor; check:links fails if a person page ever
starts to count.
"""
import json, io, sys, pathlib

p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".linkfloor.json")
d = json.load(io.open(p, encoding="utf-8"))
before = len(d["pages"])
d["pages"] = {k: v for k, v in d["pages"].items() if not k.startswith("/people/")}
io.open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
print("strip-linkfloor: %d person pages taken out, %d pages kept" % (before - len(d["pages"]), len(d["pages"])))
