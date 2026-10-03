import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {dirname, resolve} from 'node:path'
import {fileURLToPath} from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const groups = ['plugin', 'runtime', 'eval', 'issue', 'omp']
const [{default: yaml}, {default: picomatch}] = await Promise.all([
  import('js-yaml'),
  import('picomatch'),
])
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
  return Object.fromEntries(groups.map(group => [group,
    matched.shared || matched.unknown || matched[group]]))
}

// Without these fixtures, a filter edit could silently run the wrong checks.
// The pinned action reports a rename as both the old and new path.
const fixtures = [
  {name: 'config-only', paths: ['.github/workflows/ci.yml'], expected: groups},
  {name: 'plugin component', paths: ['.claude-plugin/plugin.json'], expected: ['plugin', 'omp']},
  {name: 'Omp manifest', paths: ['.omp-plugin/plugin.json'], expected: ['omp']},
  {name: 'Omp agent alias', paths: ['agents/implementation.md'], expected: ['plugin', 'omp']},
  {name: 'runtime component', paths: ['hooks/check.py'], expected: ['runtime']},
  {name: 'eval component', paths: ['evals/experiments/classes-glm.yaml'], expected: ['runtime', 'eval', 'omp']},
  {name: 'issue component', paths: ['infra/github/labels.tf'], expected: ['issue']},
  {name: 'Omp component', paths: ['extensions/daily-driver.js'], expected: ['runtime', 'omp']},
  {name: 'mixed components', paths: ['agents/reviewer.md', 'infra/github/labels.tf'], expected: ['plugin', 'issue', 'omp']},
  {name: 'shared script', paths: ['scripts/new-validation.py'], expected: groups},
  {name: 'unknown path', paths: ['new-component/source.txt'], expected: groups},
  {name: 'unknown root file', paths: ['new-root-file.txt'], expected: groups},
  {name: 'deleted component file', paths: ['hooks/removed.py'], expected: ['runtime']},
  {name: 'cross-component rename', paths: ['omp_configs/old.yml', 'skills/new-skill/SKILL.md'], expected: ['plugin', 'runtime', 'omp']},
  {name: 'issue-labels skill', paths: ['skills/issue-labels/SKILL.md'], expected: ['plugin', 'runtime', 'issue', 'omp']},
  {name: 'docs file', paths: ['docs/notes/0001-example.md'], expected: ['plugin']},
  {name: 'root README', paths: ['README.md'], expected: ['plugin']},
  {name: 'attic file', paths: ['attic/skills/old/SKILL.md'], expected: []},
  {name: 'verse file', paths: ['HAIKU.md'], expected: []},
  {name: 'personal overlay', paths: ['omp_configs/new-model.yml'], expected: []},
  {name: 'eval shell fixtures', paths: ['evals/fixtures/example/shared/lib.sh'], expected: ['runtime', 'eval', 'omp']},
]

for (const fixture of fixtures) {
  const actual = selected(fixture.paths)
  const got = Object.keys(actual).filter(group => actual[group])
  assert.deepEqual(got, fixture.expected, fixture.name)
}

console.log('check-ci-scope: paths-filter fixtures passed')
