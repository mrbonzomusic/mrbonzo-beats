# Guardrails — UI, i18n, and layout

Rules for future changes so the site stays consistent and flicker-free.

## 1. Internationalization keys

- Every **new user-visible string** must have a matching entry in **`src/i18n/en.ts` and `src/i18n/el.ts`** (same key path, e.g. `section.blockLabel`).
- Prefer **flat dotted keys** in markup: `data-i18n="hero.label"` maps to `hero.label` on the dictionary root (not `hero.title` unless you add that key).
- When a string supports HTML (e.g. line breaks, spans), keep the same structure in both languages. At runtime, **`applyTranslations()`** uses **`textContent`** for most keys; only an explicit **HTML allowlist** in `BaseLayout.astro` (`htmlKeys`) uses **`innerHTML`** (currently `drumkits.title`, `about.titleHtml`, `contact.title`).

## 2. English defaults in `.astro` files (flicker / CLS)

- **Default text inside `.astro` templates (the text between tags) must match the English dictionary exactly** for any element that has `data-i18n` (or attribute variants below). That way the first paint matches what English users see after the script runs, and you avoid layout shift when copy length changes between SSR default and `en`.
- If you change `en.ts`, update the corresponding **fallback text in the component** in the same PR.
- Attribute fallbacks: use `data-i18n-alt`, `data-i18n-title`, and `data-i18n-aria-label` with defaults equal to the English strings in `en.ts`.

## 3. Client script expectations

- Do not store arbitrary values in **`localStorage['selected-lang']`**; only `en` and `el` are supported. Invalid values are cleared at runtime (fallback `en`).
- Adding a new attribute type for translations requires extending **`applyTranslations()`** in `BaseLayout.astro` (keep `resolveString` + English fallback pattern).

## 4. Links and images

- **External URLs** (social, stores) may stay in config; **link labels** should use `data-i18n` where they are not proper nouns/brand names.
- **`alt` text**: use `data-i18n-alt` when the phrase is translatable. Proper nouns (playlist titles, product names) may stay locale-neutral.
- **`iframe` `title`**: use `data-i18n-title` (see Beatstars player).
- **Scroll reveal:** New homepage sections that should animate in on scroll can add the **`section-reveal`** class on the outer `section` in `index.astro` (Player, Beats, Kits, Releases, About, Contact, plus inner sections that own the class e.g. Collaborations); keep **`prefers-reduced-motion`** in mind (class is a no-op when reduce is set).

## 5. Z-index stacking (fixed UI)

Order from **top to bottom** (highest on top):

1. **BaseBox banner** (`.basebox-banner`) — in-flow promo strip at the very top; scrolls away (not a fixed layer).
2. **Header** (`#main-header`) — `position: sticky` below the banner so it pins after scroll without covering the banner initially.
3. **Main content** — flows after the header; sections may use `scroll-margin-top` for in-page anchors.

When adding modals or overlays, assign z-index **above** the header only if they must cover the whole viewport; document the value here if you introduce a new layer.

## 6. Dangerous patterns to avoid

- **Do not put JavaScript block comments (`/* … */`) inside HTML tags** in `.astro` files; they end up in the built HTML and can break attributes (this previously broke the Beatstars iframe).
- Prefer HTML comments **outside** tags or Astro frontmatter notes.

## 7. Optional hardening checklist (PR self-review)

- [ ] New copy added to `en.ts` / `el.ts`
- [ ] `.astro` default matches `en.ts`
- [ ] `npm run build` succeeds
- [ ] Toggle EL → refresh → still EL (`selected-lang` respected)

## 8. `git-save` workflow (recommended)

- Prefer **`npm run git-save -- "your message"`** before sharing work; it ties commits to the documentation guard.
- See **`architecture.md` → Automation: `git-save`** for flags (`--push-all`, `--sync-branches`, `--allow-stale-docs`, `--no-tag-docs`) and the local audit log under `.git/`.
- **Agent / human rule:** if you change layouts, i18n, new components under `src/components/`, or build config, update `architecture.md` / `guardrails.md` in the same change when the behaviour or rules change; otherwise let `git-save` append its one-line **auto-stub** and refine the prose in a follow-up commit.

## 9. Security (CSP, third-party scripts, forms)

- **Never add a third-party `<script src>`** without updating the **CSP meta** in `BaseLayout.astro` (`script-src` / `connect-src` / `frame-src` as needed) and noting it in `architecture.md`.
- **SRI (`integrity=`)** is not pinned on volatile vendor scripts (e.g. GTM); rely on **CSP allowlists** and HTTPS. For **self-hosted** scripts in `public/`, add SRI when the file is immutable.
- **HTML in i18n:** New rich-text keys must be added to the **`htmlKeys`** object in `BaseLayout.astro` or kept as plain text — never inject untrusted HTML into `en.ts` / `el.ts`.
- **Forms:** There is no server-side contact form today. If you add one, use a **honeypot** (hidden field), server validation, rate limits, and optionally CAPTCHA; see the HTML comment in `ContactSection.astro`.
