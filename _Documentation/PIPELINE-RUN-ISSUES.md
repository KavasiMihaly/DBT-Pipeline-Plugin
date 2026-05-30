# Pipeline Run — Issues & Plugin Improvement Report

**Run:** GP Open Dataset (NHS England) end-to-end build
**Date:** 2026-05-29
**Plugin:** `dbt-pipeline-toolkit` v1.0.1 (OneDayBI-Marketplace)
**Environment:** Windows 11, OneDrive-synced repo, local SQL Server 2022, dbt 1.11.11 + dbt-sqlserver 1.9.2, Python 3.13
**Outcome:** ✅ Pipeline built and validated (12 models, 129 tests, 100% coverage, 0 failures) — **but only after the orchestrator worked around ~13 distinct issues.** Several would block or silently derail a less defensive run.

This document is written for the plugin maintainers. Each issue has: **what happened → impact → root cause → recommended fix.** Issues are ordered by severity.

---

## Severity legend
- 🔴 **Blocker** — halts the pipeline or produces wrong results unless manually worked around.
- 🟠 **Major** — forces non-obvious orchestrator intervention; would likely break an unattended run.
- 🟡 **Minor** — cosmetic, noisy, or low-impact but worth fixing.

---

## 🔴 1. `AskUserQuestion` is unavailable inside subagents — breaks the business-analyst discovery gate

**What happened:** Stage 2 spawns `business-analyst` (foreground) to ask the 4 discovery questions via a structured `AskUserQuestion` call. The subagent returned: *"AskUserQuestion is not available inside subagents"* and escalated back to the orchestrator without writing Section 1.

**Impact:** The single most important user-interaction gate cannot be performed by the agent that owns it. The orchestrator had to ask the 4 questions itself and write Section 1 directly. Any deployment that relies on the BA to run the gate would stall.

**Root cause:** `AskUserQuestion` is a main-thread-only tool; the BA is always a subagent. The orchestrator design even calls the BA in "foreground" expecting it to prompt the user, but foreground ≠ main-thread for tool availability.

**Recommended fix:**
- Update the orchestrator + BA contract so the **orchestrator owns the `AskUserQuestion` call** and passes answers to the BA (or writes Section 1 itself). The BA should return *the question set* (it already does this well — it pre-computed source-aware options) and the orchestrator asks.
- Remove the "spawn BA in foreground so it can prompt the user" guidance from the orchestrator doc — it's not achievable.

---

## 🔴 2. Subagent git-worktree creation fails with Windows "Filename too long"

**What happened:** Stage 9's `dbt-fact-builder` (worktree-isolated) failed at the `WorktreeCreate` hook:
```
error: unable to create file .claude/agent-memory/dbt-pipeline-toolkit-dbt-pipeline-orchestrator-dbt-pipeline-orchestrator/feedback_parallel_staging.md: Filename too long
fatal: Could not reset index file to revision 'HEAD'.
```

**Impact:** The fact builder could not launch at all. The orchestrator had to untrack `.claude/agent-memory/` from git, gitignore it, commit, then retry. Note the dimension builders (Stage 8) *happened* to succeed earlier — this is intermittent and path-length-dependent, so it will bite unpredictably.

**Root cause:** Compounding path lengths exceed the Windows ~260-char `MAX_PATH`:
`<repo>` (already long: `...\OneDrive\Documents\GitHub\Data Platform Next Step\Demo 1 - End`) `+ \.claude\worktrees\wt-xxxxxxxx\ +` the **very long agent-memory directory name** (`dbt-pipeline-toolkit-dbt-pipeline-orchestrator-dbt-pipeline-orchestrator`) `+` filename. When the worktree checks out committed files, those deep paths overflow.

**Recommended fix (several, ideally all):**
- The plugin should **gitignore `.claude/agent-memory/` and `.claude/worktrees/` by default** in the scaffold's `.gitignore` (the architecture-setup skill). Agent memory should never be committed *and then re-checked-out under a worktree.*
- Shorten the agent-memory directory naming scheme (the triple-repeated `dbt-pipeline-toolkit-...-orchestrator-orchestrator` is ~65 chars on its own).
- The `WorktreeCreate` hook should enable Windows long-path support (`git config core.longpaths true`) in the repo, or create worktrees in a short path (e.g. `%TEMP%\wt-xxxx`) instead of nested under the already-deep repo.

---

