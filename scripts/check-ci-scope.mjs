import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {resolve} from 'node:path'
import {changedMakeTargets, formatPlan, hasTopLevelDirectoryChanges, parseNameStatus, selectChecks, selectChecksForDiff} from './ci-select.mjs'

const root = resolve(import.meta.dirname, '..')
const filters = (await import('js-yaml')).default.load(
  readFileSync(resolve(root, '.github/ci-filters.yml'), 'utf8'),
)
const targets = Object.keys(filters)

// Without these positives, an edit to a retained input could silently skip its check.
for (const [target, patterns] of Object.entries(filters)) {
  const representative = patterns.find(pattern => !pattern.startsWith('!'))
  assert.ok(selectChecks([representative.replaceAll('**', 'fixture').replaceAll('*', 'fixture')]).includes(target),
    `${target} must be selected by a mapped input`)
  assert.ok(!selectChecks(['unrelated-root-file.data']).includes(target),
    `${target} must sleep for an unrelated root file`)
}

// Without these exclusions, review-depth edits can wake unrelated fixture and adapter suites.
assert.deepEqual(selectChecks(['evals/fixtures/review-depth/shared/review.sh']), [
  'check-constitution', 'check-scripts', 'check-eval-fixtures',
])
assert.deepEqual(selectChecks(['evals/fixtures/model-classes/shared/grader.sh']), [
  'check-constitution', 'check-scripts', 'check-model-classes-grader',
])

// Without this dependency, Omp RPC changes can break transcript consumers without running them.
assert.deepEqual(selectChecks(['evals/coder-eval-omp/src/coder_eval_omp/rpc.py']), [
  'check-constitution', 'check-omp-agent', 'check-codex-agent', 'check-omp-agent-settle',
])

// Without these checks, real label changes run synthetic fixtures or unrelated suites.
assert.deepEqual(selectChecks(['infra/github/labels.tf']), ['check-labels'])
assert.deepEqual(selectChecks(['scripts/check-labels.py']), ['check-labels', 'check-labels-fixtures'])

// Without these cases, a path outside known inputs could revive the old all-check fallback.
assert.deepEqual(selectChecks(['scripts/unrelated.py']), [])
// Without this scanner dependency, numbered-step references in another workflow can drift unchecked.
assert.deepEqual(selectChecks(['.github/workflows/infra.yml']), ['check-step-names'])
assert.deepEqual(selectChecks(['CHANGELOG.md']), [])
// Without path-local exclusions, a changelog edit can mask README changes in the same commit.
assert.ok(selectChecks(['README.md', 'CHANGELOG.md']).includes('check-step-names'))
assert.deepEqual(selectChecks(['docs/notes/unclassified.txt']), [])
assert.deepEqual(selectChecks(['uv.lock']), ['check-omp-agent-settle'])
assert.deepEqual(selectChecks(['new-component/source.txt']), [])
assert.deepEqual(selectChecks(['README.md']), ['check-step-names', 'check-manifests'])
assert.deepEqual(selectChecks(['evals/fixtures/review-depth/cases/path with space/source;$(touch nope).sh']), [
  'check-constitution', 'check-scripts', 'check-eval-fixtures',
])

assert.deepEqual(selectChecks(['evals/fixtures/review-depth/cases/case\tname/source;$(id).sh']), [
  'check-constitution', 'check-scripts', 'check-eval-fixtures',
])

// Without these structural cases, release validation misses first/last tracked files and directory renames.
assert.equal(hasTopLevelDirectoryChanges(['skills/existing/SKILL.md'], ['skills/existing/SKILL.md', 'skills/new.txt']), false)
assert.equal(hasTopLevelDirectoryChanges(['skills/existing/SKILL.md'], ['skills/existing/SKILL.md', 'unclassified/new.txt']), true)
assert.equal(hasTopLevelDirectoryChanges(['old-root/file.txt', 'skills/keep.md'], ['skills/keep.md']), true)
assert.equal(hasTopLevelDirectoryChanges(['old-root/file.txt'], ['new-root/file.txt']), true)
assert.deepEqual(selectChecksForDiff(['new-component/source.txt'], ['skills/old/file.md'], [
  'skills/old/file.md', 'new-component/source.txt',
]), ['check-release-paths'])
assert.deepEqual(selectChecksForDiff(['.github/misc.txt'], ['.github/workflows/ci.yml'], [
  '.github/workflows/ci.yml', '.github/misc.txt',
]), [])

