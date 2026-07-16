# Architecture — Mr. Bonzo Beats (Astro)

## Overview

Static Astro site (`output: "static"`). One primary page (`src/pages/index.astro`) composes sections as Astro components and wraps everything in `BaseLayout.astro`.

## Directory layout (high level)

| Area | Role |
|------|------|
| `src/pages/` | Routes; `index.astro` assembles the homepage. |
| `src/layouts/BaseLayout.astro` | Global HTML shell: meta, fonts, analytics, BaseBox promo strip (in-flow), sticky header/nav, mobile menu, **client-side i18n**, optional layout tweaks. |
| `src/components/` | Page sections (Hero, player, playlists, releases, about, contact, footer, etc.). |
| `src/i18n/en.ts`, `src/i18n/el.ts` | Translation dictionaries (plain objects, default export). |
| `src/config/` | URLs, analytics constants, collaboration list. |
| `src/lib/` | Server-side helpers (e.g. Spotify/RSS) used at build time in `index.astro`. |
| `src/styles/global.css` | Tailwind import + shared typography / utility classes. |

## BaseLayout ↔ components

- `BaseLayout` renders a **slot** (`<slot />`) inside `<main>`. `index.astro` passes all section components into that slot.
- Header, banner, and i18n script live only in `BaseLayout`; section components do not repeat layout chrome.
- `BaseLayout` imports `en` and `el`, builds `const translations = { en, el }`, and passes it to an **inline** script via `define:vars={{ translations }}` so the browser receives a serialized JSON snapshot at build time.

## BaseBox banner + sticky header

- **BaseBox banner** (`.basebox-banner`): **static** in-flow strip at the top (`position: static`; full width). It **scrolls away** with the page (never `position: fixed`).
- **Header** (`#main-header`): `position: sticky; top: 0` so that after the banner scrolls off, the nav bar stays pinned to the viewport top without overlapping the banner on first paint.
- **`adjustLayout()`** no longer stacks a fixed banner under a fixed header; it clears legacy `padding-top` / `top` inline styles when present so older sessions do not keep empty offset.
- `resize` and delayed calls after language change still invoke `adjustLayout()` (keeps hook for future layout tweaks; currently resets legacy inline offsets).

## Visual effects (runtime, `BaseLayout` + `global.css`)

- **Navbar hover ring:** `#nav-hover-ring` lives inside **`#main-header`**. On **`(pointer: fine)`** and **`min-width: 1024px`**, `mousemove` / `mouseleave` on the header drive a single **outline ring** that only appears while the pointer hovers **nav links**, **dropdown controls**, **`#share-btn`**, **`#burger-btn`**, **language switcher buttons**, **Store CTA**, or **mobile menu** links — not the logo, not blank chrome. **`elementFromPoint`** + **`closest`** gate targets; leaving the header **hides** the ring. Position and size follow the active control with the same **velocity spring** as before (tension / friction + snap), or **instant** updates when **`prefers-reduced-motion: reduce`**. Initialized once (`window.__mrbonzoNavHoverRing`).
- **Scroll reveal:** **`section-reveal`** on major page bands (Collaborations, Player, Beats, Kits, Releases, About, Contact) via **`index.astro`** wrappers + inner sections where applicable; **`IntersectionObserver`** → **`is-revealed`**. Reduced-motion bypass. **`astro:page-load`** re-binds reveal only.

## Client-side i18n script (`BaseLayout.astro`)

- **No framework hydration** for copy: Astro ships static HTML; a single inline script applies translations on the client.
- **Execution order**: The script is at the **end of `<body>`**. It runs synchronously after the DOM is parsed, then calls `applyTranslations()` and `adjustLayout()` immediately, before `window` `load` fires. The first paint may already include the server-rendered English defaults; `applyTranslations()` then aligns visible text with `localStorage` (`selected-lang`: `en` | `el`).
- **Normalization**: Invalid or legacy `localStorage` values are cleared and the UI falls back to English so a bad key cannot break the whole script.
- **Lookup**: String keys use dotted paths (`hero.label` → `dict.hero.label`). Missing keys fall back to the English dictionary to avoid empty nodes.
- **Attributes**: Besides `[data-i18n]` (inner HTML), the script updates `[data-i18n-alt]`, `[data-i18n-title]`, and `[data-i18n-aria-label]` for images, iframe titles, and icon buttons.
- **Persistence**: Choosing EL/EN writes `localStorage.setItem('selected-lang', …)`; on refresh, `normalizeLang()` reads it and `applyTranslations()` applies the correct dictionary. `document.documentElement.lang` is set to match the active locale.
- **View transitions**: If Astro view transitions are enabled later, `astro:page-load` re-runs `applyTranslations()`, `adjustLayout()`, and listener wiring.

