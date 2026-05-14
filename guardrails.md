# Guardrails — UI, i18n, and layout

Rules for future changes so the site stays consistent and flicker-free.

## 1. Internationalization keys

- Every **new user-visible string** must have a matching entry in **`src/i18n/en.ts` and `src/i18n/el.ts`** (same key path, e.g. `section.blockLabel`).
- Prefer **flat dotted keys** in markup: `data-i18n="hero.label"` maps to `hero.label` on the dictionary root (not `hero.title` unless you add that key).
- When a string supports HTML (e.g. line breaks, spans), keep the same structure in both languages and escape carefully; `applyTranslations` sets **`innerHTML`** for `[data-i18n]`.

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

## 5. Z-index stacking (fixed UI)

Order from **top to bottom** (highest on top):

1. **BaseBox banner** (`.basebox-banner`) — top promo strip; must stay above the header.
2. **Header** (`#main-header`) — navigation; above page content, below the banner.
3. **Main content** — sections, dropdowns use local stacking within the header where needed.

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