// Without these cases, incidental Makefile edits rerun unrelated checks or recipe changes go unnoticed.
const makeBefore = 'CODER_EVAL_VERSION := 0.11.6\n\ncheck-git-sync:\n\tpython3 scripts/check-git-sync.py\n\ncheck-omp-cache-clean:\n\tpython3 scripts/check-omp-cache-clean.py\n'
assert.deepEqual(changedMakeTargets(`# doc change\n${makeBefore}`, makeBefore), [])
assert.deepEqual(changedMakeTargets(makeBefore, makeBefore.replace('python3 scripts/check-git-sync.py', 'python3 scripts/check-git-sync.py --strict')), ['check-git-sync'])
assert.deepEqual(changedMakeTargets(makeBefore, makeBefore.replace('0.11.6', '0.11.7')), ['check-omp-agent-settle'])
assert.deepEqual(changedMakeTargets(makeBefore, `${makeBefore}\n__git_sync_run:\n\tgit fetch\n`), ['check-git-sync'])
assert.deepEqual(changedMakeTargets(makeBefore, `${makeBefore}\nevals-run-omp-gpt-6-luna:\n\tcoder-eval run\n`), ['check-eval-arms'])
assert.deepEqual(changedMakeTargets('SHELL := /bin/bash\n', 'SHELL := /bin/sh\n'), targets)

// Without these consumers, user-facing cache refreshes or eval-arm recipe changes can drift from CI coverage.
assert.deepEqual(changedMakeTargets(makeBefore, `${makeBefore}\nomp-update-daily-driver:\n\tomp plugin upgrade\n`), ['check-omp-cache-clean'])
assert.deepEqual(changedMakeTargets(makeBefore, `${makeBefore}\ncheck-unmapped:\n\ttrue\n`), ['check-ci-scope'])

// Without decoding status records, deletions and renames can lose the removed input or one rename side.
const deletedLabelScript = parseNameStatus(Buffer.from('D\0scripts/check-labels.py\0'))
assert.deepEqual(selectChecks(deletedLabelScript), ['check-labels', 'check-labels-fixtures'])
const renamedShell = parseNameStatus(Buffer.from('R100\0evals/fixtures/review-depth/old.sh\0evals/fixtures/model-classes/shared/new.sh\0'))
assert.deepEqual(renamedShell, ['evals/fixtures/review-depth/old.sh', 'evals/fixtures/model-classes/shared/new.sh'])
assert.deepEqual(selectChecks(renamedShell), [
  'check-constitution', 'check-scripts', 'check-eval-fixtures', 'check-model-classes-grader',
])
// Without rejecting truncated records, malformed Git output can silently omit an affected path.
assert.throws(() => parseNameStatus(Buffer.from('R100\0old.sh\0')), /malformed NUL-delimited git diff output/)
// Without treating paths as NUL-delimited data, tabs and shell metacharacters can corrupt selection.
const specialPath = 'evals/fixtures/review-depth/cases/case\tname/source;$(id).sh'
assert.deepEqual(selectChecks(parseNameStatus(Buffer.from(`M\0${specialPath}\0`))), [
  'check-constitution', 'check-scripts', 'check-eval-fixtures',
])
// Without testing both rename paths, a move into or out of a scoped filter can miss its consumer.
assert.deepEqual(selectChecks(['skills/issue-labels/SKILL.md', 'attic/issue-labels/SKILL.md']), [
  'check-step-names', 'check-skills', 'check-manifests', 'check-labels', 'check-omp-plugin',
])

// Without this inventory comparison, a removed Make target could remain scheduled or a new one go unmapped.
const makefile = readFileSync(resolve(root, 'Makefile'), 'utf8')
const declared = new Set([...makefile.matchAll(/^(check-[a-z0-9-]+):/gm)].map(match => match[1]))
const groups = new Set(['check-plugin-validity', 'check-runtime', 'check-eval-tooling', 'check-issue-infra', 'check-infra'])
assert.deepEqual([...declared].filter(target => !groups.has(target)).sort(), [...targets].sort())
// Without an explicit empty-plan line, the required job gives no visible no-work result.
assert.equal(formatPlan([]), 'Selected CI checks: (none)')
assert.match(makefile, /^check: check-ci-scope check-step-names check-release-paths check-plugin-validity check-runtime check-eval-tooling check-issue-infra$/m)

console.log(`check-ci-scope: ${targets.length} check mappings and narrow-selection fixtures passed`)
