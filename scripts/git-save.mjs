#!/usr/bin/env node
/**
 * git-save — staged commit + push with documentation guard (Astro / i18n aware).
 *
 * Usage:
 *   npm run git-save -- "fix: hero label alignment"
 *   npm run git-save -- --allow-stale-docs "chore: wip"
 *   npm run git-save -- --push-all "feat: nav"
 *   npm run git-save -- --sync-branches main,develop -m "merge from feature"
 *   npm run git-save -- --no-tag-docs "refactor only"   (skip auto-stub; use with --allow-stale-docs if needed)
 *
 * Env:
 *   GIT_SAVE_SKIP_DOC=1     same as --allow-stale-docs
 *   GIT_SAVE_PUSH_ALL=1    same as --push-all
 */

import { execSync } from "node:child_process";
import { appendFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

function sh(cmd) {
  execSync(cmd, { cwd: ROOT, encoding: "utf8", stdio: "inherit" });
}

function shOut(cmd) {
  return execSync(cmd, { cwd: ROOT, encoding: "utf8", stdio: "pipe" }).trim();
}

function shTry(cmd) {
  try {
    return execSync(cmd, { cwd: ROOT, encoding: "utf8", stdio: "pipe" }).trim();
  } catch {
    return "";
  }
}

function gitDir() {
  return shOut("git rev-parse --git-dir");
}

function logAudit(line) {
  const dir = gitDir();
  const path = resolve(ROOT, dir, "git-save-doc-audit.log");
  appendFileSync(path, `[${new Date().toISOString()}] ${line}\n`, "utf8");
  console.log(`\n[git-save] Audit log: ${path}\n  → ${line}`);
}

const IMPACT_PATTERNS = [
  /^src\/layouts\//,
  /^src\/i18n\//,
  /^src\/pages\//,
  /^src\/components\//,
  /^src\/config\//,
  /^src\/lib\//,
  /^src\/styles\//,
  /^scripts\//,
  /^astro\.config\./,
  /^package\.json$/,
  /^package-lock\.json$/,
  /^pnpm-lock\.yaml$/,
  /^tsconfig\.json$/,
];

const DOC_FILES = new Set(["architecture.md", "guardrails.md"]);

function normalizePath(f) {
  return f.replace(/\\/g, "/");
}

function parseArgs(argv) {
  const out = {
    message: "",
    allowStaleDocs: false,
    pushAll: false,
    syncBranches: [],
    noTagDocs: false,
    dryRun: false,
  };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--allow-stale-docs" || a === "--skip-doc") out.allowStaleDocs = true;
    else if (a === "--push-all") out.pushAll = true;
    else if (a === "--no-tag-docs") out.noTagDocs = true;
    else if (a === "--dry-run") out.dryRun = true;
    else if (a === "--sync-branches") {
      const v = argv[++i] || "";
      out.syncBranches = v
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    } else if (a === "-m" || a === "--message") out.message = argv[++i] || "";
    else if (!a.startsWith("-")) rest.push(a);
  }
  if (!out.message && rest.length) out.message = rest.join(" ");
  if (process.env.GIT_SAVE_SKIP_DOC === "1") out.allowStaleDocs = true;
  if (process.env.GIT_SAVE_PUSH_ALL === "1") out.pushAll = true;
  return out;
}

function hasDocImpact(files) {
  return files.some((f) => IMPACT_PATTERNS.some((re) => re.test(normalizePath(f))));
}

function docsTouched(files) {
  return files.some((f) => DOC_FILES.has(normalizePath(f)));
}

const DOC_NOTICE =
  "\n\n---\n\n> **git-save (auto-stub):** Structural or i18n-related paths changed in this commit. Expand `architecture.md` / `guardrails.md` if behaviour, keys, or layout rules changed.\n";

