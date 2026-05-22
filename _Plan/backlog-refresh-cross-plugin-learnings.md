# Plan — Backlog refresh from cross-plugin learnings + agent memory

## Context

The user asked: *"Check all the new learnings and failures in all the repos under the Plugin folder (also memory files for agents) and update the backlog with potential improvements to this Plugin."*

I explored four parallel sources:

1. **Dataflow to Notebook Plugin** — sibling plugin with 15 documented findings (N1–N15) in `_Documentation/plugin_learnings.md`. Several patterns (worktree footgun, AskUserQuestion main-session-only, plugin-cache read restrictions, pre-shipment audit gates, sample/dry-run mode, risk isolation cells) are battle-tested there and not yet adopted here.
2. **Fabric Migration Test / Live Test** — added empirical signals around HIGH RISK / HUMAN REVIEW cells, multi-stage validation checkpoints, unknown-pattern backlogs, DAG-first parallelization.
3. **AI-plugins marketplace** — reinforces fresh-install testing as the only acceptable validation, plus a "versioning/rollback story" gap.
4. **Agent memory files** (`projects/...-Plugins-DBT-Pipeline-Plugin/memory/` and `...-Plugins-Dataflow-to-Notebook-Plugin/memory/`) — encoded user feedback rules: atomic Bash in **all** contexts (session + generated), audit-the-full-bug-class policy, AskUserQuestion main-session-only, Norton TLS interception environment fact.

The DBT Pipeline Plugin's existing `Backlog.md` is thin (8 rows, mostly placeholders), while `Issues.md` is dense (63 IDs, many `resolved` but not yet `closed`). The gap is **forward-looking improvements** that the cross-plugin evidence now supports.

**Intended outcome:** `Backlog.md` gains ~10 concrete new backlog rows under appropriate epics (some new). `Issues.md` gains ~4 new rows for items that are actually *existing-behavior problems* surfaced by the sibling plugin's experience (e.g. plugin-shipped `hooks/remove-worktree.py` has the same untracked-file-destruction risk; reference files in `reference/` may not be readable from background subagents). One new Epic ("Cross-plugin learnings adoption") is added to group the work.

No production code changes in this plan — only documentation and tracker edits. Plugin code changes would be filed as their own plans referenced from the new backlog rows.

---

## Files to modify

- `_Plan/Backlog.md` — add new epic + ~10 rows
- `_Plan/Issues.md` — add ~4 new `I-###` rows (next sequential ID is **I-064**)
- `CLAUDE.md` — add one short subsection under "Lessons Learned" pointing at the cross-plugin learnings folder so future audits know where to look (optional; user can defer)

No script, agent, or hook code is touched in this plan.

---

## Proposed Backlog.md additions

New epic: **Cross-plugin learnings adoption** — work that ports validated patterns from the Dataflow / Fabric Migration plugins into the DBT Pipeline Plugin.

| Backlog Item | Epic | Notes |
|---|---|---|
| Audit `hooks/remove-worktree.py` for untracked-file destruction; add commit-and-merge-back step OR drop worktree isolation for builders | Architectural resilience | Sibling N8 finding. File as I-064 (risk) first; backlog item drives the fix plan. |
| Pre-ship audit suite — pytest gates: `gate_atomic_bash`, `gate_paths`, `gate_namespace`, `gate_skills_frontmatter`, `gate_plugin_manifest`, `gate_skill_md_flag_match` (consolidates I-018) | Developer tooling | Mirror sibling plugin's gate pattern. Each gate is a regression-prevention check. |
| Bundle a tiny 3-table sample dataset + `--dry-run`/`--sample` orchestrator flag so first-run smoke test needs no live DB | Production readiness | Replaces vague "build smoke test" row. Covers Issue I-002 indirectly. |
| Add HIGH RISK / HUMAN REVIEW comment-block convention to builder agents (staging/dim/fact/test-writer) for ambiguous patterns | Code hygiene | Sibling Fabric Migration N5 + Dataflow N5. Stops silent best-effort outputs. |
| Add `_Documentation/sql-pattern-backlog.md` — running catalog of T-SQL patterns that need future plugin support; builder agents auto-append unknown forms | Documentation | Mirrors Fabric Migration's M-pattern backlog. |
| Add `dbt parse` / DAG-resolution gate before Stage 7 parallel staging fan-out | Production readiness | Fabric Migration showed parallelization is only safe after a clean dependency inventory. |
| Trust-but-verify post-spawn artifact check: after each background `Task` returns, orchestrator atomically `ls` the claimed output paths and HALTs on miss (already partial via I-057 for dim/fact deviations — extend to staging + test-writer) | Architectural resilience | Hardens against silent envelope-claims-but-file-missing class. |
| Dynamic question selection in business-analyst — skip irrelevant questions based on profile inventory (no CSVs → skip CSV-specific question, etc.) | UX | Sibling N4. Reduces from 4 generic to 1–2 specific touchpoints when applicable. |
| Setup-CorpCertBundle helper script + README section for users behind corporate TLS interception (Norton, Zscaler, etc.) | Production readiness | Sibling N12 + agent memory environment note. Currently invisible to first-run users. |
| Document the "bug-class audit" policy formally in CLAUDE.md and reference it from Issues.md `Anti-patterns` block (also enshrine in Issue I-021 follow-up) | Documentation | Agent memory `feedback_audit_bug_class.md` captures the rule; codify in repo so future agents/contributors apply it. |
| Versioning + rollback story: tag releases on git, document how a user pins to an older version when the marketplace pulls latest | Production readiness | Surfaced in AI-plugins marketplace exploration; no rollback path currently exists. |
| Periodic audit of plugin-shipped restrictions (what fields are silently stripped from agent frontmatter beyond `hooks`/`mcpServers`/`permissionMode`) | Architectural resilience | I-016 already exists; backlog row drives the recurring audit cadence. |

