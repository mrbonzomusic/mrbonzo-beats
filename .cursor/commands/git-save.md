---
description: Run git-save — commit, push, and documentation guard (architecture & guardrails sync)
---

When the user asks for **git-save**, **save to git**, or **sync docs and commit**:

1. Run from the project root: `npm run git-save -- "<descriptive conventional message>"`  
   - If they did not give a message, propose a short imperative one (e.g. `chore: update footer links`).

2. **If structural / i18n / layout work was done in this session** (e.g. `BaseLayout`, `src/i18n`, new components, `astro.config`):  
   - Prefer editing `architecture.md` and/or `guardrails.md` **before** running `git-save`, so the commit is meaningful.  
   - If the user insists on a quick save only, use `npm run git-save -- --allow-stale-docs "..."` and remind them the audit log will record the bypass.

3. After the command finishes, read `.git/git-save-doc-audit.log` (last lines) if present and summarize: **code vs documentation** outcome.

4. **Do not** silently merge across branches unless the user explicitly requested `--sync-branches` with a branch list; warn that merges can conflict.

Optional flags to mention when relevant:

- `--push-all` — push every local branch ahead of its upstream  
- `--sync-branches main,develop` — merge current `HEAD` into listed branches and push  
- `--allow-stale-docs` / `GIT_SAVE_SKIP_DOC=1` — skip auto-stub / bypass doc guard logging path  
- `--no-tag-docs` — never append the auto-stub (combine with `--allow-stale-docs` if impact paths changed)
