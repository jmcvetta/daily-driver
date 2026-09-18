#!/usr/bin/env node
/**
 * Differential check for the Omp worktree guard (extensions/daily-driver.js).
 *
 * `check-omp-extension.mjs` asserts the guard's verdict on commands a person
 * thought of. This one asserts the property those assertions are for, against
 * the only authority on what a shell command does: bash.
 *
 * For each command shape it takes the guard's verdict on a pristine fixture,
 * then runs the same command under real bash in a fresh copy of that fixture
 * and looks at whether the primary checkout actually moved — its HEAD ref, its
 * commit, or its tracked files. The property is one-directional and is the
 * whole point of the guard:
 *
 *     the guard allowed it  =>  the primary checkout did not change
 *
 * A guard that denies something harmless fails no assertion here. That
 * asymmetry is the inversion #269 asks for: a false positive costs the model
 * one rewritten command, and a false negative costs the user their checkout.
 * Over-blocking is held in check by `check-omp-extension.mjs` instead, which
 * names the commands that must stay available.
 *
 * Every shape below is a real construct, and six of them are the fail-open
 * holes four review rounds found one at a time: a here-document that never
 * ends, `cd` in a subshell, an arithmetic `<<`, a function body, a stale
 * function-body flag, and a command substitution nested in arithmetic.
 *
 * Credential-free, network-free, deterministic. Run from the repository root:
 *
 *     node scripts/check-omp-guard-differential.mjs
 */

import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const EXTENSION = resolve(ROOT, "extensions", "daily-driver.js");

const { default: dailyDriverExtension } = await import(
	pathToFileURL(EXTENSION).href
);

/** The tool_call handler, with the rest of the extension surface stubbed. */
function guardHandler() {
	let handler = null;
	const schema = new Proxy(() => schema, {
		get: () => () => schema,
		apply: () => schema,
	});
	dailyDriverExtension({
		zod: { object: (spec) => spec, string: () => schema, number: () => schema },
		on(event, fn) {
			if (event === "tool_call") handler = fn;
		},
		registerTool() {},
		setSessionName() {},
		sendMessage() {},
		setTimeout: () => 0,
		clearTimer() {},
	});
	if (handler === null) throw new Error("extension registered no tool_call handler");
	return handler;
}

const onToolCall = guardHandler();

function git(cwd, ...args) {
	execFileSync("git", ["-C", cwd, ...args], {
		encoding: "utf8",
		stdio: ["ignore", "pipe", "pipe"],
	});
}

function gitRead(cwd, ...args) {
	const run = spawnSync("git", ["-C", cwd, ...args], { encoding: "utf8" });
	return run.status === 0 ? run.stdout.trim() : `<error:${run.status}>`;
}

/**
 * A throwaway repository: a primary checkout on `master` with a second branch
 * to switch to, one attached task worktree, and one detached worktree.
 */
function makeFixture() {
	const root = mkdtempSync(resolve(tmpdir(), "daily-driver-differential-"));
	const primary = resolve(root, "primary");
	const task = resolve(root, "task");
	const detached = resolve(root, "detached");
	mkdirSync(primary);
	git(primary, "init", "-b", "master");
	git(primary, "config", "user.name", "Differential Check");
	git(primary, "config", "user.email", "differential@example.invalid");
	writeFileSync(resolve(primary, "tracked.txt"), "primary\n");
	git(primary, "add", "tracked.txt");
	git(primary, "commit", "-m", "Initial fixture");
	writeFileSync(resolve(primary, "tracked.txt"), "second\n");
	git(primary, "commit", "-am", "Second commit");
	git(primary, "branch", "feature/y", "HEAD~1");
	git(primary, "worktree", "add", "-b", "feature/task", task);
	git(primary, "worktree", "add", "--detach", detached);
	return { root, primary, task, detached };
}

