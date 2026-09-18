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
 * The property is asserted over the commands this guard claims. #269 named
 * `git checkout` and `git switch`; #289 widened the claim to every subcommand
 * that rewrites tracked files in the working tree, and the shapes below cover
 * `reset --hard`, `restore`, `merge`, `rebase`, `cherry-pick` and `revert`
 * alongside them. What the guard still does not claim gets no shape here: `git
 * reset --soft` moves HEAD and stages the difference without touching a
 * working-tree file, so it is allowed, and it would fail the property below —
 * which reads the primary's HEAD as well as its files. A check that claimed
 * the whole surface while the recognizer covered part of it would be the
 * overstatement this guard was rewritten to stop making.
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
	// A branch genuinely ahead of master, so a merge, a rebase and a
	// cherry-pick against it move the primary rather than reporting that there
	// was nothing to do.
	git(primary, "switch", "-c", "feature/ahead");
	writeFileSync(resolve(primary, "ahead.txt"), "ahead\n");
	git(primary, "add", "ahead.txt");
	git(primary, "commit", "-m", "Ahead commit");
	git(primary, "switch", "master");
	// Configured aliases: the spelling a guarded subcommand takes in a user's
	// own config. Repository config is shared with every worktree cut from
	// it, so a command run in the task worktree carries them too.
	git(primary, "config", "alias.co", "checkout");
	git(primary, "config", "alias.sw", "switch");
	git(primary, "config", "alias.undo", "reset --hard");
	git(primary, "config", "alias.lg", "log --oneline");
	git(primary, "config", "alias.chain", "co");
	git(primary, "config", "alias.visual", "!git switch feature/y");
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
function shapes({ root, primary, task, detached }) {
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

	// Substitution and wrappers that hide the git word from a positional scan.
	add("substitution inside double quotes", task, `echo "$(git -C ${primary} switch feature/y)"`);
	add("assignment from a substitution", task, `x="$(cd ${primary} && git switch feature/y)"`);
	add("non-literal word before git", task, `env -u NOPE* git -C ${primary} switch feature/y`);
	add("glob before git", task, `nice -n 5 */dev/null git -C ${primary} switch feature/y`);

	// A `cd` whose own execution was conditional on something that failed.
	add("cd after a failed and", primary, `false && cd ${task}\ngit switch feature/y`);
	add("cd after a successful or", primary, `true || cd ${task}\ngit switch feature/y`);
	add("cd downstream of a pipe", primary, `echo x | cd ${task}\ngit switch feature/y`);

	// A substitution standing in a Git option's value. It is part of the word
	// carrying it, so ending the command there hid `switch` from the scan
	// entirely — the same fail-open the quoted-substitution fix closed, reopened
	// by that fix.
	add("substitution in a -C value", task, `git -C "$(echo ${primary})" switch feature/y`);
	add("substitution in a -C value, unquoted", task, `git -C $(echo ${primary}) switch feature/y`);
	add("substitution in a -C value, backticks", task, `git -C \`echo ${primary}\` switch feature/y`);
	add("substitution appended to a -C value", task, `git -C "${primary}$(echo /.)" switch feature/y`);
	add("substitution in git-dir and work-tree", task, `git --git-dir="$(echo ${primary})/.git" --work-tree="$(echo ${primary})" switch feature/y`);
	add("substitution in a GIT_DIR value", task, `GIT_DIR="$(echo ${primary})/.git" git switch feature/y`);
	add("substitution standing in for an option", task, `git "$(echo -C)" ${primary} switch feature/y`);
	add("substitution in a -C value, checkout", task, `git -C "$(echo ${primary})" checkout feature/y`);

	// An earlier `git` that is an argument rather than the executable.
	add("git as an argument before the real one", task, `touch git; find . -name git -exec git -C ${primary} switch feature/y \\;`);

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

	// The working-tree rewrites beyond checkout and switch, which #289 added
	// to the claim. Each one reaches the primary from the task worktree, where
	// the guard has no other reason to refuse it.
	add("reset --hard", task, `git -C ${primary} reset --hard HEAD~1`);
	add("restore from a source", task, `git -C ${primary} restore --source=HEAD~1 tracked.txt`);
	add("merge a branch ahead", task, `git -C ${primary} merge feature/ahead`);
	add("rebase onto a branch ahead", task, `git -C ${primary} rebase feature/ahead`);
	add("cherry-pick", task, `git -C ${primary} cherry-pick feature/ahead`);
	add("revert the head commit", task, `git -C ${primary} revert --no-edit HEAD`);
	add("cd then reset --hard", task, `cd ${primary} && git reset --hard HEAD~1`);
	add("git rm", task, `git -C ${primary} rm -r tracked.txt`);
	add("git mv", task, `git -C ${primary} mv tracked.txt other.txt`);
	add("bisect start", task, `git -C ${primary} bisect start HEAD HEAD~1`);
	add("sparse-checkout set", task, `git -C ${primary} sparse-checkout set nothing`);

	// An alias renames a guarded subcommand into one the recognizer has never
	// met, and a `cd` that fails leaves the shell in the primary. Both were
	// allowed until the review of #297 measured them here.
	add("inline alias definition", task, `git -C ${primary} -c alias.q=switch q feature/y`);
	add("alias through --config-env", task, `SWV=switch git -C ${primary} --config-env=alias.q=SWV q feature/y`);
	add("config value that expands", task, 'git -c core.pager="$PAGER" log --oneline -1');
	add("substituted alias name", task, `git -C ${primary} -c "$(echo alias.q)=switch" q feature/y`);
	add("backticked alias name", task, `git -C ${primary} -c \`echo alias.q\`=switch q feature/y`);
	add("substituted --config-env alias name", task, `SWV=switch git -C ${primary} --config-env="$(echo alias.q)=SWV" q feature/y`);
	// A configured alias, which is the same rename without a command line to
	// read it off: the guard has to ask Git what the word means.
	add("configured alias for switch", task, `git -C ${primary} sw feature/y`);
	add("configured alias for checkout", task, `git -C ${primary} co feature/y`);
	add("configured alias carrying --hard", task, `git -C ${primary} undo HEAD~1`);
	add("alias naming another alias", task, `git -C ${primary} chain feature/y`);
	add("shell alias in the primary", primary, "git visual");
	add("alias for a read-only command", primary, "git lg -1");
	add("cd into a missing directory", primary, `cd ${root}/never-created\ngit switch feature/y`);
	add("restore in the primary", primary, "git restore --source=HEAD~1 tracked.txt");

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
