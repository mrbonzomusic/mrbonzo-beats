---
description: Run save — commit, push, and always refresh architecture / guardrails / AGENTS
---

When the user asks for **save**, **git-save**, **save to git**, or **sync docs and commit**:

1. Run from the project root: `npm run save -- "<descriptive conventional message>"`  
   - If they did not give a message, propose a short imperative one (e.g. `chore: update footer links`).

2. **If structural / i18n / layout / FX / releases behaviour changed in this session**:  
   - Edit `architecture.md` and/or `guardrails.md` (and `AGENTS.md` if agent workflow changed) **before** running save, so prose matches reality.  
   - `npm run save` always updates **Last save** stamps and prepends a **Save log** line in `architecture.md`.

3. After the command finishes, summarize from `.git/git-save-doc-audit.log` (last lines) if present: docs refreshed + push outcome.

4. **Do not** silently merge across branches unless the user explicitly requested `--sync-branches`; warn that merges can conflict.

Optional flags:

- `--push-all` — push every local branch ahead of its upstream  
- `--sync-branches main,develop` — merge current `HEAD` into listed branches and push  
- `--allow-stale-docs` / `GIT_SAVE_SKIP_DOC=1` — skip impact auto-stub only (Save log still runs)  
- `--no-tag-docs` — skip impact auto-stub  
- `--dry-run` — print plan only  

Alias: `npm run git-save` → same as `npm run save`.
