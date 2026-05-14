# Architecture — Mr. Bonzo Beats (Astro)

## Overview

Static Astro site (`output: "static"`). One primary page (`src/pages/index.astro`) composes sections as Astro components and wraps everything in `BaseLayout.astro`.

## Directory layout (high level)

| Area | Role |
|------|------|
| `src/pages/` | Routes; `index.astro` assembles the homepage. |
| `src/layouts/BaseLayout.astro` | Global HTML shell: meta, fonts, analytics, fixed BaseBox banner, fixed header/nav, mobile menu, **client-side i18n**, dynamic top padding. |
| `src/components/` | Page sections (Hero, player, playlists, releases, about, contact, footer, etc.). |
| `src/i18n/en.ts`, `src/i18n/el.ts` | Translation dictionaries (plain objects, default export). |
| `src/config/` | URLs, analytics constants, collaboration list. |
| `src/lib/` | Server-side helpers (e.g. Spotify/RSS) used at build time in `index.astro`. |
| `src/styles/global.css` | Tailwind import + shared typography / utility classes. |

## BaseLayout ↔ components

- `BaseLayout` renders a **slot** (`<slot />`) inside `<main>`. `index.astro` passes all section components into that slot.
- Header, banner, and i18n script live only in `BaseLayout`; section components do not repeat layout chrome.
- `BaseLayout` imports `en` and `el`, builds `const translations = { en, el }`, and passes it to an **inline** script via `define:vars={{ translations }}` so the browser receives a serialized JSON snapshot at build time.

## Fixed banner + header and dynamic padding

- **BaseBox banner** (`.basebox-banner`): `position: fixed; top: 0; left: 0; right: 0;` with a high `z-index` so it stays above the page.
- **Header** (`#main-header`): `position: fixed` with a separate high `z-index`, below the banner in stacking order.
- After paint, `adjustLayout()` (in `BaseLayout` inline script) measures the banner height, sets `header.style.top` to that height so the header sits **under** the banner, and sets `document.body.style.paddingTop` to `bannerHeight + headerHeight + 30` so content is not hidden under the fixed chrome.
- `resize` and delayed calls after language change re-run `adjustLayout()` so reflows from text length changes stay corrected.

## Client-side i18n script (`BaseLayout.astro`)

- **No framework hydration** for copy: Astro ships static HTML; a single inline script applies translations on the client.
- **Execution order**: The script is at the **end of `<body>`**. It runs synchronously after the DOM is parsed, then calls `applyTranslations()` and `adjustLayout()` immediately, before `window` `load` fires. The first paint may already include the server-rendered English defaults; `applyTranslations()` then aligns visible text with `localStorage` (`selected-lang`: `en` | `el`).
- **Normalization**: Invalid or legacy `localStorage` values are cleared and the UI falls back to English so a bad key cannot break the whole script.
- **Lookup**: String keys use dotted paths (`hero.label` → `dict.hero.label`). Missing keys fall back to the English dictionary to avoid empty nodes.
- **Attributes**: Besides `[data-i18n]` (inner HTML), the script updates `[data-i18n-alt]`, `[data-i18n-title]`, and `[data-i18n-aria-label]` for images, iframe titles, and icon buttons.
- **Persistence**: Choosing EL/EN writes `localStorage.setItem('selected-lang', …)`; on refresh, `normalizeLang()` reads it and `applyTranslations()` applies the correct dictionary. `document.documentElement.lang` is set to match the active locale.
- **View transitions**: If Astro view transitions are enabled later, `astro:page-load` re-runs `applyTranslations()`, `adjustLayout()`, and listener wiring.

## Build-time vs runtime data

- Spotify / RSS release data is fetched **at build time** in `index.astro` and passed into `DiscographySection` as props.
- UI strings for those dynamic titles (e.g. album names) remain proper nouns; translatable chrome uses `data-i18n` and the shared dictionaries.

## Performance & security (browser)

- **Images:** Hero logo uses `loading="eager"`, `fetchpriority="high"`, `decoding="async"`, and explicit `width`/`height` to reduce CLS. Header logo in `BaseLayout` is also eager + high priority. Below-the-fold images (About portrait, playlists, releases, drum kit art) use `loading="lazy"` and `decoding="async"` where applicable.
- **Beatstars iframe** (`FeaturedBeatstars.astro`): `loading="lazy"`, `fetchpriority="low"`, `referrerpolicy="strict-origin-when-cross-origin"`. (`decoding` is not a valid iframe attribute; use image tags for `decoding="async"`.)
- **Preconnect / DNS:** `BaseLayout` preconnects Beatstars, Google Tag Manager, Google Analytics, fonts (existing), plus `gc.zgo.at` for GoatCounter; GoatCounter script uses `https://` and `crossorigin="anonymous"`.
- **Fonts:** Google Fonts URL includes `&display=swap` (non-blocking text).
- **CSP & headers:** A **meta** `Content-Security-Policy` in `BaseLayout` allows `self`, required **`unsafe-inline`** scripts (gtag bootstrap + i18n), Google Analytics / GTM, `gc.zgo.at`, Beatstars `frame-src`, and broadened `connect-src` for analytics. **`public/_headers`** adds `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy` on hosts that honour it (e.g. Cloudflare Pages). Tighten CSP further at the edge if you move inline scripts to nonced bundles.
- **i18n XSS:** `applyTranslations()` uses **`textContent`** for all keys except an explicit allowlist (`drumkits.title`, `about.titleHtml`, `contact.title`) that ship trusted HTML from the repo. Alt/title/aria values are passed through **`safeAttr()`** (strips control chars and angle brackets).

## Automation: `git-save`

- **Command:** `npm run git-save -- "type: short description"` (implementation: `scripts/git-save.mjs`).
- **Flow:** `git add -A` → **documentation guard** (see `guardrails.md`) → optional **auto-stub** footer in `architecture.md` / `guardrails.md` when “impact” paths change without those files in the commit → `git commit` → `git push` for the **current branch**.
- **Audit log:** append-only lines in **`.git/git-save-doc-audit.log`** (local to the clone, not committed) describing whether docs were touched, bypassed, or assumed up-to-date.
- **Multi-branch:** optional `--sync-branches main,develop` merges current `HEAD` into each listed branch and pushes (manual conflict resolution if needed). Optional `--push-all` pushes every local branch that is **ahead** of its upstream.
- **Why Node:** one entrypoint that works on **Windows and Unix**, matching how this Astro repo is already driven via `npm`.
