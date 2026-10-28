# Architecture — Mr. Bonzo Beats (Astro)

> **Last save:** 2026-10-28 10:24

## Overview

Static Astro site (`output: "static"`). The homepage (`src/pages/index.astro`) composes sections as Astro components and wraps everything in `BaseLayout.astro`. Hosted on Cloudflare Pages. Newsletter signup posts to a Pages Function (`functions/api/subscribe.js`) which talks to self-hosted Plunk; the secret stays in Pages env, never in the client.

## Current site map (homepage)

Order in `src/pages/index.astro` (inside `BaseLayout` → `<main>`):

1. **Hero** — `Hero.astro`
2. **Collaborations** — `CollaborationsSection.astro` (`section-reveal`)
3. **Player** — `#player` → `FeaturedBeatstars.astro` (Beatstars iframe)
4. **Beats** — `#beats` → `TypeBeatGrid.astro`
5. **Drum kits** — `#drumkits` → `DrumKits.astro`
6. **Latest Releases** — `#latest-releases` → `DiscographySection.astro` (inner `#releases`)
7. **About** — `#about` → `AboutSection.astro` + `ServicesSection.astro`
8. **Contact** — `#contact` → `ContactSection.astro` (email / Instagram / Discord)
9. **Footer** — `SiteFooter.astro` (copyright + social links)

Old `/terms` and `/privacy` redirect to `/` (`public/_redirects`). Header section links use `/#…`.

Chrome outside `<main>` (in `BaseLayout.astro`): BaseBox banner → sticky `#main-header` (nav, share, EN/EL, Store, burger + mobile menu) → `#nav-hover-ring`.

## Directory layout (high level)

| Area | Role |
|------|------|
| `src/pages/` | Routes; `index.astro` assembles the homepage. |
| `src/layouts/BaseLayout.astro` | Global HTML shell: meta, fonts, analytics, BaseBox, sticky header/nav, mobile menu, **client-side i18n**, navbar hover ring, section reveal init. |
| `src/components/` | Page sections (Hero, player, playlists, releases, about, contact, footer, etc.). |
| `src/i18n/en.ts`, `src/i18n/el.ts` | Translation dictionaries (plain objects, default export). |
| `src/config/` | URLs (`links.ts`), collaboration list. |
| `src/lib/` | Build-time helpers (`spotify.ts`: API / RSS / scrape + `sortReleasesNewestFirst`). |
| `src/styles/global.css` | Tailwind import + typography tokens (eyebrows, `--ui-interactive` / `--ui-meta`, `.nav-link`), `section-reveal`, `.nav-hover-ring`. |
| `functions/` | Cloudflare Pages Functions (`api/subscribe.js` → Plunk). |
| `scripts/save.mjs` | `npm run save` — commit, push, always refresh docs. |
| `AGENTS.md` / `guardrails.md` | Agent entrypoint + hard rules. |

## BaseLayout ↔ components

- `BaseLayout` renders a **slot** (`<slot />`) inside `<main>`. `index.astro` passes all section components into that slot.
- Header, banner, and i18n script live only in `BaseLayout`; section components do not repeat layout chrome.
- `BaseLayout` imports `en` and `el`, builds `const translations = { en, el }`, and passes it to an **inline** script via `define:vars={{ translations }}`.

## Links & config

- **Canonical social / store URLs:** `src/config/links.ts` (`socialLinks`, `beatstarsLinks`, `basebox`).
- YouTube beats: `socialLinks.youtube` (`@mrbonzobeats`). Artist channel: `socialLinks.youtubeArtist` (`@mrbonzomusic`). Pond5: `socialLinks.pond5`.
- Nav Discord / TikTok / Spotify / YouTube / Pond5 and Contact Discord must use `socialLinks.*` (no duplicate hardcoded invites).

## BaseBox banner + sticky header

- **BaseBox banner** (`.basebox-banner`): **static** in-flow strip; scrolls away (never `position: fixed`). Sentence-case promo at **16px** (name, tagline, CTA) so it reads beside the 14px uppercase nav. Cube WebP logo, BaseBox-DB name, product hook, filled “try it free” CTA. Links to BaseBox-DB (`basebox` in `links.ts`).
- **Header** (`#main-header`): `position: sticky; top: 0`.
- **`adjustLayout()`** clears legacy fixed-offset inline styles.

## Typography (UI chrome)

- **Display headings** and **body copy** stay large (`text-3xl`–`text-7xl` / `text-base`–`text-xl`).
- **Interactive UI** (nav, buttons, footer links): **14px** (`--ui-interactive` / `text-sm`). Desktop nav uses `.nav-link`.
- **Meta / chips** (badges, captions, year, EN/EL): **12px** (`--ui-meta` / `text-xs`). Nothing user-facing below 12px.

