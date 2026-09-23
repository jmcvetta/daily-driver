import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {readFileSync} from 'node:fs'
import {dirname, resolve} from 'node:path'
import {fileURLToPath} from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const jobs = ['plugin', 'runtime', 'eval', 'issue', 'omp']

function verifyAggregate(env) {
  if (env.DETECTION !== 'success' || env.REPOSITORY !== 'success') return false
  for (const name of jobs) {
    const selectedValue = env[`${name.toUpperCase()}_SELECTED`]
    const result = env[`${name.toUpperCase()}_RESULT`]
    if (!['true', 'false'].includes(selectedValue)) return false
    if (selectedValue === 'true' && result !== 'success') return false
    if (selectedValue === 'false' && result !== 'skipped') return false
  }
  return true
}

if (process.argv[2] === '--aggregate') {
  if (!verifyAggregate(process.env)) {
    console.error('CI Success rejected a failed, skipped, cancelled, or invalid required job')
    process.exitCode = 1
  }
} else {
  const [{default: yaml}, {default: picomatch}] = await Promise.all([
    import('js-yaml'),
    import('picomatch'),
  ])
  const workflowText = readFileSync(resolve(root, '.github/workflows/ci.yml'), 'utf8')
  const workflow = yaml.load(workflowText)
  const filters = yaml.load(readFileSync(resolve(root, '.github/ci-filters.yml'), 'utf8'))

  function filterMatches(patterns, paths) {
    const include = patterns.filter(pattern => !pattern.startsWith('!'))
    const exclude = patterns.filter(pattern => pattern.startsWith('!')).map(pattern => pattern.slice(1))
    return paths.some(path => include.some(pattern => picomatch(pattern, {dot: true})(path)) &&
      !exclude.some(pattern => picomatch(pattern, {dot: true})(path)))
  }

  function selected(paths) {
    const matched = Object.fromEntries(Object.entries(filters).map(([name, patterns]) =>
      [name, filterMatches(patterns, paths)]))
    return Object.fromEntries(jobs.map(job => [job,
      matched.shared || matched.unknown || matched[job]]))
  }

  // The pinned action reports a rename as both the old and new path.
  const fixtures = [
    {name: 'config-only', paths: ['.github/workflows/ci.yml'], expected: jobs},
    {name: 'plugin component', paths: ['.claude-plugin/plugin.json'], expected: ['plugin', 'omp']},
    {name: 'runtime component', paths: ['hooks/check.py'], expected: ['runtime']},
    {name: 'eval component', paths: ['omp_configs/personal.yml'], expected: ['eval']},
    {name: 'issue component', paths: ['infra/github/labels.tf'], expected: ['issue']},
    {name: 'Omp component', paths: ['extensions/daily-driver.js'], expected: ['runtime', 'omp']},
    {name: 'mixed components', paths: ['agents/reviewer.md', 'infra/github/labels.tf'], expected: ['plugin', 'issue']},
    {name: 'shared script', paths: ['scripts/new-validation.py'], expected: jobs},
    {name: 'unknown path', paths: ['new-component/source.txt'], expected: jobs},
    {name: 'unknown root file', paths: ['new-root-file.txt'], expected: jobs},
    {name: 'deleted component file', paths: ['hooks/removed.py'], expected: ['runtime']},
    {name: 'cross-component rename', paths: ['omp_configs/old.yml', 'skills/new-skill/SKILL.md'], expected: ['plugin', 'runtime', 'eval', 'issue', 'omp']},
    {name: 'new model overlay', paths: ['omp_configs/new-model.yml'], expected: ['eval']},
  ]
  for (const fixture of fixtures) {
    const actual = selected(fixture.paths)
    const got = Object.keys(actual).filter(job => actual[job])
    assert.deepEqual(got, fixture.expected, fixture.name)
  }
  assert.equal(workflow.jobs.changes.permissions['pull-requests'], 'read')
  assert.equal(workflow.jobs['ci-success'].if, 'always()')
  assert.equal(workflow.jobs['ci-success'].name, 'CI Success')
  assert.deepEqual(workflow.jobs['ci-success'].needs, [
    'changes', 'repository-checks', 'plugin-validity', 'runtime',
    'eval-tooling', 'issue-infra', 'omp-integration',
  ])
  assert.match(workflowText, /dorny\/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d/)
  assert.match(workflowText, /predicate-quantifier: some-with-excludes/)

  function aggregateCase(name, values, expected) {
    const result = spawnSync(process.execPath, [fileURLToPath(import.meta.url), '--aggregate'], {
      cwd: root,
      env: {...process.env, ...values},
      encoding: 'utf8',
    })
    assert.equal(result.status === 0, expected, `aggregate case ${name}: ${result.stderr}`)
  }
  const valid = {DETECTION: 'success', REPOSITORY: 'success'}
  for (const job of jobs) {
    valid[`${job.toUpperCase()}_SELECTED`] = job === 'eval' ? 'true' : 'false'
    valid[`${job.toUpperCase()}_RESULT`] = job === 'eval' ? 'success' : 'skipped'
  }
  aggregateCase('intentional skips', valid, true)
  for (const [name, selectedValue, resultValue] of [
    ['selected failure', 'true', 'failure'],
    ['selected skip', 'true', 'skipped'],
    ['selected cancellation', 'true', 'cancelled'],
    ['unselected run', 'false', 'success'],
  ]) {
    aggregateCase(name, {...valid, PLUGIN_SELECTED: selectedValue, PLUGIN_RESULT: resultValue}, false)
  }
  aggregateCase('detection failure', {...valid, DETECTION: 'failure'}, false)
  aggregateCase('unconditional failure', {...valid, REPOSITORY: 'failure'}, false)
  aggregateCase('missing selection output', {...valid, EVAL_SELECTED: ''}, false)
  console.log('check-ci-scope: paths-filter fixtures and CI Success contract passed')
}
