#!/usr/bin/env node
/**
 * save — staged commit + push with always-on docs refresh (Astro / i18n aware).
 *
 * Usage:
 *   npm run save -- "fix: hero label alignment"
 *   npm run save -- --allow-stale-docs "chore: wip"
 *   npm run save -- --push-all "feat: nav"
 *   npm run save -- --sync-branches main,develop -m "merge from feature"
 *   npm run save -- --no-tag-docs "refactor only"
 *
 * Alias: npm run git-save (same script)
 *
 * Env:
 *   GIT_SAVE_SKIP_DOC=1     same as --allow-stale-docs (skips impact auto-stub only; Save log still runs)
 *   GIT_SAVE_PUSH_ALL=1     same as --push-all
 */

import { execSync } from "node:child_process";
import { appendFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

const TAG = "[save]";

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
  console.log(`\n${TAG} Audit log: ${path}\n  → ${line}`);
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

const DOC_FILES = ["architecture.md", "guardrails.md", "AGENTS.md"];
const DOC_FILE_SET = new Set(DOC_FILES);

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
  return files.some((f) => DOC_FILE_SET.has(normalizePath(f)));
}

const DOC_NOTICE =
  "\n\n---\n\n> **save (auto-stub):** Structural or i18n-related paths changed in this commit. Expand `architecture.md` / `guardrails.md` if behaviour, keys, or layout rules changed.\n";

function ensureDocStubIfNeeded(files, opts) {
  if (opts.allowStaleDocs || opts.noTagDocs) return { touched: false };
  if (!hasDocImpact(files)) return { touched: false };
  // Prose already edited this save — skip stub
  if (docsTouched(files) && !opts._forceStub) return { touched: false };

  let touched = false;
  for (const name of ["architecture.md", "guardrails.md"]) {
    const p = resolve(ROOT, name);
    if (!existsSync(p)) continue;
    const cur = readFileSync(p, "utf8");
    if (cur.includes("**save (auto-stub):**") || cur.includes("**git-save (auto-stub):**")) continue;
    writeFileSync(p, cur.replace(/\s*$/, "") + DOC_NOTICE, "utf8");
    touched = true;
  }
  return { touched };
}

function formatStamp(d = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function summarizePaths(files, limit = 8) {
  const normalized = files.map(normalizePath).filter((f) => !DOC_FILE_SET.has(f));
  const list = normalized.length ? normalized : files.map(normalizePath);
  if (list.length <= limit) return list.join(", ");
  return `${list.slice(0, limit).join(", ")} (+${list.length - limit} more)`;
}

function upsertLastSaveLine(content, stamp) {
  const line = `> **Last save:** ${stamp}`;
  if (/^>\s*\*\*Last save:\*\*.*$/m.test(content)) {
    return content.replace(/^>\s*\*\*Last save:\*\*.*$/m, line);
  }
  // Insert after first H1
  return content.replace(/^(#\s+[^\n]+\n)/, `$1\n${line}\n`);
}

function prependSaveLogEntry(content, entryLine) {
  const header = "## Save log";
  if (!content.includes(header)) {
    return `${content.replace(/\s*$/, "")}\n\n${header}\n\n${entryLine}\n`;
  }
  // Match ## Save log followed by one or more blank lines (LF or CRLF).
  return content.replace(
    /(## Save log)(\r?\n)+/,
    `$1\n\n${entryLine}\n\n`
  );
}

/**
 * Always refresh docs on every save: Last save stamps + architecture Save log.
 */
function refreshDocsOnSave({ message, files }) {
  const stamp = formatStamp();
  const n = files.length;
  const summary = summarizePaths(files);
  const entry = `- ${stamp} — ${message} — ${n} files (${summary})`;

  for (const name of DOC_FILES) {
    const p = resolve(ROOT, name);
    if (!existsSync(p)) continue;
    let cur = readFileSync(p, "utf8");
    cur = upsertLastSaveLine(cur, stamp);
    if (name === "architecture.md") {
      cur = prependSaveLogEntry(cur, entry);
    }
    writeFileSync(p, cur.replace(/\s*$/, "") + "\n", "utf8");
  }

  return { stamp, entry };
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
      console.log(`${TAG} Pushing ${b} (${n} commit(s) ahead of ${upstream})…`);
      sh(`git push origin "${b}"`);
    }
  }
}

function syncBranches(branchList) {
  const current = shOut("git branch --show-current");
  const head = shOut("git rev-parse HEAD");
  for (const target of branchList) {
    if (target === current) continue;
    console.log(`${TAG} Merging ${current} (${head.slice(0, 7)}) → ${target}…`);
    sh(`git checkout "${target}"`);
    try {
      sh(`git merge "${head}" -m "save: merge ${current} into ${target}"`);
    } catch {
      console.error(
        `${TAG} Merge failed into ${target}. Resolve conflicts, push, then: git checkout ${current}`
      );
      process.exit(1);
    }
    sh(`git push origin "${target}"`);
  }
  sh(`git checkout "${current}"`);
}

function stageDocs() {
  const existing = DOC_FILES.filter((f) => existsSync(resolve(ROOT, f)));
  if (existing.length) sh(`git add ${existing.join(" ")}`);
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  let message = opts.message?.trim();
  if (!message) {
    message = `chore: snapshot ${new Date().toISOString().slice(0, 19)}`;
    console.warn(`${TAG} No message passed; using default: ${message}`);
  }

  try {
    gitDir();
  } catch {
    console.error(`${TAG} Not a git repository.`);
    process.exit(1);
  }

  if (opts.dryRun) {
    console.log(`${TAG} Dry run: would git add -A, refresh docs, commit, push.`);
    process.exit(0);
  }

  sh("git add -A");

  let staged = shOut("git diff --cached --name-only")
    .split("\n")
    .filter(Boolean);

  // If only docs would be touched by refresh, still need something staged;
  // if tree is fully clean, exit.
  if (staged.length === 0) {
    logAudit("Nothing to commit (clean working tree after git add -A).");
    console.log(`${TAG} Nothing to commit.`);
    process.exit(0);
  }

  // Always refresh Last save + Save log (even when --allow-stale-docs).
  const refreshed = refreshDocsOnSave({ message, files: staged });
  stageDocs();
  logAudit(`Docs refreshed on save (${refreshed.stamp}): Last save stamps + architecture Save log.`);

  // Impact auto-stub only when prose was not meaningfully present and impact paths changed.
  staged = shOut("git diff --cached --name-only")
    .split("\n")
    .filter(Boolean);

  const stub = ensureDocStubIfNeeded(staged, opts);
  if (stub.touched) {
    stageDocs();
    logAudit("Appended save auto-stub to architecture.md and/or guardrails.md (expand narrative when you can).");
  } else if (hasDocImpact(staged) && opts.allowStaleDocs) {
    logAudit("Impact auto-stub bypassed (--allow-stale-docs); Save log still updated.");
  }

  staged = shOut("git diff --cached --name-only")
    .split("\n")
    .filter(Boolean);

  sh(`git commit -m ${JSON.stringify(message)}`);

  pushCurrent();

  if (opts.pushAll) {
    console.log(`${TAG} --push-all: pushing other ahead branches…`);
    pushAllAhead();
  }

  if (opts.syncBranches.length) {
    syncBranches(opts.syncBranches);
  }

  console.log(`\n${TAG} Done.\n`);
}

main();
