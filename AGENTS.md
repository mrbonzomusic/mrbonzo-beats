# AGENTS.md — Mr. Bonzo Beats

> **Last save:** 2026-07-16 13:54

## Before you change code

1. Read **[`architecture.md`](architecture.md)** (how the site is built, current map, releases, FX).
2. Read **[`guardrails.md`](guardrails.md)** (i18n, links, no grain / no full custom cursor, save workflow).

## While you work

- Match existing Astro + Tailwind patterns; prefer small, focused diffs.
- New UI copy → `src/i18n/en.ts` **and** `src/i18n/el.ts`, with English defaults in the `.astro` file.
- Social/store URLs → `src/config/links.ts`.
- If behaviour or rules change, update `architecture.md` and/or `guardrails.md` in the **same** session.

## When you finish

Always save with:

```bash
npm run save -- "type: short description"
```

(`npm run git-save` is an alias.) This commits, pushes, and **always** refreshes Last save stamps + the Save log in `architecture.md`.

Do not use raw `git commit` / `git push` for routine work unless the user asks otherwise.