## Build-time vs runtime data

- **Latest Releases** are fetched **at build time** in `index.astro` and passed into `DiscographySection` as props (not at page view).
- **Fetch order:** (1) **Spotify Web API** via `getArtistAlbums` when `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET` are set (optional `SPOTIFY_ARTIST_ID`, else parsed from `socialLinks.spotify`); albums are sorted by `release_date` and capped at 6. (2) Else **RSS** if `RELEASES_RSS_URL` is set. (3) Else **scrape** of the public Spotify artist page. After fetch, **`pinnedReleases`** in `index.astro` (currently **Catalyst (Beat Tape)**) are merged in, then **`sortReleasesNewestFirst`** always orders cards newest→oldest. If all sources return empty, `DiscographySection` uses hardcoded **fallback** cards.
- Env template: see `.env.example`. On Cloudflare Pages, set the same variables under **Settings → Environment variables**, then **rebuild** after new Spotify releases so the static HTML updates.
- UI strings for those dynamic titles (e.g. album names) remain proper nouns; translatable chrome uses `data-i18n` and the shared dictionaries.

## Performance & security (browser)

- **Images:** Hero logo uses `loading="eager"`, `fetchpriority="high"`, `decoding="async"`, and explicit `width`/`height` to reduce CLS. Header logo in `BaseLayout` is also eager + high priority. Below-the-fold images (About portrait, playlists, releases, drum kit art) use `loading="lazy"` and `decoding="async"` where applicable.
- **Beatstars iframe** (`FeaturedBeatstars.astro`): `loading="lazy"`, `fetchpriority="low"`, `referrerpolicy="strict-origin-when-cross-origin"`. (`decoding` is not a valid iframe attribute; use image tags for `decoding="async"`.)
- **Preconnect / DNS:** `BaseLayout` preconnects Beatstars, Google Tag Manager, Google Analytics, fonts (existing), plus `gc.zgo.at` for GoatCounter; GoatCounter script uses `https://` and `crossorigin="anonymous"`.
- **Fonts:** Google Fonts URL includes `&display=swap` (non-blocking text).
- **CSP & headers:** Meta CSP includes **`https://*.beatstars.com`** in **`frame-src`** and **`script-src`** so **`player.beatstars.com`** embeds work (not only `www.beatstars.com`). **`img-src`** adds Spotify (`*.scdn.co`, `*.spotifycdn.com`) and YouTube/Google thumbnail hosts (`*.ggpht.com`, `*.googleusercontent.com`) beside Beatstars/ytimg/pages.dev. **`public/_headers`** still adds transport headers on supporting hosts.
- **i18n XSS:** `applyTranslations()` uses **`textContent`** for all keys except an explicit allowlist (`drumkits.title`, `about.titleHtml`, `contact.title`) that ship trusted HTML from the repo. Alt/title/aria values are passed through **`safeAttr()`** (strips control chars and angle brackets).

## Automation: `git-save`

- **Command:** `npm run git-save -- "type: short description"` (implementation: `scripts/git-save.mjs`).
- **Flow:** `git add -A` → **documentation guard** (see `guardrails.md`) → optional **auto-stub** footer in `architecture.md` / `guardrails.md` when “impact” paths change without those files in the commit → `git commit` → `git push` for the **current branch**.
- **Audit log:** append-only lines in **`.git/git-save-doc-audit.log`** (local to the clone, not committed) describing whether docs were touched, bypassed, or assumed up-to-date.
- **Multi-branch:** optional `--sync-branches main,develop` merges current `HEAD` into each listed branch and pushes (manual conflict resolution if needed). Optional `--push-all` pushes every local branch that is **ahead** of its upstream.
- **Why Node:** one entrypoint that works on **Windows and Unix**, matching how this Astro repo is already driven via `npm`.
