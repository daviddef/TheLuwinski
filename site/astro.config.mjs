import { defineConfig } from 'astro/config';

// THE RULE NOW: this site is served from its OWN DOMAIN at
// https://luwinski.defranceski.com, so `base` is '/' and every internal link is
// root-relative. THE RULE BEFORE, until 12 October 2026: it was a GitHub Pages
// PROJECT site at https://daviddef.github.io/TheLuwinski and `base` was
// '/TheLuwinski'. The line that used to stand here was a DIRECTION — "change
// base to '/' and site to the domain if this moves" — and a direction becomes
// false the moment somebody follows it, so it is replaced with the state rather
// than deleted. The old address still works: GitHub 301-redirects
// daviddef.github.io/TheLuwinski to this domain.
// AND site/public/CNAME IS LOAD-BEARING: .github/workflows uploads site/dist, and
// any deploy whose output carries no CNAME DETACHES the custom domain.
/* 9 October 2026. Three pages folded into pages that do the same job, and their published
   addresses stay alive: Letters out is the Errands page (the whole page, chase schedule and
   all), the Research log is What changed, and Bounded negatives is a section of What has
   been read. */
const redirects = {
  '/letters': '/errands/',
  '/research-log': '/changes/',
  '/negatives': '/searched/#negatives',
  /* 9 October 2026: the estate's address for this page is /searched/. */
  '/evidence': '/searched/',
};

export default defineConfig({
  site: 'https://luwinski.defranceski.com',
  base: '/',
  redirects,
  /* WHY outDir IS A VARIABLE, and why the default must stay 'dist'.
     Several sessions build this estate at once, and `astro build` EMPTIES its
     outDir before it refills it — so one session's build wipes the tree
     another session's gates are reading, and the gates report a torrent of
     absences that are simply not copied yet. The kit's tools all honour
     ARCHIVE_OUT and, when they refuse a shared build, print «build to a
     directory of your own: ARCHIVE_OUT=...» as the way out. WITHOUT THIS LINE
     THAT HATCH CANNOT BE TAKEN: the variable redirected every reader and
     nothing that writes. Found 27 September 2026, after the kit had been
     printing that advice for four days.
     THE DEFAULT MUST STAY 'dist' — .github/workflows uploads `path: site/dist`,
     so changing it here would publish nothing. */
  outDir: process.env.ARCHIVE_OUT || 'dist',

  build: { format: 'directory' },
});
