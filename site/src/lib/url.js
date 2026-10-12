// Prefix a site-root path with the deployment base. Since 12 October 2026 the
// base is '/' and this returns the path unchanged; before that the site was a
// GitHub Pages project at /TheLuwinski and this is what made the links portable.
// IT IS KEPT, not inlined: it reads BASE_URL, so it is what makes the next move
// cost nothing.
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
export const u = (p = "/") => `${BASE}${p.startsWith("/") ? p : "/" + p}`;