/** Everything about the primary checkout a guarded command must not change. */
function primaryState(primary) {
	// Untracked files are deliberately not counted. This guard reads shell
	// commands for branch moves; an arbitrary `cat > file` in the primary is
	// the `write` and `edit` guard's business, and holding this check to a
	// promise the recognizer never made would only teach it to lie.
	return [
		gitRead(primary, "symbolic-ref", "-q", "HEAD"),
		gitRead(primary, "rev-parse", "HEAD"),
		gitRead(primary, "status", "--porcelain", "--untracked-files=no"),
	].join("\n");
}

/** The guard's verdict: true where it blocked the call. */
function blocked(command, cwd) {
	const decision = onToolCall(
		{ type: "tool_call", toolCallId: "differential", toolName: "bash", input: { command, cwd } },
		{ cwd, ui: {} },
	);
	return decision?.block === true;
}

/**
 * Command shapes, built against one fixture's real paths. `from` is the
 * directory the shell starts in: `task` is the interesting one, because a
 * command run from a task worktree is one the guard has no other reason to
 * refuse, so anything that reaches the primary from there is a hole.
 */
function shapes({ primary, task, detached }) {
	const move = (cwd) => `git -C ${cwd} switch feature/y`;
	const cases = [];
	const add = (label, from, command) => cases.push({ label, from, command });

	// The four ways to name the primary checkout from elsewhere.
	add("bare -C switch", task, move(primary));
	add("cd then switch", task, `cd ${primary} && git switch feature/y`);
	add("git-dir and work-tree", task, `git --git-dir=${primary}/.git --work-tree=${primary} switch feature/y`);
	add("GIT_DIR environment", task, `GIT_DIR=${primary}/.git git switch feature/y`);
	add("relative git-dir after -C", task, `git --git-dir=.git -C ${primary} switch feature/y`);
	add("last assignment wins", task, `GIT_DIR=/nonexistent/x.git GIT_DIR=${primary}/.git git switch feature/y`);

	// The six fail-open holes four review rounds found, one at a time.
	add("arithmetic left shift", primary, "echo $((1 << 2))\ngit switch feature/y");
	add("substitution inside arithmetic", task, `echo $(( $(cd ${primary} && git switch feature/y) + 1 ))`);
	add("cd in a subshell", primary, `(cd ${task}) ; git switch feature/y`);
	add("function body cd", primary, `f() { cd ${task}; }\ngit switch feature/y`);
	add("function defined then called", task, `f() { cd ${primary}; }\nf\ngit switch feature/y`);
	add("stale function-body flag", task, `f() ( true )\n{ cd ${primary} ; }\ngit switch feature/y`);
	add("unterminated here-document", primary, "cat <<EOF\ngit switch feature/y\n");
	add("here-document body is data", primary, "cat > s.sh <<'EOF'\ngit switch feature/y\nEOF\n");

	// Control flow, which reads as a call to a keyword unless the keyword is
	// stripped away.
	add("if condition", task, `if ${move(primary)}; then true; fi`);
	add("while condition", task, `while ${move(primary)}; do break; done`);
	add("for loop with expanded cd", task, `for d in ${primary}; do cd $d; git switch feature/y; done`);
	add("until condition", task, `until ${move(primary)}; do break; done`);
	add("negated command", task, `! ${move(primary)}`);

	// Strings run by an interpreter.
	add("eval literal", task, `eval '${move(primary)}'`);
	add("eval then switch", task, `eval 'cd ${primary}'\ngit switch feature/y`);
	add("bash -c literal", task, `bash -c '${move(primary)}'`);
	add("sh -c literal", task, `sh -c '${move(primary)}'`);
	add("eval expanded", task, `x='${move(primary)}'; eval "$x"`);
	add("expanded executable from a task worktree", task, `g=git; $g -C ${primary} switch feature/y`);
	add("ordinary arithmetic", task, "n=1; echo $(( $n + 1 ))");
	add("bash -c expanded", task, `x='${move(primary)}'; bash -c "$x"`);

	// Expansions standing where the guard reads a literal.
	add("expanded cd target", task, `x=${primary}; cd $x; git switch feature/y`);
	add("expanded executable", primary, "g=git; $g switch feature/y");
	add("expanded subcommand", primary, "s=switch; git $s feature/y");
	add("command substitution as executable", primary, "$(echo git) switch feature/y");
	add("backtick substitution", task, `echo \`cd ${primary} && git switch feature/y\``);
	add("substitution result discarded", task, `echo $(cd ${primary}; git switch feature/y)`);

	// `cd` forms the walker has to recognize or call unknown.
	add("cd with double dash", task, `cd -- ${primary} && git switch feature/y`);
	add("cd with -P", task, `cd -P ${primary} && git switch feature/y`);
	add("cd then or-else", task, `cd ${primary} || true\ngit switch feature/y`);
	add("cd in a pipeline", primary, `cd ${task} | cat\ngit switch feature/y`);
	add("cd backgrounded", primary, `cd ${task} &\ngit switch feature/y`);
	add("pushd", task, `pushd ${primary} >/dev/null && git switch feature/y`);
	add("cd with no argument", task, `cd\ngit switch feature/y`);

	// Wrappers that exec their argument in the same directory.
	add("env wrapper", task, `env ${move(primary)}`);
	add("command wrapper", task, `command ${move(primary)}`);
	add("xargs wrapper", task, `echo feature/y | xargs git -C ${primary} switch`);
	add("timeout wrapper", task, `timeout 10 ${move(primary)}`);
	add("nohup wrapper", task, `nohup ${move(primary)}`);

	// Quoting, comments, and prose that only look like commands.
	add("quoted prose", primary, 'echo "git switch feature/y"');
	add("single-quoted prose", primary, "echo 'git switch feature/y'");
	add("commented out", primary, "# git switch feature/y\ntrue");
	add("line continuation", primary, "git \\\n  switch feature/y");
	add("unterminated quote", primary, 'git switch feature/y "');

	// Checkout forms, where a pathspec edits files without moving HEAD.
	add("checkout with pathspec", primary, "git checkout -- tracked.txt");
	add("checkout a branch", primary, "git checkout feature/y");
	add("checkout new branch", primary, "git checkout -b feature/z");

	// The detached worktree, and mutations that should run untouched.
	add("switch in a detached worktree", detached, "git switch feature/y");
	add("work in the task worktree", task, "git status --porcelain");
	add("ordinary substitution", task, "echo $(echo hello)");

	return cases;
}