## Analytics

- **Google Analytics 4** in `BaseLayout.astro` (`gtag.js`, Measurement ID `G-XBS5WKEGPE`, stream URL `https://mrbonzo-beats.pages.dev/`).
- Outbound clicks (Beatstars, Discord, Spotify, TikTok, Instagram, YouTube, Pond5) send `gtag('event', 'outbound_click', { link_url, link_host })`.
- GTM/GA `preconnect` is without `crossorigin` so it matches classic `<script src>` (avoids Chrome `ERR_BLOCKED_BY_ORB` on gtag.js).
- GoatCounter was removed (account deleted; no `gc.zgo.at` script or CSP hosts).

## SEO

- `public/robots.txt` + `public/sitemap.xml` (homepage). JSON-LD `MusicGroup` + `sameAs` in `BaseLayout`. OG image `/og-image-v2.jpg`. Hero has `sr-only` `<h1>`.
- Newsletter remains paused until a public domain.

## Visual effects (runtime)

- **No film grain** — grain overlay was removed; do not reintroduce unless explicitly requested.
- **No full-page custom cursor** — native browser cursor site-wide.
- **Navbar hover ring only:** `#nav-hover-ring` inside `#main-header`; desktop fine pointer ≥1024px; hides on header `mouseleave`. See `initNavbarHoverRing` in `BaseLayout.astro`.
- **Scroll reveal:** `.section-reveal` → IntersectionObserver → `.is-revealed`.

## Client-side i18n (`BaseLayout.astro`)

- Inline script at end of `<body>`; `localStorage['selected-lang']` is only `en` | `el`.
- Keys: `data-i18n`, `data-i18n-alt`, `data-i18n-title`, `data-i18n-aria-label`.
- HTML allowlist (`htmlKeys`): `drumkits.title`, `about.titleHtml`, `contact.title`.
- Extra attributes: `data-i18n-placeholder` (kept for the paused newsletter field).
- Collaboration marquee: order in `src/config/collaborations.ts`; labels in `collaborations.artists` (`en.ts` / `el.ts`). Greek script only for names whose Greek spelling is confirmed. The name sits in its own span so `textContent` updates do not remove the separator.

## Newsletter (Plunk) — paused until a public domain

- Form is **not** on the site. Copy stays in `newsletter.*` (`en.ts` / `el.ts`). Function `functions/api/subscribe.js` returns 503 until re-enabled.
- When bringing it back: named Cloudflare Tunnel (stable hostname) + `PLUNK_API_URL` / `PLUNK_SECRET_KEY` Pages secrets. Homelab API is `https://plunk-api.homelab.lan/` (`POST /contacts`). Do not put the secret in git or the browser.
- Quick `trycloudflare.com` tunnels were a stopgap; do not leave `plunk-tunnel` running without a domain (URL changes on PC reboot).

## Latest Releases (build-time)

- Fetched at **build**, not on each page view (static host).
- **Order:** Spotify Web API → RSS (`RELEASES_RSS_URL`) → public page scrape.
- Always merge **iTunes Search API** (no auth; often sees DistroKid drops first) + **`pinnedReleases`**, then **`mergeReleaseLists`** (dedupe by title; prefer a real Spotify `/album/` URL) + **`sortReleasesNewestFirst`**, cap 6.
- Empty result → `DiscographySection` hardcoded fallbacks (includes Anomaly).
- Env: `.env.example`. Cloudflare Pages must set `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` for live API (note: some Spotify apps may return 403 without eligible owner subscription).
- **Automatic refresh:** GitHub Action `.github/workflows/refresh-releases.yml` runs daily 05:00 UTC (`workflow_dispatch` too) and POSTs `CLOUDFLARE_PAGES_DEPLOY_HOOK`. Without that secret, new drops still need a deploy or pin.
- Brand-new albums can still be pinned in `pinnedReleases` in `index.astro` (e.g. Anomaly, 2026-09-04) for same-day cover/link.

## Performance & security

- Eager high-priority logos; lazy below-the-fold images; Beatstars iframe lazy + low fetch priority.
- CSP meta in `BaseLayout` must allow Beatstars (`*.beatstars.com`), Google Analytics (`*.googletagmanager.com`, `*.google-analytics.com` in script/img/connect), Spotify CDN images, **Apple artwork** (`*.mzstatic.com`) for iTunes-sourced covers.
- `public/_headers` for transport headers on supporting hosts.

## Automation: `npm run save`

- **Command:** `npm run save -- "type: short description"` (`scripts/save.mjs`). Alias: `npm run git-save`.
- **Flow:** `git add -A` → **always** refresh `architecture.md` / `guardrails.md` / `AGENTS.md` (Last save stamp + Save log entry) → commit → push current branch.
- **Flags:** `--push-all`, `--sync-branches a,b`, `--allow-stale-docs`, `--no-tag-docs`, `--dry-run`.
- **Audit log:** `.git/git-save-doc-audit.log` (local, not committed).

