#!/bin/sh
# THE RIBBON FLAGS TAKE NO ROOM (27 October 2026; kit/docs/ribbon-flags.md). The kit's box gate, checkflagfit.mjs, opens the BUILT
# pages in Chrome and measures every ribbon card with its mini flags and with them hidden, at 1440, 1100 and 390: a card one pixel
# taller or wider, or a strip that touches the glyph, "Gen. n", the name or the years, fails. Pages: /story/ and every family page
# that site/src/data/family-lines.json draws a ribbon on (its `page`). It serves site/dist itself on a local port and stops after.
#
# Needs playwright-core and an installed Google Chrome; neither is a dependency of this site (the kit says so too). CI installs
# playwright-core without saving it into the checkout's root node_modules (outside site/, ignored), where the kit's script finds it:
#   npm i --prefix . --no-save --no-package-lock --no-audit --no-fund playwright-core@1.63.0     (from the checkout's root)
# then: cd site && npm run check:flagfit. Exit 0 clean, 1 a card changed size or a strip touches a word, 2 it could not run
# (which fails CI: not run is not a pass).
set -e
cd "$(dirname "$0")/../site"
KIT=node_modules/@daviddef/archive-kit/kit/tools
DIST="${ARCHIVE_OUT:-dist}"
[ -f "$DIST/story/index.html" ] || { echo "  --    flagfit    not run: $DIST/story/index.html is missing (build first)"; exit 2; }
# A free port the system picks, unless one is given: a fixed port can be held by another server on the same machine, which
# would then answer for this build (it happened on 27 October 2026, and the first pages measured were not this archive's).
PORT="${FLAGFIT_PORT:-$(python3 -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1])")}"
python3 -m http.server "$PORT" --bind 127.0.0.1 -d "$DIST" > /dev/null 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT INT TERM
i=0
# Ready, and ours: the page served is byte for byte this build's (another server on the port would serve another page).
until python3 -c "import urllib.request, sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:$PORT/story/').read() != open('$DIST/story/index.html', 'rb').read())" 2>/dev/null; do
  i=$((i + 1)); [ $i -gt 50 ] && { echo "  --    flagfit    not run: the local server did not start"; exit 2; }
  kill -0 $SRV 2>/dev/null || { echo "  --    flagfit    not run: the local server exited (port $PORT taken?)"; exit 2; }
  sleep 0.2
done
URLS=$(python3 -c "
import json
pages = ['/story/'] + [f['page'] for f in json.load(open('src/data/family-lines.json'))['families'] if f.get('cards')]
print(' '.join('--url http://127.0.0.1:$PORT' + p for p in pages))")
# shellcheck disable=SC2086
node "$KIT/checkflagfit.mjs" $URLS --widths 1440,1100,390
node "$KIT/checkflagfit.mjs" --selftest
