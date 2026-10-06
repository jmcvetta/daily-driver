import {execFileSync} from 'node:child_process'
import {readFileSync} from 'node:fs'
import {dirname, resolve} from 'node:path'
import {fileURLToPath} from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const [{default: yaml}, {default: picomatch}] = await Promise.all([
  import('js-yaml'),
  import('picomatch'),
])
const filters = yaml.load(readFileSync(resolve(root, '.github/ci-filters.yml'), 'utf8'))
function assertFilterMap(value) {
  if (!value || Array.isArray(value) || typeof value !== 'object' || Object.keys(value).length === 0) {
    throw new Error('CI filter map must be a non-empty mapping of check targets to pattern lists')
  }
  for (const [name, patterns] of Object.entries(value)) {
    if (!/^check-[a-z0-9-]+$/.test(name) || !Array.isArray(patterns) || patterns.length === 0 ||
        patterns.some(pattern => typeof pattern !== 'string' || pattern.length === 0)) {
      throw new Error(`invalid CI filter entry: ${name}`)
    }
  }
}

assertFilterMap(filters)
const checkNames = Object.keys(filters)
const matchers = Object.fromEntries(checkNames.map(name => [name,
  filters[name].map(pattern => {
    const exclude = pattern.startsWith('!')
    return {exclude, matches: picomatch(exclude ? pattern.slice(1) : pattern, {dot: true})}
  })]))

const workflowToolConsumers = {
  'Install Claude Code CLI': ['check-plugin', 'check-skills', 'check-agents', 'check-claude-dependency'],
  'Ensure ShellCheck': ['check-scripts'],
  'Install Worktrunk': ['check-git-sync', 'check-task-worktree-fixture', 'check-worktrunk-install'],
  'Install uv': ['check-eval-arms', 'check-agent-judges', 'check-evals-judge', 'check-evals-preflight', 'check-evals-provenance', 'check-omp-agent-settle'],
  'Install Omp': ['check-omp-plugin', 'check-omp-eval-guard-live', 'check-omp-agent-settle'],
}

function workflowChecks(base, head) {
  const before = yaml.load(git(['show', `${base}:.github/workflows/ci.yml`]).toString('utf8'))
  const after = yaml.load(git(['show', `${head}:.github/workflows/ci.yml`]).toString('utf8'))
  const beforeSteps = new Map(before.jobs['ci-success'].steps.map(step => [step.name ?? step.id ?? step.uses, step]))
  const afterSteps = new Map(after.jobs['ci-success'].steps.map(step => [step.name ?? step.id ?? step.uses, step]))
  const changed = []
  for (const name of new Set([...beforeSteps.keys(), ...afterSteps.keys()])) {
    if (JSON.stringify(beforeSteps.get(name)) === JSON.stringify(afterSteps.get(name))) continue
    changed.push(...(workflowToolConsumers[name] ?? []))
    const run = afterSteps.get(name)?.run ?? beforeSteps.get(name)?.run ?? ''
    const target = /\bmake\s+(check-[a-z0-9-]+)/.exec(run)?.[1]
    if (target && checkNames.includes(target)) changed.push(target)
  }
  return changed
}

/** Detect whether tracked files add or remove a top-level directory. */
export function hasTopLevelDirectoryChanges(beforeFiles, afterFiles) {
  const directories = files => new Set(files.filter(path => path.includes('/')).map(path => path.split('/')[0]))
  return !sameSet(directories(beforeFiles), directories(afterFiles))
}

/** Select checks for changed paths and add release validation when tracked roots change. */
export function selectChecksForDiff(paths, beforeFiles, afterFiles) {
  const selected = new Set(selectChecks(paths))
  if (hasTopLevelDirectoryChanges(beforeFiles, afterFiles)) selected.add('check-release-paths')
  return checkNames.filter(name => selected.has(name))
}

function trackedFiles(revision) {
  return git(['ls-tree', '-r', '--name-only', '-z', revision]).toString('utf8').split('\0').filter(Boolean)
}


/** Select checks whose configured path patterns match changed paths. */
export function selectChecks(paths) {
  if (!Array.isArray(paths) || paths.some(path => typeof path !== 'string' || path.includes('\0'))) {
    throw new TypeError('changed paths must be an array of NUL-free strings')
  }
  return checkNames.filter(name => {
    const patterns = matchers[name]
    return paths.some(path =>
      patterns.some(({exclude, matches}) => !exclude && matches(path)) &&
      !patterns.some(({exclude, matches}) => exclude && matches(path)))
  })
}

function git(args) {
  return execFileSync('git', args, {cwd: root, encoding: 'buffer', maxBuffer: 32 * 1024 * 1024})
}

/** Parse NUL-delimited Git name-status output, retaining both sides of renames. */
export function parseNameStatus(bytes) {
  const fields = bytes.toString('utf8').split('\0')
  const paths = []
  for (let index = 0; index < fields.length;) {
    const status = fields[index++]
    if (!status) continue
    const count = status.startsWith('R') || status.startsWith('C') ? 2 : 1
    for (let n = 0; n < count; n++) {
      const path = fields[index++]
      if (!path) throw new Error('malformed NUL-delimited git diff output')
      paths.push(path)
    }
  }
  return paths
}


