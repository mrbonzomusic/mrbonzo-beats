# Architecture — Mr. Bonzo Beats (Astro)

> **Last save:** 2026-07-16 13:53

## Overview

Static Astro site (`output: "static"`). One primary page (`src/pages/index.astro`) composes sections as Astro components and wraps everything in `BaseLayout.astro`. Hosted on Cloudflare Pages (typical).

## Current site map (homepage)

Order in `src/pages/index.astro` (inside `BaseLayout` → `<main>`):

1. **Hero** — `Hero.astro`
2. **Collaborations** — `CollaborationsSection.astro` (`section-reveal`)
3. **Player** — `#player` → `FeaturedBeatstars.astro` (Beatstars iframe)
4. **Beats** — `#beats` → `TypeBeatGrid.astro`
5. **Drum kits** — `#drumkits` → `DrumKits.astro`
6. **Latest Releases** — `#latest-releases` → `DiscographySection.astro` (inner `#releases`)
7. **About** — `#about` → `AboutSection.astro` + `ServicesSection.astro`
8. **Contact** — `#contact` → `ContactSection.astro`
9. **Footer** — `SiteFooter.astro` (+ stats via `FooterStats.astro` where used)

Chrome outside `<main>` (in `BaseLayout.astro`): BaseBox banner → sticky `#main-header` (nav, share, EN/EL, Store, burger + mobile menu) → `#nav-hover-ring`.

## Directory layout (high level)

| Area | Role |
|------|------|
| `src/pages/` | Routes; `index.astro` assembles the homepage. |
| `src/layouts/BaseLayout.astro` | Global HTML shell: meta, fonts, analytics, BaseBox, sticky header/nav, mobile menu, **client-side i18n**, navbar hover ring, section reveal init. |
| `src/components/` | Page sections (Hero, player, playlists, releases, about, contact, footer, etc.). |
| `src/i18n/en.ts`, `src/i18n/el.ts` | Translation dictionaries (plain objects, default export). |
| `src/config/` | URLs (`links.ts`), analytics, collaboration list. |
| `src/lib/` | Build-time helpers (`spotify.ts`: API / RSS / scrape + `sortReleasesNewestFirst`). |
| `src/styles/global.css` | Tailwind import + typography, `section-reveal`, `.nav-hover-ring`. |
| `scripts/save.mjs` | `npm run save` — commit, push, always refresh docs. |
| `AGENTS.md` / `guardrails.md` | Agent entrypoint + hard rules. |

## BaseLayout ↔ components

- `BaseLayout` renders a **slot** (`<slot />`) inside `<main>`. `index.astro` passes all section components into that slot.
- Header, banner, and i18n script live only in `BaseLayout`; section components do not repeat layout chrome.
- `BaseLayout` imports `en` and `el`, builds `const translations = { en, el }`, and passes it to an **inline** script via `define:vars={{ translations }}`.

## Links & config

- **Canonical social / store URLs:** `src/config/links.ts` (`socialLinks`, `beatstarsLinks`).
- Nav Discord / TikTok / Spotify and Contact Discord must use `socialLinks.*` (no duplicate hardcoded invites).
- Pond5 / YouTube channel URLs may remain locals in `BaseLayout` if not yet moved into config.

## BaseBox banner + sticky header

- **BaseBox banner** (`.basebox-banner`): **static** in-flow strip; scrolls away (never `position: fixed`).
- **Header** (`#main-header`): `position: sticky; top: 0`.
- **`adjustLayout()`** clears legacy fixed-offset inline styles.

## Visual effects (runtime)

- **No film grain** — grain overlay was removed; do not reintroduce unless explicitly requested.
- **No full-page custom cursor** — native browser cursor site-wide.
- **Navbar hover ring only:** `#nav-hover-ring` inside `#main-header`; desktop fine pointer ≥1024px; hides on header `mouseleave`. See `initNavbarHoverRing` in `BaseLayout.astro`.
- **Scroll reveal:** `.section-reveal` → IntersectionObserver → `.is-revealed`.

## Client-side i18n (`BaseLayout.astro`)

- Inline script at end of `<body>`; `localStorage['selected-lang']` is only `en` | `el`.
- Keys: `data-i18n`, `data-i18n-alt`, `data-i18n-title`, `data-i18n-aria-label`.
- HTML allowlist (`htmlKeys`): `drumkits.title`, `about.titleHtml`, `contact.title`.

## Latest Releases (build-time)

- Fetched at **build**, not on each page view.
- **Order:** Spotify Web API → RSS (`RELEASES_RSS_URL`) → public page scrape.
- Then **`pinnedReleases`** (e.g. Catalyst) merged + **`sortReleasesNewestFirst`** (newest → oldest), cap 6.
- Empty result → `DiscographySection` hardcoded fallbacks.
- Env: `.env.example`. Cloudflare Pages must set `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` for live API (note: some Spotify apps may return 403 without eligible owner subscription).
- New Spotify drops need a **rebuild/deploy** (or pin in `pinnedReleases`).

## Performance & security

- Eager high-priority logos; lazy below-the-fold images; Beatstars iframe lazy + low fetch priority.
- CSP meta in `BaseLayout` must allow Beatstars (`*.beatstars.com`), analytics, Spotify CDN images.
- `public/_headers` for transport headers on supporting hosts.

## Automation: `npm run save`

- **Command:** `npm run save -- "type: short description"` (`scripts/save.mjs`). Alias: `npm run git-save`.
- **Flow:** `git add -A` → **always** refresh `architecture.md` / `guardrails.md` / `AGENTS.md` (Last save stamp + Save log entry) → commit → push current branch.
- **Flags:** `--push-all`, `--sync-branches a,b`, `--allow-stale-docs`, `--no-tag-docs`, `--dry-run`.
- **Audit log:** `.git/git-save-doc-audit.log` (local, not committed).

## Save log

(Entries prepended automatically by `npm run save`.)