function ensureDocStubIfNeeded(files, opts) {
  if (opts.allowStaleDocs || opts.noTagDocs) return { touched: false };
  if (!hasDocImpact(files)) return { touched: false };
  if (docsTouched(files)) return { touched: false };

  let touched = false;
  for (const name of DOC_FILES) {
    const p = resolve(ROOT, name);
    if (!existsSync(p)) continue;
    const cur = readFileSync(p, "utf8");
    if (cur.includes("**git-save (auto-stub):**")) continue;
    writeFileSync(p, cur.replace(/\s*$/, "") + DOC_NOTICE, "utf8");
    touched = true;
  }
  return { touched };
}

function pushCurrent() {
  const branch = shOut("git branch --show-current");
  sh(`git push -u origin "${branch}"`);
}

function pushAllAhead() {
  const branches = shOut('git for-each-ref --format="%(refname:short)" refs/heads/')
    .split("\n")
    .filter(Boolean);

  for (const b of branches) {
    const upstream = shTry(`git rev-parse --abbrev-ref "${b}@{upstream}"`);
    if (!upstream) continue;
    const ahead = shTry(`git rev-list --count "${upstream}..${b}"`);
    const n = parseInt(ahead, 10);
    if (n > 0) {
      console.log(`[git-save] Pushing ${b} (${n} commit(s) ahead of ${upstream})…`);
      sh(`git push origin "${b}"`);
    }
  }
}

function syncBranches(branchList) {
  const current = shOut("git branch --show-current");
  const head = shOut("git rev-parse HEAD");
  for (const target of branchList) {
    if (target === current) continue;
    console.log(`[git-save] Merging ${current} (${head.slice(0, 7)}) → ${target}…`);
    sh(`git checkout "${target}"`);
    try {
      sh(`git merge "${head}" -m "git-save: merge ${current} into ${target}"`);
    } catch {
      console.error(
        `[git-save] Merge failed into ${target}. Resolve conflicts, push, then: git checkout ${current}`
      );
      process.exit(1);
    }
    sh(`git push origin "${target}"`);
  }
  sh(`git checkout "${current}"`);
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  let message = opts.message?.trim();
  if (!message) {
    message = `chore: snapshot ${new Date().toISOString().slice(0, 19)}`;
    console.warn(`[git-save] No message passed; using default: ${message}`);
  }

  try {
    gitDir();
  } catch {
    console.error("[git-save] Not a git repository.");
    process.exit(1);
  }

  if (opts.dryRun) {
    console.log("[git-save] Dry run: would git add -A, doc guard/stub, commit, push.");
    process.exit(0);
  }

  sh("git add -A");

  let staged = shOut("git diff --cached --name-only")
    .split("\n")
    .filter(Boolean);

  if (staged.length === 0) {
    logAudit("Nothing to commit (clean working tree after git add -A).");
    console.log("[git-save] Nothing to commit.");
    process.exit(0);
  }

  const stub = ensureDocStubIfNeeded(staged, opts);
  if (stub.touched) {
    sh("git add architecture.md guardrails.md");
    staged = shOut("git diff --cached --name-only")
      .split("\n")
      .filter(Boolean);
    logAudit(
      "Appended git-save auto-stub to architecture.md and/or guardrails.md (expand narrative when you can)."
    );
  } else if (hasDocImpact(staged) && docsTouched(staged)) {
    logAudit("Documentation files were already part of this commit.");
  } else if (hasDocImpact(staged) && opts.allowStaleDocs) {
    logAudit("Documentation guard bypassed (--allow-stale-docs); impact paths changed without new doc edits.");
  } else if (!hasDocImpact(staged)) {
    logAudit(
      "Documentation check: no architecture/i18n/layout-rule paths in this commit — architecture.md & guardrails.md assumed up-to-date."
    );
  } else if (hasDocImpact(staged) && !docsTouched(staged)) {
    logAudit(
      "Impact paths changed; doc stub already present in markdown (no duplicate appended) or only non-doc files — commit proceeds."
    );
  }

  sh(`git commit -m ${JSON.stringify(message)}`);

  pushCurrent();

  if (opts.pushAll) {
    console.log("[git-save] --push-all: pushing other ahead branches…");
    pushAllAhead();
  }

  if (opts.syncBranches.length) {
    syncBranches(opts.syncBranches);
  }

  console.log("\n[git-save] Done.\n");
}

main();
