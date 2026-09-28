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

After verifying the task path and branch, use that path as the root for every
later task operation. Omp does not relocate the live session when the agent
creates a worktree, and no extension tool registers or displays a separate
task-root status. Do not invoke `/wt`: it creates another worktree and may
carry primary-checkout changes into it.

**File tools do not inherit a bash cwd change.** Omp resolves each `write`
target and each path in an `edit` payload against the session's own cwd. A
relative hashline header such as `[extensions/file.mjs#ABCD]` therefore still
targets the session root, even after a previous bash call changed directory.
Use the absolute task-worktree path in every file-tool target, including
hashline headers and move destinations; preserve the full path and snapshot
tag returned by `read`. The extension reports the supplied target, resolved
path, containing worktree, primary worktree, and branch state when it blocks a
file mutation. Follow that classification; never retry a rejected mutation
with the same relative path.

Set `cwd` to the task worktree on every later `bash` call. Pass absolute
task-worktree paths to `read`, `write`, `edit`, `glob`, and `grep`. Give the
same absolute path to a `task` handling a delegated slice. Verify with
`git -C <task-worktree> branch --show-current` and compare
`git -C <primary-worktree> status --short` with the setup baseline before
delivery.
