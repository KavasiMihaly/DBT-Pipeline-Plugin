"""WorktreeCreate hook — creates a git worktree for agent isolation.
Auto-initializes git if the repo isn't a git repository yet.
Prints the absolute worktree path to stdout (required by Claude Code).
"""

import json
import os
import subprocess
import sys
import uuid


def run_git(args, cwd):
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result


def main():
    data = json.load(sys.stdin)
    # Generate a unique worktree ID if none provided — prevents collisions
    # when multiple agents spawn worktrees in parallel
    worktree_id = data.get("worktree_id") or f"wt-{uuid.uuid4().hex[:8]}"
    base_branch = data.get("base_branch", "main")
    cwd = data.get("cwd", os.getcwd())

    # Auto-init git if not a repo
    check = run_git(["rev-parse", "--git-dir"], cwd)
    if check.returncode != 0:
        run_git(["init"], cwd)
        run_git(["add", "-A"], cwd)
        run_git(["commit", "-m", "Initial scaffold for worktree support", "--allow-empty"], cwd)

    # Ensure we have at least one commit (bare init edge case)
    log = run_git(["log", "--oneline", "-1"], cwd)
    if log.returncode != 0:
        run_git(["add", "-A"], cwd)
        run_git(["commit", "-m", "Initial scaffold for worktree support", "--allow-empty"], cwd)

    # Resolve current branch name for base
    branch_check = run_git(["branch", "--show-current"], cwd)
    if branch_check.returncode == 0 and branch_check.stdout.strip():
        base_branch = branch_check.stdout.strip()

    # Create worktree path
    worktree_path = os.path.join(cwd, ".claude", "worktrees", worktree_id)
    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

    # Create the worktree (detached so we don't need a new branch)
    result = run_git(["worktree", "add", "--detach", worktree_path, base_branch], cwd)
    if result.returncode != 0:
        print(f"Error creating worktree: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Print absolute path to stdout (required)
    print(os.path.abspath(worktree_path))


if __name__ == "__main__":
    main()
