// Prefix a site-root path with the deployment base, so the same links work at
// https://daviddef.github.io/TheLuwinski/ and at a custom domain later.
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
export const u = (p = "/") => `${BASE}${p.startsWith("/") ? p : "/" + p}`;