## 🟠 3. Worktree outputs are not merged back to main; transcripts truncate before confirming the build

**What happened:** Dimension, fact, and test subagents build their model files inside isolated worktrees. Those files are **not auto-merged** to `main`. Worse, the fact-builder's final transcript was **truncated** mid-sentence ("Now let me write the profiles.yml...") with **no JSON envelope** — so success could not be confirmed from the result. The orchestrator had to locate the files in the worktree, copy them to main, and re-run `dbt run`/`dbt test` itself to get authoritative results.

Additionally, the orchestrator's own session CWD ended up **inside a worktree**, so a new builder created a **nested** worktree (`wt-6cfa7230/.claude/worktrees/wt-92e3efda`).

**Impact:** Without manual merge + re-validation, the marts would be missing from `main` and the "build" would appear done while the project tree is incomplete. High risk of silent divergence.

**Root cause:**
- No defined merge-back step in the worktree lifecycle (the orchestrator doc says "merge worktrees back to main" but provides no mechanism, and `git worktree remove` fails on Windows/OneDrive file locks — see #11).
- Builders return large free-text summaries that can exceed transcript limits, truncating the structured envelope that the orchestrator's conformance gate depends on.

**Recommended fix:**
- Make the worktree **auto-commit on its branch and the orchestrator merge that branch** (`git merge --no-ff`) rather than relying on file copies. Provide a helper the orchestrator can call.
- Require builders to **emit the JSON envelope FIRST** (before prose), so truncation never eats the machine-readable result.
- Have builders write a small `*-result.json` to a known path as the source of truth, instead of relying on the chat transcript.

---

## 🟠 4. `dbt-sqlserver` legacy schema naming → tables land in `staging`/`analytics`, not `dbo_staging`/`dbo_analytics`

**What happened:** `dbt_project.yml` configures `+schema: staging` / `+schema: analytics`. With dbt-sqlserver's **legacy** `generate_schema_name` behaviour (the default), the custom schema name is used **directly without the `dbo_` target prefix**. So models materialized into schemas `staging` and `analytics` — but the orchestrator's master-doc template, the Created Objects Registry, and the `pbip-from-dbt` default (`--schema dbo_analytics`) all assume `dbo_*`.

**Impact:** Registry labels were wrong until corrected. Critically, `pbip-from-dbt` would have pointed Power BI at a non-existent `dbo_analytics` schema; the orchestrator had to override `--schema analytics`.

**Root cause:** Mismatch between the scaffold's schema config, the adapter's legacy behaviour, and the hard-coded `dbo_*` assumptions sprinkled across the orchestrator doc, registry template, reset script defaults, and pbip defaults.

**Recommended fix:**
- Make the scaffold **deterministic**: either set `flags.dbt_sqlserver_use_default_schema_concat: True` (so you really get `dbo_staging`/`dbo_analytics`) **or** standardize on the legacy `staging`/`analytics` names — and make every downstream default (registry template, `pbip-from-dbt --schema`, reset `--schemas`) read the actual schema from `dbt_project.yml`/`profiles.yml` rather than hard-coding `dbo_*`.
- `pbip-from-dbt` should **auto-detect** the marts schema from the dbt manifest instead of defaulting to `dbo_analytics`.

---

## 🟠 5. Headerless CSV loading requires manual column extraction; risk of silent header-row consumption

**What happened:** Three NHS ODS files (`epraccur`, `ebranchs`, `ets`) are headerless 27-column fixed-format files. The loader (`load_data.py`) has a fail-fast gate that (correctly) refuses to load them without `--no-header --columns "..."`. The orchestrator had to: detect headerlessness from profiles, get the BA to verify the 27 NHS ODS column names, extract those names from the rewritten profile JSON, and pass them on the CLI.

**Impact:** Worked well *because* the orchestrator handled it, but it's a lot of bespoke glue. The fail-fast gate is good (it prevented row-0 being consumed as headers), but the happy path is manual.

**Root cause:** No structured handoff of "verified column names" from the BA/profiler to the loader. The names live in prose/JSON and the orchestrator manually bridges them.

**Recommended fix:**
- When the profiler/ BA verify headerless columns, **write the verified column list into a machine-readable sidecar** (e.g. `profile_<table>.columns.json` or a `load_spec.yml`) that `load_data.py` can consume directly (`--columns-file`).
- Ship a small **NHS ODS column dictionary** as a known template, since the `e*` 27-column layout is standardized and recurring.

---

## 🟠 6. `architecture-setup` subagent died mid-run (API socket error) but left a usable scaffold

**What happened:** Stage 5's `dbt-architecture-setup` returned `API Error: Unable to connect to API (FailedToOpenSocket)` after 11 tool calls and **no JSON envelope**. The orchestrator verified the filesystem and found the scaffold was actually complete (dbt_project.yml, profiles.yml, packages, venv, dbt_packages, .gitignore, CLAUDE.md, model folders).

**Impact:** With no envelope, success was ambiguous; the orchestrator had to verify everything by hand. A naive run might re-scaffold or abort.

**Root cause:** Transient API failure + the skill doing all its durable work before returning a summary. (Not the plugin's fault per se, but recoverability could be better.)

**Recommended fix:**
- Make architecture-setup **idempotent and resumable**, and have it write a `scaffold-result.json` checkpoint as it goes so the orchestrator can verify completion independent of the chat transcript.

---

## 🟡 7. `run_dbt.py` wrapper throws a cosmetic `charmap` UnicodeEncodeError on Windows (exit 1 on success)

**What happened:** Every `dbt run`/`test`/`build` via the dbt-runner ended with:
```
ERROR: Unexpected error running dbt command: 'charmap' codec can't encode character '✓' in position 0: character maps to <undefined>
```
…**after** dbt itself printed `Completed successfully / PASS=.. ERROR=0`. The wrapper fails trying to print a `✓` to the Windows console (cp1252), and **exits 1**.

**Impact:** Every successful dbt invocation looks like a failure by exit code. The orchestrator had to learn to ignore the trailing error and instead parse dbt's own PASS/ERROR line or `target/run_results.json`. A run that trusts exit codes would treat the whole pipeline as failing.

**Root cause:** The wrapper prints Unicode (`✓`) to a non-UTF-8 Windows stdout without `encoding='utf-8'`/`errors='replace'`, and lets the exception set a non-zero exit.

**Recommended fix:**
- Set `PYTHONIOENCODING=utf-8` / `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` in the wrapper, or use ASCII status markers.
- **Never** let a print/encoding error change the propagated dbt exit code — capture dbt's real return code and exit with it.

---

## 🟡 8. `git add -A` stages worktrees as embedded repos; gitignore patterns under-anchored

**What happened:** `.gitignore` had `.claude/worktrees/` (anchored to repo root). A **nested** worktree at `3 - Data Pipeline/.claude/worktrees/wt-c594f659` was NOT matched and got staged as an *embedded git repository* on `git add -A`. Had to `git rm --cached -f` it and broaden the ignore to `**/.claude/worktrees/`.

**Impact:** Risk of committing an embedded repo / huge transient trees.

**Root cause:** Worktrees can be created nested (see #3), but the default ignore pattern only covers the root location.

**Recommended fix:**
- Scaffold `.gitignore` with `**/.claude/worktrees/` and `**/.claude/agent-memory/` (depth-agnostic).
- Prefer creating worktrees **outside the repo** (temp dir) so they can never be staged.

---

## 🟡 9. Specialists write outside their assigned master-doc section / lane

**What happened:** A staging builder edited **Section 11 (Created Objects Registry)** itself (adding its own row, with an incorrect "Stage 9" label during Stage 7), although the orchestrator is the sole owner of Section 11. A coverage/staging step also tweaked a schema label. The orchestrator had to reconcile Section 11 by hand.

**Impact:** Concurrent / out-of-lane writes to the master doc cause inconsistent stage labels and partial tables.

**Root cause:** The write-ownership protocol isn't enforced; builders are tempted to "be helpful" and update the registry.

**Recommended fix:**
- Builders should **only** return registry rows in their JSON envelope; the orchestrator writes Section 11. Make this explicit in each builder's system prompt and add a guard that builders never edit `pipeline-design.md` Section 11.

---

## 🟡 10. Source CSVs only partially copied into `2 - Source Files/`

**What happened:** Architecture-setup copied the 3 root-level CSVs into `2 - Source Files/` but not the 4 CSVs that lived in **subfolders** (`gp-reg-pat-prac-lsoa-.../`, `gp-reg-pat-prac-map-.../`). The orchestrator copied the remaining 4 in Stage 6.

**Impact:** Loader would have processed only 3 of 7 sources if the orchestrator hadn't checked counts.

**Root cause:** The copy step isn't recursive across nested source folders.

**Recommended fix:** Make the source-copy step **recursive** (flatten all discovered CSVs from Stage 0 into `2 - Source Files/`), and assert the copied count equals the discovered count.

---

## 🟡 11. `git worktree remove` fails on Windows/OneDrive ("Permission denied"); stray files left in tree

**What happened:** `git worktree remove --force` failed with `Permission denied` (OneDrive sync / `target/` file locks). Worktrees were left on disk (gitignored). Builders also left stray artifacts in the project: `staging-build-result.json` (root), `run_dim_lsoa.py` / `run_dbt_worktree.py` helper scripts (worktree roots), and several `query_results_*.csv` exports.

**Impact:** Cosmetic clutter; orphaned worktrees; an unremovable-worktree path can confuse later `git worktree` operations.

**Root cause:** OneDrive holds file handles; dbt `target/` artifacts lock; helper scripts created to dodge the atomic-Bash rule aren't cleaned up.

**Recommended fix:**
- Create worktrees outside OneDrive-synced paths (temp dir).
- Builders should clean up their own helper scripts and write result JSON to a designated `_Agent Logs/` dir, not the project root.
- The dbt-runner should support being invoked with an explicit `--project-dir` so builders don't need `cd`-dodging helper scripts at all (see #13).

---

## 🟡 12. `accepted_values` generic tests emit a dbt 1.11 deprecation warning everywhere

**What happened:** Every generated `accepted_values` test triggered `MissingArgumentsPropertyInGenericTestDeprecation` (args should nest under `arguments:`). 9+ occurrences across staging + dims.

**Impact:** Noisy warnings; will become an error in a future dbt version.

**Root cause:** The builders' schema-YAML templates use the pre-1.11 top-level `values:` form.

**Recommended fix:** Update the staging/dimension/test-writer YAML templates to nest generic-test args under `arguments:`.

---

## 🟡 13. dbt-runner requires CWD to be the project dir; combined with CWD resets, this is fragile

**What happened:** `run_dbt.py` errors `No dbt project found` unless CWD is the dbt project. The orchestrator's Bash CWD intermittently **reset to an agent worktree between turns**, so the orchestrator had to `cd "3 - Data Pipeline"` before each dbt/coverage call. Builders created helper scripts (`run_dbt_worktree.py`) specifically to dodge this under the atomic-Bash rule.

**Impact:** Easy to run dbt against the wrong tree, or fail outright. Encourages the very helper-script proliferation the project's atomic-Bash rule tries to prevent.

**Root cause:** No `--project-dir`/`--profiles-dir` passthrough on the dbt-runner wrapper, plus CWD instability in the harness.

**Recommended fix:** Add `--project-dir` (and `--profiles-dir`) to `run_dbt.py` and the coverage analyzer so they're **CWD-independent**. Document that orchestrator/builders should always pass an absolute project dir.

---

## What went well (keep these)
- **Parallel data-explorer profiling** (one agent per CSV) was fast and clean; profile JSONs were reused throughout.
- **Headerless fail-fast gate** in the loader prevented silent row-0-as-header corruption.
- **Conformance gate** concept (halt on `deviations[]`/`conforms_to_plan=false`) is sound — when builders return clean envelopes.
- **Surrogate-key conformance** held perfectly: every fact→dim `relationships` test passed first try because the design pinned exact `generate_surrogate_key` inputs.
- **Reconciliation test** (MALE+FEMALE == ALL) caught zero issues but is exactly the kind of business-rule check worth templating.
- **`pbip-from-dbt`** produced a clean openable skeleton once the schema override was supplied.

---

## Suggested priority order for plugin fixes
1. #1 AskUserQuestion ownership (blocks the user gate).
2. #2 Worktree long-path failure (blocks builds intermittently on Windows).
3. #7 charmap exit-code bug (makes every success look like failure).
4. #3 / #13 Worktree merge-back + `--project-dir` (reliability of the whole build).
5. #4 Schema-name auto-detection (wrong Power BI / registry targets).
6. #5 Machine-readable column handoff for headerless loads.
7. The rest (#6, #8–#12) are hardening + cosmetics.

---

*Generated by the dbt-pipeline-orchestrator after the GP Open Dataset run. See `1 - Documentation/pipeline-design.md` Section 12 (Design Decisions Log) for the chronological account of each workaround.*