---

## Proposed Issues.md additions (next IDs starting at I-064)

These are *existing-behavior problems* discovered via cross-plugin evidence — they belong in the issue tracker per CLAUDE.md policy, not in Backlog.md.

| ID | Title | Category | Severity | Notes |
|---|---|---|---|---|
| I-064 | `hooks/remove-worktree.py` runs `git worktree remove --force` with no merge-back; destroys untracked files written by background builders | risk | high | Sibling plugin (Dataflow) hit this as N8. This plugin uses worktree isolation in `hooks/create-worktree.py` + `hooks/remove-worktree.py`. Verify whether any builder writes untracked files (likely yes — `models/**/*.sql` is git-tracked, but `target/`, `logs/`, profile JSONs may not be). |
| I-065 | Background subagents may not be able to read plugin-cache paths like `${CLAUDE_PLUGIN_ROOT}/reference/examples/*.md` — affects how builders consume style guides | empirical | high | Dataflow N14 documents this for `${CLAUDE_PLUGIN_ROOT}/reference/risk-catalog.md`. The DBT plugin's builders reference `reference/sql-style-guide.md` and `reference/examples/dimension-models.md` from `agent.md` bodies. Test on fresh install: have a spawned specialist quote a known string from those reference files. If it can't, copy reference into the project at scaffold time. |
| I-066 | Agent memory `feedback_audit_bug_class.md` rule is not enshrined in CLAUDE.md — future contributors won't apply it | docs | medium | Rule: when finding a bug matching a prior resolved pattern, grep the entire plugin first, file one issue covering full scope, fix all instances in one pass. Currently lives only in user memory. |
| I-067 | No documented user-facing path for corporate TLS interception (Norton/Zscaler) — Python skills using `requests` / `certifi` fail silently with cert errors | docs | medium | Agent memory captures this environment fact for this user. Other users hitting Norton or similar will have an identical symptom with no troubleshooting hint in the README. |

---

## Critical files referenced (read-only in plan; edited only in execution)

- `_Plan/Backlog.md:1-38` — current backlog table + epic descriptions
- `_Plan/Issues.md:24-107` — open issue tracker; next ID is I-064
- `CLAUDE.md:67-243` — Issue Tracker Maintenance policy + Lessons Learned section (where the new audit-bug-class subsection would land)
- `hooks/remove-worktree.py` — to be read in execution to confirm whether the `--force` removal really destroys untracked files (I-064 verification)
- `reference/sql-style-guide.md` and `reference/examples/dimension-models.md` — referenced by builder `agent.md` bodies; subject of I-065 empirical test
- Sibling **Dataflow to Notebook Plugin** — its `_Documentation/plugin_learnings.md` (N1–N15) is the source material to cite in commit messages
- Project-specific Claude Code auto-memory feedback entries (`feedback_audit_bug_class.md`, `feedback_bash_atomic_scope.md`) — source material for I-066 codification; codified into this repo's `CLAUDE.md` so the rule no longer depends on local machine state

---

## Verification

After execution:

1. `Backlog.md` table parses cleanly (single row per item, all 5 columns populated). Cross-reference each new row against the listed epic.
2. `Issues.md` IDs I-064 → I-067 added in correct table sections (`Architectural risks`, `Empirical verification needs`, `Documentation gaps`).
3. No duplicate row IDs across the file. `grep -E "^\| I-[0-9]+" _Plan/Issues.md` shows monotonically increasing IDs with no gaps below I-064.
4. CLAUDE.md (if updated) gains a "Bug-class audit policy" subsection referenced by the new Issues.md anti-patterns block.
5. Spot-check: pick 3 new backlog rows and confirm the linked issue ID (where applicable) actually exists in `Issues.md`.

End-to-end: open `Backlog.md` in a markdown preview, confirm the new "Cross-plugin learnings adoption" epic appears below the existing epics with rationale, and that each new row has a clear next-step trail back to either a research file or a sibling-plugin learning citation.

---

## Out of scope (explicitly)

- No code changes to hooks, agents, skills, or scripts in this plan. Each new backlog/issue row will spawn its own follow-up plan when prioritized.
- No archive sweep of resolved-but-not-closed issues — that's a separate weekly cadence task.
- No editing of sibling plugins. They remain authoritative sources; we only port patterns.
- No fresh-install verification run in this plan — I-065 requires that as a follow-up.