## Save log

- 2026-10-28 10:24 — feat: SEO, canonical YouTube, and conversion polish — 13 files (dist/index.html, public/manifest.json, public/robots.txt, public/sitemap.xml, src/components/FeaturedBeatstars.astro, src/components/Hero.astro, src/components/SiteFooter.astro, src/components/TypeBeatGrid.astro (+4 more))

- 2026-10-28 10:15 — chore: pause newsletter until a public domain — 5 files (dist/index.html, functions/api/subscribe.js, src/components/ContactSection.astro)

- 2026-10-28 10:08 — fix: prefer Plunk /contacts and document Cloudflare tunnel — 3 files (.env.example, functions/api/subscribe.js)

- 2026-10-28 09:55 — feat: newsletter signup, drop terms/privacy, Greek mobile wrapping — 18 files (.env.example, dist/index.html, functions/api/subscribe.js, public/_redirects, public/tiktok-app-icon-1024.png, src/components/CollaborationsSection.astro, src/components/ContactSection.astro, src/components/DrumKits.astro (+8 more))

- 2026-10-18 15:03 — feat: translate terms and privacy with language switcher — 8 files (src/i18n/el.ts, src/i18n/en.ts, src/layouts/BaseLayout.astro, src/pages/privacy.astro, src/pages/terms.astro, src/styles/global.css)

- 2026-10-18 14:54 — feat: add public terms and privacy pages — 8 files (src/components/SiteFooter.astro, src/i18n/el.ts, src/i18n/en.ts, src/layouts/BaseLayout.astro, src/pages/privacy.astro, src/pages/terms.astro)

- 2026-10-11 19:30 — feat: add artists and Greek collaboration names — 6 files (src/components/CollaborationsSection.astro, src/config/collaborations.ts, src/i18n/el.ts, src/i18n/en.ts)

- 2026-09-04 13:28 — feat: pin Anomaly and auto-refresh releases — 11 files (.astro/types.d.ts, .env.example, .github/workflows/refresh-releases.yml, dist/index.html, public/images/releases/anomaly-beat-tape.jpg, src/components/DiscographySection.astro, src/layouts/BaseLayout.astro, src/lib/spotify.ts (+1 more))

- 2026-09-01 22:00 — feat: larger BaseBox banner type — 2 files (src/layouts/BaseLayout.astro)

- 2026-09-01 21:18 — feat: richer BaseBox promo bar — 5 files (.astro/types.d.ts, public/images/basebox-logo.png, public/images/basebox-logo.webp, src/layouts/BaseLayout.astro)

- 2026-09-01 21:11 — fix: use transparent BaseBox-DB cube logo — 1 files (public/images/basebox-logo.png)

- 2026-09-01 21:04 — feat: professional BaseBox-DB promo banner — 5 files (public/images/basebox-logo.png, src/i18n/el.ts, src/i18n/en.ts, src/layouts/BaseLayout.astro)

- 2026-09-01 20:54 — feat: BaseBox banner links to BaseBox-DB — 5 files (src/config/links.ts, src/i18n/el.ts, src/i18n/en.ts, src/layouts/BaseLayout.astro)

- 2026-09-01 12:52 — fix: drop Official Website label and shorten hero — 3 files (src/components/Hero.astro, src/i18n/el.ts, src/i18n/en.ts)

- 2026-08-31 19:54 — fix: GA4 ID G-XBS5WKEGPE for Mr. Bonzo stream — 2 files (src/layouts/BaseLayout.astro)

- 2026-08-31 19:43 — fix: use live GA4 measurement ID G-XB55WKEGPE — 2 files (src/layouts/BaseLayout.astro)

- 2026-08-31 19:36 — fix: GTM preconnect without CORS to avoid ORB block — 2 files (src/layouts/BaseLayout.astro)

- 2026-08-31 19:25 — fix: allow GA4 collect endpoints in CSP — 2 files (src/layouts/BaseLayout.astro)

- 2026-08-31 19:18 — chore: remove GoatCounter after account deletion — 2 files (src/layouts/BaseLayout.astro)

- 2026-08-31 19:09 — fix: readable UI type and remove footer counter — 15 files (dist/index.html, src/components/AboutSection.astro, src/components/DiscographySection.astro, src/components/FeaturedBeatstars.astro, src/components/FooterStats.astro, src/components/Hero.astro, src/components/SiteFooter.astro, src/components/TypeBeatGrid.astro (+5 more))

- 2026-07-16 13:54 — fix: Save log prepend handles CRLF and records entries — 1 files (scripts/save.mjs)

(Entries prepended automatically by `npm run save`.)
