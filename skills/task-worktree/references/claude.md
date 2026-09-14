# Claude Code routes — task-worktree

`SKILL.md` names the operations. This file names how a Claude Code session
performs them. Oh My Pi's route is in [`omp.md`](omp.md), and Codex's in
[`codex.md`](codex.md).

Use `Bash` for the Git setup:

```sh
git rev-parse --show-toplevel
git branch --show-current
git worktree list --porcelain
git remote
git config --get remote.pushDefault
git symbolic-ref --short refs/remotes/<remote>/HEAD
git -C <primary-worktree> status --short
git worktree add -b <task-branch> <sibling-path> <remote>/<base>
```

The first entry from `git worktree list --porcelain` is the primary worktree.
Use the remote declared by the task or repository, then `remote.pushDefault`,
then the only configured remote. More than one unexplained remote is a stop,
not permission to assume `origin`. Keep the full remote-tracking name returned
for `<remote>/HEAD` as the start point.

Where `mcp__Claude_Code_Remote__get_session` designates exactly one branch for
this task, use it as `<task-branch>`. Otherwise follow the project's convention,
then derive the short name from the issue or task.

If the task branch already exists and is free, omit `-b` and put that branch
last. In a detached worktree already dedicated to the task, use `git switch
<task-branch>` when the branch exists and is free; otherwise use `git switch -c
<task-branch> <remote>/<base>`. A branch held by another worktree is a
collision to inspect, not one to force.

`Bash` does not relocate the session for later calls. Prefix each later shell
command with `cd <task-worktree> &&`, or use a command's own directory option.
Pass absolute task-worktree paths to `Read`, `Write`, `Edit`, `Glob`, and
`Grep`. Give the same absolute path to an `Agent` handling a delegated slice.
Verify with `git -C <task-worktree> branch --show-current` and compare
`git -C <primary-worktree> status --short` with the setup baseline before
delivery.
