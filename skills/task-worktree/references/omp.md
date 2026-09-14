# Oh My Pi routes — task-worktree

`SKILL.md` names the operations. This file names how an Oh My Pi session
performs them. Claude Code's route is in [`claude.md`](claude.md), and Codex's
in [`codex.md`](codex.md).

Use the `bash` tool for the Git setup:

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

If the task branch already exists and is free, omit `-b` and put that branch
last. In a detached worktree already dedicated to the task, use `git switch
<task-branch>` when the branch exists and is free; otherwise use `git switch -c
<task-branch> <remote>/<base>`. A branch held by another worktree is a
collision to inspect, not one to force.

Set `cwd` to the task worktree on every later `bash` call. Pass absolute
task-worktree paths to `read`, `write`, `edit`, `glob`, and `grep`. Give the
same absolute path to a `task` handling a delegated slice. Verify with
`git -C <task-worktree> branch --show-current` and compare
`git -C <primary-worktree> status --short` with the setup baseline before
delivery.
