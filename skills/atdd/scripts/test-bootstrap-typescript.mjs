import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const script = fileURLToPath(new URL('./bootstrap-typescript.mjs', import.meta.url));
const root = resolve(dirname(script), '../../..');
const rootManifest = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
const versions = { '@cucumber/cucumber': '13.3.0', tsx: '4.23.15' };
const command = 'cucumber-js --config acceptance/cucumber.json';
const offlineEnvironment = {
  ...process.env,
  npm_config_offline: 'true',
  npm_config_audit: 'false',
  npm_config_fund: 'false',
  npm_config_update_notifier: 'false',
  npm_config_registry: 'http://127.0.0.1:1',
};

function fixture(t, { manager = 'npm', type = 'module', manifest = true, locks = true } = {}) {
  const directory = mkdtempSync(join(tmpdir(), 'daily-driver-atdd-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const repository = join(directory, 'repository with spaces');
  mkdirSync(repository);
  if (manifest) writeFileSync(join(repository, 'package.json'), `${JSON.stringify({ name: 'offline-atdd-fixture', private: true, ...(type === null ? {} : { type }) }, null, 2)}\n`);
  if (locks) writeFileSync(join(repository, manager === 'npm' ? 'package-lock.json' : 'pnpm-lock.yaml'), manager === 'npm' ? '{"lockfileVersion":3}\n' : "lockfileVersion: '9.0'\n");
  return { directory, repository };
}

function transport(directory) {
  const bin = join(directory, 'bin');
  const log = join(directory, 'package-manager.jsonl');
  mkdirSync(bin);
  // Only package-manager transport is scripted. Behavioral tests below execute real npm and Cucumber.
  const source = `#!${process.execPath}
const fs = require('node:fs');
const path = require('node:path');
const args = process.argv.slice(2);
const manager = path.basename(process.argv[1]);
fs.appendFileSync(process.env.ATDD_COMMAND_LOG, JSON.stringify({ manager, args, cwd: process.cwd() }) + '\\n');
if (process.env.ATDD_FAIL_MANAGER === manager) process.exit(17);
const file = path.join(process.cwd(), 'package.json');
const manifest = JSON.parse(fs.readFileSync(file, 'utf8'));
if (args[0] === 'pkg' && args[1] === 'set' && args[2].startsWith('scripts.acceptance=')) {
  manifest.scripts = { ...manifest.scripts, acceptance: args[2].slice('scripts.acceptance='.length) };
} else if (args[0] === 'install' || args[0] === 'add') {
  manifest.devDependencies = { ...manifest.devDependencies };
  for (const specifier of args.slice(3)) {
    const separator = specifier.lastIndexOf('@');
    manifest.devDependencies[specifier.slice(0, separator)] = specifier.slice(separator + 1);
  }
} else {
  throw new Error('Unexpected package-manager command: ' + args.join(' '));
}
fs.writeFileSync(file, JSON.stringify(manifest, null, 2) + '\\n');
`;
  for (const manager of ['npm', 'pnpm']) {
    writeFileSync(join(bin, manager), source);
    chmodSync(join(bin, manager), 0o755);
  }
  return {
    env: { ...offlineEnvironment, PATH: `${bin}:${process.env.PATH}`, ATDD_COMMAND_LOG: log },
    commands: () => existsSync(log) ? readFileSync(log, 'utf8').trim().split('\n').map(line => JSON.parse(line)) : [],
  };
}

function bootstrap(repository, { noInstall = false, env = offlineEnvironment, arguments: arguments_ } = {}) {
  return spawnSync(process.execPath, [script, ...(arguments_ ?? [...(noInstall ? ['--no-install'] : []), repository])], { env, encoding: 'utf8', timeout: 30_000 });
}

function succeeded(result) {
  assert.ifError(result.error);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
}

function refused(result, message) {
  assert.ifError(result.error);
  assert.notEqual(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stderr, message);
}

function readConfig(repository) {
  return JSON.parse(readFileSync(join(repository, 'acceptance/cucumber.json'), 'utf8')).default;
}

function snapshot(directory, prefix = '') {
  return Object.fromEntries(readdirSync(directory).flatMap(name => {
    const relative = prefix ? `${prefix}/${name}` : name;
    const path = join(directory, name);
    if (statSync(path).isDirectory()) return Object.entries(snapshot(path, relative));
    return [[relative, { content: readFileSync(path, 'utf8'), modified: statSync(path).mtimeMs }]];
  }));
}

for (const manager of ['npm', 'pnpm']) {
  test(`${manager} pins the root-approved versions and does not use the other package manager`, t => {
    for (const [name, version] of Object.entries(versions)) assert.equal(rootManifest.devDependencies[name], version);
    const { directory, repository } = fixture(t, { manager });
    const scripted = transport(directory);
    succeeded(bootstrap(repository, { env: scripted.env }));
    assert.deepEqual(scripted.commands(), [
      { manager, args: [manager === 'npm' ? 'install' : 'add', '--save-dev', '--save-exact', ...Object.entries(versions).map(([name, version]) => `${name}@${version}`)], cwd: repository },
      { manager, args: ['pkg', 'set', `scripts.acceptance=${command}`], cwd: repository },
    ]);
    const manifest = JSON.parse(readFileSync(join(repository, 'package.json'), 'utf8'));
    assert.deepEqual(manifest.devDependencies, versions);
    assert.equal(manifest.scripts.acceptance, command);
    assert.deepEqual(readConfig(repository), {
      paths: ['acceptance/features/**/*.feature'], format: ['progress'], publish: false,
      import: ['acceptance/support/register.mjs', 'acceptance/steps/**/*.ts', 'acceptance/support/**/*.ts'],
    });
    const before = snapshot(repository);
    succeeded(bootstrap(repository, { env: scripted.env }));
    assert.deepEqual(snapshot(repository), before, 'reruns must not rewrite manifests, lockfiles, or harness files');
    assert.equal(scripted.commands().length, 2, 'reruns must not reinstall or reset the same command');
  });

  test(`${manager} --no-install changes the package script without installing or replacing existing product files`, t => {
    const { directory, repository } = fixture(t, { manager, type: 'commonjs' });
    const scripted = transport(directory);
    for (const [path, content] of [['features/owned.feature', 'Feature: Existing product contract\n'], ['steps/owned.ts', '// Product binding\n'], ['support/owned.ts', '// Product support\n']]) {
      mkdirSync(dirname(join(repository, 'acceptance', path)), { recursive: true });
      writeFileSync(join(repository, 'acceptance', path), content);
    }
    const before = snapshot(join(repository, 'acceptance'));
    succeeded(bootstrap(repository, { noInstall: true, env: scripted.env }));
    assert.deepEqual(scripted.commands(), [{ manager, args: ['pkg', 'set', `scripts.acceptance=${command}`], cwd: repository }]);
    const after = snapshot(join(repository, 'acceptance'));
    for (const [path, entry] of Object.entries(before)) assert.deepEqual(after[path], entry);
    assert.deepEqual(Object.keys(after).sort(), ['cucumber.json', ...Object.keys(before)].sort());
    assert.equal(JSON.parse(readFileSync(join(repository, 'package.json'), 'utf8')).devDependencies, undefined);
    assert.deepEqual(readConfig(repository), {
      paths: ['acceptance/features/**/*.feature'], format: ['progress'], publish: false,
      requireModule: ['tsx/cjs'], require: ['acceptance/steps/**/*.ts', 'acceptance/support/**/*.ts'],
    });
    const firstRun = snapshot(repository);
    succeeded(bootstrap(repository, { noInstall: true, env: scripted.env }));
    assert.deepEqual(snapshot(repository), firstRun);
    assert.equal(scripted.commands().length, 1);
    const harness = snapshot(join(repository, 'acceptance'));
    succeeded(bootstrap(repository, { env: scripted.env }));
    assert.deepEqual(snapshot(join(repository, 'acceptance')), harness, 'installing after offline setup must preserve the harness and product files');
    assert.deepEqual(scripted.commands().at(-1), {
      manager, args: [manager === 'npm' ? 'install' : 'add', '--save-dev', '--save-exact', ...Object.entries(versions).map(([name, version]) => `${name}@${version}`)], cwd: repository,
    });
    assert.deepEqual(JSON.parse(readFileSync(join(repository, 'package.json'), 'utf8')).devDependencies, versions);
  });
}

for (const conflict of ['cucumber.json', 'cucumber.yaml', 'cucumber.yml', 'cucumber.js', 'cucumber.cjs', 'cucumber.mjs', 'acceptance/cucumber.json']) {
  test(`refuses existing ${conflict} instead of replacing another harness`, t => {
    const { directory, repository } = fixture(t);
    const scripted = transport(directory);
    mkdirSync(dirname(join(repository, conflict)), { recursive: true });
    writeFileSync(join(repository, conflict), 'existing configuration\n');
    const before = snapshot(repository);
    refused(bootstrap(repository, { env: scripted.env }), /Existing .*cucumber\./);
    assert.deepEqual(snapshot(repository), before);
    assert.deepEqual(scripted.commands(), []);
  });
}

for (const alteration of ['configuration', 'command', 'registration', 'missing registration']) {
  test(`refuses an altered bootstrap ${alteration} instead of silently resetting operator choices`, t => {
    const { directory, repository } = fixture(t);
    const scripted = transport(directory);
    succeeded(bootstrap(repository, { noInstall: true, env: scripted.env }));
    if (alteration === 'configuration') writeFileSync(join(repository, 'acceptance/cucumber.json'), '{"default":{"publish":false}}\n');
    if (alteration === 'command') {
      const manifest = JSON.parse(readFileSync(join(repository, 'package.json'), 'utf8'));
      manifest.scripts.acceptance = 'custom acceptance';
      writeFileSync(join(repository, 'package.json'), JSON.stringify(manifest));
    }
    if (alteration === 'registration') writeFileSync(join(repository, 'acceptance/support/register.mjs'), '// Operator loader\n');
    if (alteration === 'missing registration') rmSync(join(repository, 'acceptance/support/register.mjs'));
    const before = snapshot(repository);
    refused(bootstrap(repository, { noInstall: true, env: scripted.env }), /Existing acceptance\/cucumber.json/);
    assert.deepEqual(snapshot(repository), before);
    assert.equal(scripted.commands().length, 1);
  });
}

for (const evidence of ['missing manifest', 'invalid manifest', 'no lockfile', 'both lockfiles', 'unsupported type', 'existing command', 'registration conflict', 'directory conflict']) {
  test(`refuses ${evidence} before package-manager side effects instead of guessing or overwriting`, t => {
    const { directory, repository } = fixture(t, { manifest: evidence !== 'missing manifest', locks: evidence !== 'no lockfile' });
    const scripted = transport(directory);
    let expected;
    switch (evidence) {
      case 'missing manifest': expected = /Missing .*package.json/; break;
      case 'invalid manifest': writeFileSync(join(repository, 'package.json'), '{'); expected = /Cannot read .*package.json/; break;
      case 'no lockfile': expected = /exactly one.*found 0/; break;
      case 'both lockfiles': writeFileSync(join(repository, 'pnpm-lock.yaml'), 'lockfileVersion: 9\n'); expected = /exactly one.*found 2/; break;
      case 'unsupported type': writeFileSync(join(repository, 'package.json'), '{"type":"unsupported"}'); expected = /Unsupported package type/; break;
      case 'existing command': writeFileSync(join(repository, 'package.json'), '{"scripts":{"acceptance":"existing command"}}'); expected = /Existing scripts.acceptance/; break;
      case 'registration conflict': mkdirSync(join(repository, 'acceptance/support'), { recursive: true }); writeFileSync(join(repository, 'acceptance/support/register.mjs'), '// Existing loader\n'); expected = /Existing acceptance\/support\/register.mjs/; break;
      case 'directory conflict': mkdirSync(join(repository, 'acceptance')); writeFileSync(join(repository, 'acceptance/features'), 'not a directory'); expected = /acceptance\/features is not a directory/; break;
    }
    const before = snapshot(repository);
    refused(bootstrap(repository, { env: scripted.env }), expected);
    assert.deepEqual(snapshot(repository), before);
    assert.deepEqual(scripted.commands(), []);
  });
}

test('creates only reusable harness files instead of claiming acceptance with a toy or pending product scenario', t => {
  const { directory, repository } = fixture(t);
  const scripted = transport(directory);
  succeeded(bootstrap(repository, { noInstall: true, env: scripted.env }));
  assert.deepEqual(Object.keys(snapshot(join(repository, 'acceptance'))).sort(), ['cucumber.json', 'support/register.mjs']);
  assert.deepEqual(readdirSync(join(repository, 'acceptance/features')), []);
  assert.deepEqual(readdirSync(join(repository, 'acceptance/steps')), []);
});

test('reports an unavailable detected package manager instead of falling back to another manager', t => {
  const { directory, repository } = fixture(t, { manager: 'pnpm' });
  const emptyPath = join(directory, 'empty-bin');
  mkdirSync(emptyPath);
  refused(bootstrap(repository, { noInstall: true, env: { ...offlineEnvironment, PATH: emptyPath } }), /Cannot run pnpm:.*Install the detected package manager/);
  assert.equal(existsSync(join(repository, 'acceptance')), false);
});

test('reports package-manager failure without claiming or writing a working harness', t => {
  const { directory, repository } = fixture(t);
  const scripted = transport(directory);
  refused(bootstrap(repository, { env: { ...scripted.env, ATDD_FAIL_MANAGER: 'npm' } }), /failed \(17\)/);
  assert.equal(existsSync(join(repository, 'acceptance')), false);
});

test('rejects ambiguous or unknown CLI arguments instead of bootstrapping the wrong repository', t => {
  const { repository } = fixture(t);
  for (const args of [[], ['--unknown', repository], [repository, repository], ['--no-install', '--no-install', repository]]) {
    refused(bootstrap(repository, { arguments: args }), /Usage:/);
  }
  assert.equal(existsSync(join(repository, 'acceptance')), false);
});

for (const type of ['module', 'commonjs', undefined]) {
  test(`${type ?? 'absent type'} runs real TypeScript Cucumber green, rejects a consequential wrong increment, then returns green offline`, t => {
    const { repository } = fixture(t, { type: type ?? null });
    symlinkSync(join(root, 'node_modules'), join(repository, 'node_modules'), 'dir');
    succeeded(bootstrap(repository, { noInstall: true }));
    mkdirSync(join(repository, 'src'));
    const implementation = join(repository, 'src/increment.ts');
    const correct = 'export function increment(value: number): number { return value + 1; }\n';
    writeFileSync(implementation, correct);
    writeFileSync(join(repository, 'acceptance/features/increment.feature'), 'Feature: Increment\n  Scenario: Increment an integer\n    Given the starting value is 41\n    When I increment the value\n    Then the result is 42\n');
    writeFileSync(join(repository, 'acceptance/support/input.ts'), "import { Before } from '@cucumber/cucumber';\nBefore(function () { this.input = 40; });\n");
    writeFileSync(join(repository, 'acceptance/steps/increment.ts'), `import assert from 'node:assert/strict';
import { Given, When, Then } from '@cucumber/cucumber';
import { increment } from '../../src/increment.ts';
Given('the starting value is {int}', function (value: number) {
  assert.equal(this.input, 40, 'the TypeScript support hook must execute');
  this.input = value;
});
When('I increment the value', function () { this.result = increment(this.input); });
Then('the result is {int}', function (expected: number) { assert.equal(this.result, expected); });
`);
    function acceptance() {
      return spawnSync('npm', ['run', 'acceptance'], { cwd: repository, env: offlineEnvironment, encoding: 'utf8', timeout: 30_000 });
    }
    const initial = acceptance();
    succeeded(initial);
    assert.match(initial.stdout, /1 scenario \(1 passed\)/);
    assert.match(initial.stdout, /4 steps \(4 passed\)/);
    writeFileSync(implementation, 'export function increment(value: number): number { return value; }\n');
    const red = acceptance();
    assert.ifError(red.error);
    assert.notEqual(red.status, 0, `${red.stdout}\n${red.stderr}`);
    assert.match(red.stdout, /1 scenario \(1 failed\)/);
    assert.match(red.stdout, /41 !== 42/);
    writeFileSync(implementation, correct);
    const repaired = acceptance();
    succeeded(repaired);
    assert.match(repaired.stdout, /1 scenario \(1 passed\)/);
  });
}
