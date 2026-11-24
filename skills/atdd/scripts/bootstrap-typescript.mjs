#!/usr/bin/env node
import { existsSync, lstatSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const acceptanceCommand = 'cucumber-js --config acceptance/cucumber.json';
const registration = "import { register } from 'tsx/esm/api';\n\nregister();\n";
const rootConfigurations = ['cucumber.json', 'cucumber.yaml', 'cucumber.yml', 'cucumber.js', 'cucumber.cjs', 'cucumber.mjs'];

function present(path) {
  try {
    lstatSync(path);
    return true;
  } catch (error) {
    if (error.code === 'ENOENT') return false;
    throw error;
  }
}

function readManifest(path) {
  if (!existsSync(path)) throw new Error(`Missing ${path}. Choose a repository with package.json.`);
  try {
    const manifest = JSON.parse(readFileSync(path, 'utf8'));
    if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) throw new Error('expected an object');
    return manifest;
  } catch (error) {
    throw new Error(`Cannot read ${path}: ${error.message}. Repair the package manifest first.`);
  }
}

function run(manager, args, target) {
  const result = spawnSync(manager, args, { cwd: target, stdio: 'inherit' });
  if (result.error) throw new Error(`Cannot run ${manager}: ${result.error.message}. Install the detected package manager and retry.`);
  if (result.status !== 0) throw new Error(`${manager} ${args.join(' ')} failed (${result.signal ?? result.status}). Repair the package-manager error and retry; no harness configuration was written.`);
}

function main() {
  const args = process.argv.slice(2);
  const noInstall = args.includes('--no-install');
  const targets = args.filter(argument => !argument.startsWith('--'));
  if (targets.length !== 1 || args.some(argument => argument.startsWith('--') && argument !== '--no-install') || args.filter(argument => argument === '--no-install').length > 1) {
    throw new Error('Usage: node bootstrap-typescript.mjs [--no-install] <target-repository>');
  }
  const target = resolve(targets[0]);
  const manifest = readManifest(join(target, 'package.json'));
  const locks = ['package-lock.json', 'pnpm-lock.yaml'].filter(name => present(join(target, name)));
  if (locks.length !== 1) throw new Error(`Expected exactly one of package-lock.json or pnpm-lock.yaml in ${target}; found ${locks.length}. Keep the repository's authoritative lockfile, or initialize one with npm or pnpm before retrying.`);
  const manager = locks[0] === 'package-lock.json' ? 'npm' : 'pnpm';
  if (manifest.type !== undefined && manifest.type !== 'module' && manifest.type !== 'commonjs') {
    throw new Error(`Unsupported package type ${JSON.stringify(manifest.type)}. Use "module", "commonjs", or omit type.`);
  }
  const esm = manifest.type === 'module';
  const profile = {
    paths: ['acceptance/features/**/*.feature'],
    format: ['progress'],
    publish: false,
    ...(esm
      ? { import: ['acceptance/support/register.mjs', 'acceptance/steps/**/*.ts', 'acceptance/support/**/*.ts'] }
      : { requireModule: ['tsx/cjs'], require: ['acceptance/steps/**/*.ts', 'acceptance/support/**/*.ts'] }),
  };
  const configuration = `${JSON.stringify({ default: profile }, null, 2)}\n`;
  const configPath = join(target, 'acceptance/cucumber.json');
  const registrationPath = join(target, 'acceptance/support/register.mjs');
  const conflict = rootConfigurations.find(name => present(join(target, name)));
  if (conflict) throw new Error(`Existing ${conflict} in ${target}. Use the existing Cucumber harness; this bootstrap does not migrate or overwrite it.`);
  const rerun = present(configPath);
  if (rerun && (readFileSync(configPath, 'utf8') !== configuration || manifest.scripts?.acceptance !== acceptanceCommand || (esm && (!present(registrationPath) || readFileSync(registrationPath, 'utf8') !== registration)))) {
    throw new Error('Existing acceptance/cucumber.json is not an unchanged bootstrap harness. Use the existing harness; no configuration will be overwritten.');
  }
  if (esm && present(registrationPath) && readFileSync(registrationPath, 'utf8') !== registration) {
    throw new Error('Existing acceptance/support/register.mjs conflicts with the ESM loader. Use the existing harness; the registration file will not be overwritten.');
  }
  if (manifest.scripts?.acceptance !== undefined && manifest.scripts.acceptance !== acceptanceCommand) {
    throw new Error('Existing scripts.acceptance has a different command. Integrate the existing acceptance harness explicitly; this bootstrap will not replace that command.');
  }
  for (const relative of ['acceptance', 'acceptance/features', 'acceptance/steps', 'acceptance/support']) {
    const path = join(target, relative);
    if (present(path) && !lstatSync(path).isDirectory()) throw new Error(`Existing ${relative} is not a directory. Resolve that path conflict before retrying.`);
  }

  const sourceManifest = readManifest(resolve(dirname(fileURLToPath(import.meta.url)), '../../../package.json'));
  const dependencies = ['@cucumber/cucumber', 'tsx'].map(name => {
    const version = sourceManifest.devDependencies?.[name];
    if (typeof version !== 'string' || !/^\d+\.\d+\.\d+$/.test(version)) throw new Error(`The bundled root manifest must pin ${name} to an exact development version. Repair the Daily Driver installation.`);
    return [name, version];
  });
  if (!noInstall && (!rerun || dependencies.some(([name, version]) => manifest.devDependencies?.[name] !== version))) {
    run(manager, [manager === 'npm' ? 'install' : 'add', '--save-dev', '--save-exact', ...dependencies.map(([name, version]) => `${name}@${version}`)], target);
  }
  if (manifest.scripts?.acceptance !== acceptanceCommand) run(manager, ['pkg', 'set', `scripts.acceptance=${acceptanceCommand}`], target);
  for (const directory of ['features', 'steps', 'support']) mkdirSync(join(target, 'acceptance', directory), { recursive: true });
  if (esm && !present(registrationPath)) writeFileSync(registrationPath, registration, { flag: 'wx' });
  if (!rerun) writeFileSync(configPath, configuration, { flag: 'wx' });
  console.log(`${rerun ? 'Preserved' : 'Created'} ${esm ? 'ESM' : 'CommonJS'} TypeScript Cucumber harness in ${target}.`);
  if (noInstall) console.log(`Installation skipped; provide ${dependencies.map(([name, version]) => `${name}@${version}`).join(' and ')} before execution.`);
  console.log(`Write product scenarios and bindings, then run: ${manager} run acceptance`);
}

try {
  main();
} catch (error) {
  console.error(`ATDD bootstrap: ${error.message}`);
  process.exitCode = 1;
}
