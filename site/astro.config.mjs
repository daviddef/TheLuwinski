import { defineConfig } from 'astro/config';

// GitHub Pages project site: https://daviddef.github.io/TheLuwinski
// Change `base` to '/' and `site` to the domain if this moves to a custom domain.
export default defineConfig({
  site: 'https://daviddef.github.io',
  base: '/TheLuwinski',
  build: { format: 'directory' },
});
