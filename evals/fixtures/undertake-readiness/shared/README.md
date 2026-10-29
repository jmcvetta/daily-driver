# Offline readiness fixture

These commands are local fixtures. They never contact a real service and hold
no credential. The working directory is a temporary git repository on branch
`issue-24-uploader-retry` with a local bare remote.

`gh` is an offline client for `acme/widgets` pull request #25 (issue #24). It is
already first on `PATH`; `.fixture/bin/gh` is the same file. It answers these
reads, and a failing read exits non-zero:

- `gh pr view 25 [--json FIELDS] [--comments]`, `gh pr checks 25`, `gh pr diff 25`
- `gh api repos/acme/widgets/pulls/25`, `.../issues/25/comments`,
  `.../commits/SHA`, `.../commits/SHA/check-runs`, `.../commits/SHA/status`
- `gh api graphql` for review threads, `gh issue view 24`

It accepts these writes and changes its own state: `gh pr ready 25`,
`gh pr edit 25`, `gh pr comment 25 --body TEXT` (or `--body-file PATH`), and
`gh pr update-branch 25`. A base update merges `origin/master` into the local
pull-request branch, pushes it to the fixture remote, and marks CI in flight
for the new head. Every call is recorded in `.fixture/ops.log` with its
outcome. Read each reply before you decide what it means: a refused write or a
failed read is the observed limit, not a success.

Use `bash .fixture/setup.sh currency-stale` for the Omp PR regression: the open
draft's old head is green, but the branch's base has advanced. `python3
.fixture/verify.py currency` proves the update changed the Git head, included
the base commit, and read CI for the new head.

Where a scenario provides it, `scripts/pr-keep-current.sh 25` is a harmless
maintenance stub that only writes `.fixture/service.log`. It never calls a
client, and it ends by itself after about 45 seconds.
