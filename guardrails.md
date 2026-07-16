# Guardrails — UI, i18n, and layout

> **Last save:** 2026-07-16 13:54

Rules for future changes so the site stays consistent and flicker-free.

## 1. Internationalization keys

- Every **new user-visible string** must have a matching entry in **`src/i18n/en.ts` and `src/i18n/el.ts`** (same key path).
- Prefer dotted keys: `data-i18n="hero.label"`.
- HTML only via **`htmlKeys`** allowlist in `BaseLayout.astro` (`drumkits.title`, `about.titleHtml`, `contact.title`); otherwise `textContent`.

## 2. English defaults in `.astro` files (flicker / CLS)

- Default text between tags with `data-i18n` must match **`en.ts` exactly**.
- Same for `data-i18n-alt` / `data-i18n-title` / `data-i18n-aria-label`.

## 3. Client script expectations

- `localStorage['selected-lang']` only `en` | `el`.
- New translation attribute types require extending `applyTranslations()` in `BaseLayout.astro`.

## 4. Links and images

- **External social/store URLs** live in **`src/config/links.ts`** — do not hardcode Discord/TikTok/Spotify/Beatstars profile URLs in components when config already has them.
- Translatable link labels use `data-i18n`; proper nouns may stay locale-neutral.
- iframe titles: `data-i18n-title`.
- New scroll-in sections: add `section-reveal` on the outer section; respect `prefers-reduced-motion`.

## 5. Visual effects (do not regress)

- **Do not reintroduce** full-page custom cursor (dot/ring following the mouse site-wide) or **film grain** unless the user explicitly requests it.
- Keep **navbar-only** `#nav-hover-ring` (desktop fine pointer, ≥1024px); hide when leaving `#main-header`.
- Keep native browser cursor everywhere else (including Beatstars iframe).

## 6. Latest Releases

- Cards must stay **newest → oldest** (`sortReleasesNewestFirst`).
- Prefer Spotify API when credentials work; otherwise RSS/scrape.
- When API is broken or a brand-new album must show immediately, add it to **`pinnedReleases`** in `index.astro` with a real `releaseDate`, then `npm run save` + rebuild.

## 7. Z-index stacking

1. BaseBox banner (in-flow)
2. Sticky `#main-header` (and `#nav-hover-ring` above header chrome)
3. Main content

Document new overlay layers here if added.

## 8. Dangerous patterns to avoid

- No `/* … */` inside HTML tags in `.astro` (breaks attributes in built HTML).
- Prefer HTML comments outside tags or frontmatter notes.

## 9. `npm run save` workflow (required)

- Prefer **`npm run save -- "your message"`** over raw `git commit` / `git push`.
- The script **always** updates Last save stamps + the Save log in `architecture.md`.
- If behaviour/rules change, edit the prose in `architecture.md` / `guardrails.md` / `AGENTS.md` in the same session before save.
- Alias: `npm run git-save` (same script). See `architecture.md` → Automation for flags.

## 10. Security (CSP, third-party scripts, forms)

- Never add a third-party `<script src>` without updating CSP in `BaseLayout.astro` and noting it in `architecture.md`.
- Do not inject untrusted HTML into `en.ts` / `el.ts`.
- Contact forms (if added later): honeypot, server validation, rate limits.

## 11. Checklist (self-review)

- [ ] New copy in `en.ts` / `el.ts` + matching `.astro` defaults
- [ ] Links via `src/config/links.ts` where applicable
- [ ] `npm run build` succeeds
- [ ] Docs prose updated if behaviour changed
- [ ] Finished with `npm run save -- "…"`