const results = [];
let failures = 0;
let allowed = 0;
let denied = 0;

for (const probe of shapes(makeFixture())) {
	// One fresh fixture per case: a command that creates a branch or a
	// worktree must not colour the next case's answer.
	const fixture = makeFixture();
	// The shapes carry a fixture's real paths, so they are rebuilt against
	// this one: each case runs in a repository no earlier case has touched.
	const rebuilt = shapes(fixture).find((one) => one.label === probe.label);
	const before = primaryState(fixture.primary);
	const verdict = blocked(rebuilt.command, rebuilt.from);
	spawnSync("bash", ["-c", rebuilt.command], {
		cwd: rebuilt.from,
		encoding: "utf8",
		timeout: 20000,
		env: { ...process.env, HOME: fixture.root, GIT_CONFIG_GLOBAL: "/dev/null" },
	});
	const mutated = primaryState(fixture.primary) !== before;

	if (verdict) denied++;
	else allowed++;
	if (!verdict && mutated) {
		failures++;
		results.push(
			`FAIL ${probe.label}: allowed, and the primary checkout changed\n` +
				`       from ${rebuilt.from === fixture.task ? "task worktree" : rebuilt.from === fixture.primary ? "primary" : "detached worktree"}\n` +
				`       ${rebuilt.command.replaceAll("\n", "\n       ")}`,
		);
	} else {
		results.push(
			`ok   ${probe.label} (${verdict ? "denied" : "allowed"}${mutated ? ", mutates" : ""})`,
		);
	}
	rmSync(fixture.root, { recursive: true, force: true });
}

for (const line of results) console.log(line);
console.log("");
if (failures > 0) {
	console.error(
		`${failures} shape(s) were allowed by the guard and changed the primary checkout`,
	);
	process.exit(1);
}
console.log(
	`all ${results.length} shapes agree with bash; ${denied} denied, ${allowed} allowed, none allowed a primary mutation`,
);