function makeTargetBlocks(contents) {
  const blocks = new Map()
  let name = null
  let lines = []
  const save = () => {
    if (name) blocks.set(name, lines.filter(line => line.trim() && !line.trimStart().startsWith('#')).join('\n'))
  }
  for (const line of contents.split(/\r?\n/)) {
    const target = /^([A-Za-z0-9_.-]+):/.exec(line)
    if (target && !line.startsWith('\t')) {
      save()
      name = target[1]
      lines = [line]
    } else if (name && (line.startsWith('\t') || /\\\s*$/.test(lines.at(-1) ?? ''))) {
      lines.push(line)
    } else if (name && !line.trim()) {
      lines.push('')
    } else if (name && !line.startsWith('#')) {
      save()
      name = null
      lines = []
    }
  }
  save()
  return blocks
}

const aggregateConsumers = {
  'check-plugin-validity': ['check-plugin', 'check-skills', 'check-agents', 'check-manifests', 'check-manifest-fixtures', 'check-claude-dependency'],
  'check-runtime': ['check-constitution', 'check-ask-in-chat', 'check-omp-extension', 'check-model-class-roles', 'check-omp-guard-differential', 'check-omp-cache-clean', 'check-git-sync', 'check-task-worktree-fixture', 'check-worktrunk-install', 'check-scripts'],
  'check-eval-tooling': ['check-omp-agent', 'check-omp-eval-guard', 'check-codex-agent', 'check-eval-fixtures', 'check-model-classes-grader', 'check-model-classes-builder', 'check-eval-arms', 'check-agent-judges', 'check-evals-judge', 'check-evals-preflight', 'check-evals-provenance', 'check-evals-results', 'check-model-telemetry', 'check-evals-setup-omp'],
  'check-issue-infra': ['check-labels', 'check-labels-fixtures'],
  '__git_sync_run': ['check-git-sync'],
  'omp-update-daily-driver': ['check-omp-cache-clean'],
}

/** Select CI checks affected by changed Makefile target blocks and shared variables. */
export function changedMakeTargets(beforeText, afterText) {
  const before = makeTargetBlocks(beforeText)
  const after = makeTargetBlocks(afterText)
  const changed = new Set()
  for (const target of new Set([...before.keys(), ...after.keys()])) {
    if (before.get(target) === after.get(target)) continue
    if (checkNames.includes(target)) changed.add(target)
    for (const consumer of aggregateConsumers[target] ?? []) changed.add(consumer)
    if (target.startsWith('check-') && !checkNames.includes(target) &&
        !aggregateConsumers[target] && target !== 'check-infra') changed.add('check-ci-scope')
    if (target.startsWith('evals-run-') || target === 'evals-plan' || target === 'evals-variants') {
      changed.add('check-eval-arms')
    }
  }
  const readVar = (text, name) => {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return text.match(new RegExp(`^${escaped}\\s*[:?+]?=\\s*.*$`, 'm'))?.[0] ?? ''
  }
  if (readVar(beforeText, 'CODER_EVAL_VERSION') !== readVar(afterText, 'CODER_EVAL_VERSION')) {
    changed.add('check-omp-agent-settle')
  }
  if (['SHELL', '.SHELLFLAGS'].some(name => readVar(beforeText, name) !== readVar(afterText, name))) {
    for (const name of checkNames) changed.add(name)
  }
  return checkNames.filter(name => changed.has(name))
}

function makefileChecks(base, head) {
  return changedMakeTargets(
    git(['show', `${base}:Makefile`]).toString('utf8'),
    git(['show', `${head}:Makefile`]).toString('utf8'),
  )
}

/** Plan CI checks from a base revision and a checked-out head revision. */
export function planChecks({base, head}) {
  if (!base || !head) throw new Error('both base and head revisions are required')
  const paths = parseNameStatus(git(['diff', '--name-status', '-z', '--find-renames', base, head]))
  const selected = new Set(selectChecksForDiff(paths, trackedFiles(base), trackedFiles(head)))
  if (paths.includes('Makefile')) {
    for (const target of makefileChecks(base, head)) selected.add(target)
  }
  if (paths.includes('.github/workflows/ci.yml')) {
    for (const target of workflowChecks(base, head)) selected.add(target)
  }
  return checkNames.filter(name => selected.has(name))
}

/** Format the visible CI plan, including an explicit message for an empty plan. */
export function formatPlan(checks) {
  return `Selected CI checks: ${checks.length ? checks.join(', ') : '(none)'}`
}

function sameSet(a, b) {
  return a.size === b.size && [...a].every(value => b.has(value))
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const arg = (name) => {
    const index = process.argv.indexOf(name)
    return index < 0 ? undefined : process.argv[index + 1]
  }
  const base = arg('--base')
  const head = arg('--head')
  const checks = planChecks({base, head})
  const output = JSON.stringify(checks)
  console.log(formatPlan(checks))
  if (process.env.GITHUB_OUTPUT) {
    await import('node:fs').then(({appendFileSync}) => appendFileSync(process.env.GITHUB_OUTPUT, `checks=${output}\n`))
  }
}
