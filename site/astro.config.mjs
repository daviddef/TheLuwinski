import { defineConfig } from 'astro/config';

// GitHub Pages project site: https://daviddef.github.io/TheLuwinski
// Change `base` to '/' and `site` to the domain if this moves to a custom domain.
/* 9 October 2026. Three pages folded into pages that do the same job, and their published
   addresses stay alive: Letters out is the Errands page (the whole page, chase schedule and
   all), the Research log is What changed, and Bounded negatives is a section of What has
   been read. */
const redirects = {
  '/letters': '/TheLuwinski/errands/',
  '/research-log': '/TheLuwinski/changes/',
  '/negatives': '/TheLuwinski/evidence/#negatives',
};

export default defineConfig({
  site: 'https://daviddef.github.io',
  base: '/TheLuwinski',
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
