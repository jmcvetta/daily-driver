#!/usr/bin/env node
/**
 * Behavioural check for the Omp runtime adapter (extensions/daily-driver.js).
 *
 * Imports the extension factory with a fake `ExtensionAPI` and asserts the
 * runtime-adapter contract #145 delivers:
 *
 *   - Omp's `ask` tool is blocked with actionable text;
 *   - direct writes, edits, and every Git command that rewrites the working
 *     tree — checkout, switch, reset, restore, stash, merge, rebase, pull,
 *     apply, am, cherry-pick, revert, clean — in a primary worktree are
 *     blocked, as are file mutations in a detached worktree;
 *   - attached feature-worktree mutations, worktree creation, detached branch
 *     attachment, non-Git paths, and synthetic devices pass;
 *   - a mutation the guard cannot place in a repository is refused, the way
 *     one it cannot ask Git about is;
 *   - a subcommand that is a configured alias is read as the command it
 *     expands to, and one whose expansion the guard cannot read is refused
 *     where it would reach the primary;
 *   - daily_driver_set_session_title calls pi.setSessionName;
 *   - daily_driver_get_session reads the session manager's id and the model;
 *   - daily_driver_schedule emits exactly one reminder after its delay and
 *     returns a triggerId;
 *   - daily_driver_cancel_schedule cancels a live trigger (no emission) and
 *     returns clean false for an unknown or already-fired id.
 *
 * Credential-free, dependency-free, deterministic: it uses fake managed
 * timers, so it never waits on real time. Run from the repository root:
 *
 *     node scripts/check-omp-extension.mjs
 */

import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import {
	mkdirSync,
	mkdtempSync,
	readFileSync,
	rmSync,
	symlinkSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const EXTENSION = resolve(ROOT, "extensions", "daily-driver.js");

/** A controllable fake managed timer, mirroring ctx.setTimeout/clearTimer. */
function fakeTimers() {
	const pending = new Map(); // id -> { fn, args, delay, seq }
	let nextId = 1;
	let now = 0;

	function setTimeout(fn, delay, ...args) {
		const id = nextId++;
		pending.set(id, { fn, args, delay: now + delay, seq: id });
		return id;
	}

	function clearTimer(id) {
		pending.delete(id);
	}

	/** Managed timers are cleared by the runtime on session shutdown. */
	function clearAll() {
		pending.clear();
	}

	/** Advance the clock by ms and fire every due timer exactly once. */
	function advance(ms) {
		now += ms;
		const due = [...pending.values()]
			.filter((t) => t.delay <= now)
			.sort((a, b) => a.seq - b.seq)
			.map((t) => {
				pending.delete(t.seq);
				return t;
			});
		for (const t of due) t.fn(...t.args);
		return due.map((t) => t.seq);
	}

	return { setTimeout, clearTimer, clearAll, pending, nextId: () => nextId, advance };
}

/**
 * Build a fake ExtensionAPI. `pi.on` records handlers keyed by event name;
 * `registerTool` records tool definitions; `setSessionName` and
 * `sendMessage` record calls. Returns { pi, rec, tools, fire }.
 */
function fakeApi(overrides = {}) {
	const handlers = new Map();
	const calls = { sessionNames: [], sent: [] };
	const tools = new Map();
	const timers = fakeTimers();

	// A chainable fake zod that mirrors the Omp (omptype-backed) zod surface the
// adapter actually targets: z.string, z.number().int().min().max(), and
// z.object returning the spec keyed by name. It deliberately excludes
// `z.integer` so a schema written against real Zod's alias fails here too.
	function schemaNode(meta = {}) {
		return {
			describe(desc) {
				return schemaNode({ ...meta, desc });
			},
			min(n) {
				return schemaNode({ ...meta, min: n });
			},
			max(n) {
				return schemaNode({ ...meta, max: n });
			},
			int() {
				return schemaNode({ ...meta, int: true });
			},
			_meta: () => meta,
		};
	}
	const zod = {
		object(spec) {
			return spec;
		},
		string: () => schemaNode({ type: "string" }),
		number: () => schemaNode({ type: "number" }),
		// No `integer:` — intentional, so an `.integer()` misuse is caught.
	};

	const pi = {
		zod,
		on(event, handler) {
			handlers.set(event, handler);
		},
		registerTool(def) {
			tools.set(def.name, def);
		},
		async setSessionName(name) {
			calls.sessionNames.push(name);
		},
		sendMessage(msg, opts) {
			calls.sent.push({ msg, opts });
		},
		setTimeout: timers.setTimeout,
		clearTimer: timers.clearTimer,
		...overrides,
	};

	const fire = (event, payload, ctx) => {
		const h = handlers.get(event);
		if (!h) throw new Error(`no handler for ${event}`);
		return h(payload, ctx);
	};

	return { pi, rec: calls, tools, timers, fire };
}

const results = [];
let failures = 0;
const checks = [];

async function check(name, fn) {
	checks.push(
		(async () => {
			try {
				await fn();
				results.push(`ok   ${name}`);
			} catch (err) {
				failures++;
				results.push(`FAIL ${name}: ${err.message}`);
			}
		})(),
	);
}

// Load the factory once. It is a default export function; importing the
// module gives us the factory plus its exported constants.
const module_ = await import(EXTENSION);
assert.equal(typeof module_.default, "function", "extension must export a default factory");
const {
	ASK_BLOCK_REASON,
	GIT_UNAVAILABLE_BLOCK_REASON,
	REMINDER_CUSTOM_TYPE,
	UNANCHORED_PATH_BLOCK_REASON,
	UNREADABLE_COMMAND_BLOCK_REASON,
	WORKTREE_BLOCK_REASON,
	default: dailyDriverExtension,
} = module_;

function makeSession() {
	const { pi, rec, tools, timers, fire } = fakeApi();
	dailyDriverExtension(pi);
	return { rec, tools, timers, fire, pi };
}

function runGit(cwd, ...args) {
	return execFileSync("git", ["-C", cwd, ...args], {
		encoding: "utf8",
		stdio: ["ignore", "pipe", "pipe"],
	});
}

/** A primary checkout, attached and detached worktrees, and a non-Git path. */
function makeWorktreeFixture() {
	const root = mkdtempSync(resolve(tmpdir(), "daily-driver-extension-"));
	const primary = resolve(root, "primary");
	const task = resolve(root, "task");
	const detached = resolve(root, "detached");
	const outside = resolve(root, "outside");
	mkdirSync(primary);
	mkdirSync(outside);
	runGit(primary, "init", "-b", "master");
	runGit(primary, "config", "user.name", "Extension Check");
	runGit(primary, "config", "user.email", "extension-check@example.invalid");
	writeFileSync(resolve(primary, "tracked.txt"), "primary\n");
	runGit(primary, "add", "tracked.txt");
	runGit(primary, "commit", "-m", "Initial fixture");
	// Configured aliases, which rename a guarded subcommand into a word no
	// recognizer set holds. Repository config is shared with every worktree
	// cut from it, so the task worktree carries the same aliases.
	runGit(primary, "config", "alias.co", "checkout");
	runGit(primary, "config", "alias.sw", "switch");
	runGit(primary, "config", "alias.undo", "reset --hard");
	runGit(primary, "config", "alias.lg", "log --oneline");
	runGit(primary, "config", "alias.elsewhere", "-C . switch");
	runGit(primary, "config", "alias.chain", "co");
	runGit(primary, "config", "alias.visual", "!git switch master");
	runGit(primary, "config", "alias.loop", "hoop");
	runGit(primary, "config", "alias.hoop", "loop");
	runGit(primary, "worktree", "add", "-b", "feature/worktree-guard", task);
	runGit(primary, "worktree", "add", "--detach", detached);
	const primaryFileLink = resolve(task, "primary-file-link.txt");
	symlinkSync(resolve(primary, "tracked.txt"), primaryFileLink);
	// A symlinked route to the task worktree: a symlinked worktrees root, a
	// symlinked home, `/tmp` on macOS. A `cd` through one really does arrive.
	const taskLink = resolve(root, "task-link");
	symlinkSync(task, taskLink);
	return { root, primary, task, taskLink, detached, outside, primaryFileLink };
}

const worktrees = makeWorktreeFixture();

/**
 * A checkout whose worktree listing carries a stale record — a worktree
 * removed from disk and never pruned — ordered before a live detached
 * worktree, so the stale record is read first during classification.
 */
function makeStaleWorktreeFixture() {
	const root = mkdtempSync(resolve(tmpdir(), "daily-driver-stale-"));
	const primary = resolve(root, "primary");
	const gone = resolve(root, "agone");
	const detached = resolve(root, "zdetached");
	mkdirSync(primary);
	runGit(primary, "init", "-b", "master");
	runGit(primary, "config", "user.name", "Extension Check");
	runGit(primary, "config", "user.email", "extension-check@example.invalid");
	writeFileSync(resolve(primary, "tracked.txt"), "primary\n");
	runGit(primary, "add", "tracked.txt");
	runGit(primary, "commit", "-m", "Initial fixture");
	runGit(primary, "worktree", "add", "-b", "feature/gone", gone);
	runGit(primary, "worktree", "add", "--detach", detached);
	rmSync(gone, { recursive: true, force: true });
	return { root, primary, detached };
}

const staleWorktrees = makeStaleWorktreeFixture();

/**
 * A detached primary checkout — the shape `setup.sh detached` builds, and the
 * ordinary shape of a CI checkout — plus one attached task worktree, which is
 * where a session that must not reach back into that primary sits.
 */
function makeDetachedPrimaryFixture() {
	const root = mkdtempSync(resolve(tmpdir(), "daily-driver-detached-"));
	const primary = resolve(root, "primary");
	const task = resolve(root, "task");
	mkdirSync(primary);
	runGit(primary, "init", "-b", "master");
	runGit(primary, "config", "user.name", "Extension Check");
	runGit(primary, "config", "user.email", "extension-check@example.invalid");
	writeFileSync(resolve(primary, "tracked.txt"), "primary\n");
	runGit(primary, "add", "tracked.txt");
	runGit(primary, "commit", "-m", "Initial fixture");
	runGit(primary, "switch", "--detach");
	runGit(primary, "worktree", "add", "-b", "feature/detached-task", task);
	return { root, primary, task };
}

const detachedPrimary = makeDetachedPrimaryFixture();

// --- ask is blocked; another tool passes ------------------------------------
check("ask tool is blocked with actionable reason", () => {
	const s = makeSession();
	const toolCtx = { cwd: "/tmp", ui: {} };
	const decision = s.fire("tool_call", { type: "tool_call", toolCallId: "t1", toolName: "ask", input: { questions: [] } }, toolCtx);
	assert.deepEqual(decision, { block: true, reason: ASK_BLOCK_REASON });
	assert.match(ASK_BLOCK_REASON, /do not retry/i, "reason tells the model not to retry");
	assert.match(ASK_BLOCK_REASON, /chat reply/i, "reason tells the model to ask in chat");
	assert.match(ASK_BLOCK_REASON, /recommend/i, "reason tells the model to name a recommendation");
});

check("a tool other than ask passes through", async () => {
	const s = makeSession();
	const toolCtx = { cwd: "/tmp", ui: {} };
	const decision = s.fire("tool_call", { type: "tool_call", toolCallId: "t2", toolName: "bash", input: { command: "true" } }, toolCtx);
	assert.equal(decision, undefined, "non-ask tool must not be blocked");
});

let nextGuardCall = 1;
function guardDecision(toolName, input, cwd) {
	const s = makeSession();
	return s.fire(
		"tool_call",
		{
			type: "tool_call",
			toolCallId: `guard-${nextGuardCall++}`,
			toolName,
			input,
		},
		{ cwd, ui: {} },
	);
}

function checkGuard(name, blocked, toolName, input, cwd, reason) {
	check(name, () => {
		const decision = guardDecision(toolName, input, cwd);
		if (blocked) {
			assert.deepEqual(decision, {
				block: true,
				reason: reason ?? WORKTREE_BLOCK_REASON,
			});
		} else {
			assert.equal(decision, undefined);
		}
	});
}

check("worktree denial directs the model through task-worktree", () => {
	assert.match(WORKTREE_BLOCK_REASON, /do not retry/i);
	assert.match(WORKTREE_BLOCK_REASON, /`task-worktree`/);
	assert.match(WORKTREE_BLOCK_REASON, /attaching this worktree in place/i);
});

// --- repository boundary ---------------------------------------------------
checkGuard(
	"a write in the primary worktree is blocked",
	true,
	"write",
	{ path: "new.txt", content: "unsafe\n" },
	worktrees.primary,
);

checkGuard(
	"an edit targeting the primary worktree is blocked",
	true,
	"edit",
	{
		input:
			`*** Begin Patch\n[${resolve(worktrees.primary, "tracked.txt")}#ABCD]\n` +
			"PUT 1.=1:\n+unsafe\n*** End Patch\n",
	},
	worktrees.task,
);

checkGuard(
	"a write in an attached feature worktree passes",
	false,
	"write",
	{ path: resolve(worktrees.task, "new.txt"), content: "safe\n" },
	worktrees.primary,
);

checkGuard(
	"an edit in an attached feature worktree passes",
	false,
	"edit",
	{
		input:
			`<SM:EDIT path="${resolve(worktrees.task, "tracked.txt")}">\n` +
			"<SM:FIND>\nprimary\n</SM:FIND>\n<SM:PUT>\nsafe\n</SM:PUT>\n</SM:EDIT>",
	},
	worktrees.primary,
);

checkGuard(
	"an attached-worktree symlink cannot redirect a write into the primary",
	true,
	"write",
	{ path: worktrees.primaryFileLink, content: "unsafe\n" },
	worktrees.task,
);

checkGuard(
	"a write in a detached worktree is blocked",
	true,
	"write",
	{ path: "new.txt", content: "unsafe\n" },
	worktrees.detached,
);

checkGuard(
	"an edit in a detached worktree is blocked",
	true,
	"edit",
	{
		input:
			`*** Begin Patch\n*** Update File: ${resolve(worktrees.detached, "tracked.txt")}\n` +
			"@@\n-primary\n+unsafe\n*** End Patch\n",
	},
	worktrees.task,
);

checkGuard(
	"an edit cannot move a feature-worktree file into the primary worktree",
	true,
	"edit",
	{
		input:
			`*** Begin Patch\n[${resolve(worktrees.task, "tracked.txt")}#ABCD]\n` +
			`MV ${resolve(worktrees.primary, "moved.txt")}\n*** End Patch\n`,
	},
	worktrees.task,
);

checkGuard(
	"a write to a non-Git path passes",
	false,
	"write",
	{ path: resolve(worktrees.outside, "new.txt"), content: "ordinary\n" },
	worktrees.primary,
);

checkGuard(
	"an edit to a non-Git path passes",
	false,
	"edit",
	{ path: resolve(worktrees.outside, "ordinary.txt"), old_string: "a", new_string: "b" },
	worktrees.primary,
);

checkGuard(
	"a synthetic device write passes",
	false,
	"write",
	{ path: "xd://daily_driver_set_session_title", content: "{}" },
	worktrees.primary,
);

checkGuard(
	"git checkout in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git checkout -b feature/wrong-place" },
	worktrees.primary,
);

checkGuard(
	"git switch in the primary worktree is blocked",
	true,
	"bash",
	{ command: "  git switch feature/wrong-place" },
	worktrees.primary,
);

checkGuard(
	"git -C cannot switch the primary branch from a feature worktree",
	true,
	"bash",
	{ command: `git -C "${worktrees.primary}" switch feature/wrong-place` },
	worktrees.task,
);

checkGuard(
	"--work-tree cannot disguise a primary branch switch",
	true,
	"bash",
	{
		command:
			`git --work-tree="${worktrees.task}" ` +
			"switch feature/wrong-place",
	},
	worktrees.primary,
);

checkGuard(
	"--git-dir cannot switch the primary HEAD from a feature worktree",
	true,
	"bash",
	{
		command:
			`git --git-dir="${resolve(worktrees.primary, ".git")}" ` +
			"switch feature/wrong-place",
	},
	worktrees.task,
);

checkGuard(
	"GIT_DIR cannot switch the primary HEAD from a feature worktree",
	true,
	"bash",
	{
		command:
			`GIT_DIR="${resolve(worktrees.primary, ".git")}" ` +
			"git switch feature/wrong-place",
	},
	worktrees.task,
);

checkGuard(
	"--work-tree cannot direct a feature HEAD switch into primary files",
	true,
	"bash",
	{
		command:
			`git --git-dir="${resolve(worktrees.task, ".git")}" ` +
			`--work-tree="${worktrees.primary}" switch feature/wrong-place`,
	},
	worktrees.task,
);

checkGuard(
	"a primary checkout path restore is blocked, as `git restore` is",
	true,
	"bash",
	{ command: "git checkout -- tracked.txt" },
	worktrees.primary,
);

checkGuard(
	"a bare git checkout in the primary worktree passes",
	false,
	"bash",
	{ command: "git checkout" },
	worktrees.primary,
);

checkGuard(
	"quoted Git prose is not mistaken for a branch switch",
	false,
	"bash",
	{ command: 'printf "%s\\n" "git switch feature/not-executed"' },
	worktrees.primary,
);

checkGuard(
	"worktree creation from the primary checkout passes",
	false,
	"bash",
	{ command: "git worktree add -b feature/right-place ../right-place master" },
	worktrees.primary,
);

checkGuard(
	"attaching a detached task worktree to its branch passes",
	false,
	"bash",
	{ command: "git switch -c feature/detached-fix master", cwd: worktrees.detached },
	worktrees.primary,
);

checkGuard(
	"changing into a detached task worktree before attachment passes",
	false,
	"bash",
	{ command: `cd "${worktrees.detached}" && git switch -c feature/detached-fix master` },
	worktrees.primary,
);

checkGuard(
	"a branch switch inside an attached feature worktree passes",
	false,
	"bash",
	{ command: "git switch feature/another-task" },
	worktrees.task,
);

checkGuard(
	"an explicit feature-worktree Git directory passes",
	false,
	"bash",
	{
		command:
			`git --git-dir="${resolve(worktrees.task, ".git")}" ` +
			"switch feature/another-task",
	},
	worktrees.primary,
);

// --- the working-tree rewrites beyond checkout and switch (#289) -----------
// Each pair is one subcommand: the destructive form denied in the primary
// checkout, and — where the manual gives it one — the harmless form that must
// stay available, so the guard does not become an obstacle to ordinary work.

checkGuard(
	"git reset --hard in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git reset --hard HEAD~1" },
	worktrees.primary,
);

checkGuard(
	"git reset --merge in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git reset --merge" },
	worktrees.primary,
);

checkGuard(
	"git reset --keep in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git reset --keep HEAD~1" },
	worktrees.primary,
);

checkGuard(
	"a reset mode the guard has never met is blocked, not assumed harmless",
	true,
	"bash",
	{ command: "git reset --some-future-mode HEAD~1" },
	worktrees.primary,
);

checkGuard(
	"a reset mode that expands is blocked rather than read",
	true,
	"bash",
	{ command: "m=--hard; git reset $m HEAD~1" },
	worktrees.primary,
);

checkGuard(
	"git reset --soft in the primary worktree passes",
	false,
	"bash",
	{ command: "git reset --soft HEAD~1" },
	worktrees.primary,
);

checkGuard(
	"an index-only git reset in the primary worktree passes",
	false,
	"bash",
	{ command: "git reset -q -- tracked.txt" },
	worktrees.primary,
);

checkGuard(
	"git reset --hard inside an attached feature worktree passes",
	false,
	"bash",
	{ command: "git reset --hard HEAD~1" },
	worktrees.task,
);

checkGuard(
	"git rm in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git rm -r tracked.txt" },
	worktrees.primary,
);

checkGuard(
	"git rm --cached in the primary worktree passes",
	false,
	"bash",
	{ command: "git rm --cached tracked.txt" },
	worktrees.primary,
);

checkGuard(
	"git mv in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git mv tracked.txt other.txt" },
	worktrees.primary,
);

checkGuard(
	"git mv --dry-run in the primary worktree passes",
	false,
	"bash",
	{ command: "git mv -n tracked.txt other.txt" },
	worktrees.primary,
);

checkGuard(
	"git bisect start in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git bisect start HEAD HEAD" },
	worktrees.primary,
);

checkGuard(
	"git bisect log in the primary worktree passes",
	false,
	"bash",
	{ command: "git bisect log" },
	worktrees.primary,
);

checkGuard(
	"git sparse-checkout set in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git sparse-checkout set nothing" },
	worktrees.primary,
);

checkGuard(
	"git sparse-checkout list in the primary worktree passes",
	false,
	"bash",
	{ command: "git sparse-checkout list" },
	worktrees.primary,
);

checkGuard(
	"git submodule update --force in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git submodule update --force" },
	worktrees.primary,
);

checkGuard(
	"git submodule status in the primary worktree passes",
	false,
	"bash",
	{ command: "git submodule status" },
	worktrees.primary,
);

// An alias renames a guarded subcommand into one the recognizer has never
// met, so a command that defines one carries a subcommand it cannot read.
checkGuard(
	"an inline alias definition is refused rather than read past",
	true,
	"bash",
	{ command: `git -C "${worktrees.primary}" -c alias.q=switch q feature/x` },
	worktrees.task,
);

checkGuard(
	"an inline alias definition with an attached value is refused too",
	true,
	"bash",
	{ command: "git -calias.q=switch q feature/x" },
	worktrees.primary,
);

checkGuard(
	"an ordinary -c setting is still read past",
	false,
	"bash",
	{ command: "git -c core.pager=cat log --oneline -1" },
	worktrees.primary,
);

// A configured alias renames a guarded subcommand just as an inline one does,
// and the word alone says nothing about it. The guard asks Git what the word
// means rather than reading past it.
checkGuard(
	"a configured alias for checkout is blocked in the primary worktree",
	true,
	"bash",
	{ command: "git co feature/x" },
	worktrees.primary,
);

checkGuard(
	"a configured alias for switch is blocked in the primary worktree",
	true,
	"bash",
	{ command: "git sw feature/x" },
	worktrees.primary,
);

checkGuard(
	"a configured alias carrying the destructive form is blocked",
	true,
	"bash",
	{ command: "git undo HEAD~1" },
	worktrees.primary,
);

checkGuard(
	"an alias naming another alias is followed to the guarded command",
	true,
	"bash",
	{ command: "git chain feature/x" },
	worktrees.primary,
);

checkGuard(
	"an alias whose expansion selects the primary is blocked from elsewhere",
	true,
	"bash",
	{ command: `git -C "${worktrees.primary}" elsewhere feature/x` },
	worktrees.task,
);

checkGuard(
	"a shell alias the guard cannot read is blocked in the primary worktree",
	true,
	"bash",
	{ command: "git visual" },
	worktrees.primary,
);

checkGuard(
	"a loop of aliases is refused rather than followed",
	true,
	"bash",
	{ command: "git loop feature/x" },
	worktrees.primary,
);

checkGuard(
	"an alias for a read-only command still passes in the primary worktree",
	false,
	"bash",
	{ command: "git lg -1" },
	worktrees.primary,
);

checkGuard(
	"a shell alias passes inside an attached feature worktree",
	false,
	"bash",
	{ command: "git visual" },
	worktrees.task,
);

checkGuard(
	"a subcommand that is no alias is still read as itself",
	false,
	"bash",
	{ command: "git status --porcelain" },
	worktrees.primary,
);

checkGuard(
	"an alias for checkout passes inside an attached feature worktree",
	false,
	"bash",
	{ command: "git co feature/x" },
	worktrees.task,
);

// A `--git-dir` selects the repository whose config the alias comes from, so
// the lookup follows it: reading the alias in the shell's own directory finds
// nothing and lets the aliased spelling through where the plain one is
// blocked.
checkGuard(
	"an alias is read from the repository --git-dir selects",
	true,
	"bash",
	{
		command:
			`git --git-dir="${resolve(worktrees.primary, ".git")}" ` +
			`--work-tree="${worktrees.primary}" co feature/x`,
	},
	worktrees.outside,
);

// A `--git-dir` whose value expands hides that repository's own config, so
// the lookup falls back to the directory it can reach. Refusing instead would
// deny every read-only command carrying such a selector, wherever it runs.
checkGuard(
	"a read-only command with an unreadable --git-dir still passes",
	false,
	"bash",
	{ command: 'd=.git; git --git-dir="$d" lg -1' },
	worktrees.task,
);

checkGuard(
	"a read-only command with an unreadable GIT_DIR still passes",
	false,
	"bash",
	{ command: 'd=.git; GIT_DIR="$d" git log --oneline -1' },
	worktrees.task,
);

checkGuard(
	"an alias reached through an unreadable --git-dir is still refused",
	true,
	"bash",
	{ command: 'd=.git; git --git-dir="$d" co feature/x' },
	worktrees.primary,
	UNREADABLE_COMMAND_BLOCK_REASON,
);

// Config carried in the environment defines an alias exactly as `-c` does.
checkGuard(
	"an alias defined through GIT_CONFIG_KEY is refused rather than read past",
	true,
	"bash",
	{
		command:
			"GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.q GIT_CONFIG_VALUE_0=switch " +
			"git q feature/x",
	},
	worktrees.primary,
);

checkGuard(
	"a config file named in the environment is refused too",
	true,
	"bash",
	{ command: "GIT_CONFIG_GLOBAL=/tmp/aliases git q feature/x" },
	worktrees.primary,
);

checkGuard(
	"an environment setting that renames nothing is still read past",
	false,
	"bash",
	{
		command:
			"GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.pager GIT_CONFIG_VALUE_0=cat " +
			"git log --oneline -1",
	},
	worktrees.primary,
);

// A `-C` value that expands leaves the invocation with no directory of its
// own, so the alias is looked up in the directory the tool was called in —
// the same repository, and the same config.
checkGuard(
	"an alias behind an unreadable -C is resolved through the tool's directory",
	true,
	"bash",
	{ command: `d="${worktrees.primary}"; git -C "$d" co feature/x` },
	worktrees.task,
	UNANCHORED_PATH_BLOCK_REASON,
);

// A `cd` whose target does not exist fails, and the shell stays in the
// primary: reading it as moved placed every later command somewhere the
// shell never went.
checkGuard(
	"a rewrite after a cd into a directory that does not exist is refused",
	true,
	"bash",
	{
		command: `cd "${resolve(worktrees.root, "never-created")}"\ngit switch feature/x`,
	},
	worktrees.primary,
	UNANCHORED_PATH_BLOCK_REASON,
);

checkGuard(
	"a pushd into a directory that does not exist is refused the same way",
	true,
	"bash",
	{
		command: `pushd "${resolve(worktrees.root, "never-created")}"\ngit switch feature/x`,
	},
	worktrees.primary,
	UNANCHORED_PATH_BLOCK_REASON,
);

checkGuard(
	"an attached --config-env alias definition is refused too",
	true,
	"bash",
	{
		command:
			`SWV=switch git -C "${worktrees.primary}" ` +
			"--config-env=alias.q=SWV q feature/x",
	},
	worktrees.task,
);

checkGuard(
	"a separate --config-env alias definition is refused too",
	true,
	"bash",
	{ command: "SWV=switch git --config-env alias.q=SWV q feature/x" },
	worktrees.primary,
);

checkGuard(
	"an include that can carry an alias is refused",
	true,
	"bash",
	{ command: "git -c include.path=/tmp/aliases q feature/x" },
	worktrees.primary,
);

// A setting the guard cannot read is not refused everywhere: it makes the
// invocation a rewrite, and the ordinary placement decides. So it costs the
// primary checkout, where the guard is meant to be an obstacle, and costs
// neither the task worktree nor a directory outside Git.
checkGuard(
	"a -c setting that expands is refused in the primary checkout",
	true,
	"bash",
	{ command: 'git -c core.pager="$PAGER" log --oneline -1' },
	worktrees.primary,
);

checkGuard(
	"a -c setting that expands passes in a feature worktree",
	false,
	"bash",
	{ command: 'git -c core.pager="$PAGER" log --oneline -1' },
	worktrees.task,
);

checkGuard(
	"a -c setting that expands passes outside Git",
	false,
	"bash",
	{ command: 'git -c core.pager="$PAGER" --version' },
	worktrees.outside,
);

// A substitution standing for the setting's name reaches the tokenizer with
// the substitution already removed, so the text is not the name Git will
// see. Reading it more closely is what let this through the first time.
checkGuard(
	"a substituted setting name cannot smuggle an alias past the guard",
	true,
	"bash",
	{
		command: `git -C "${worktrees.primary}" -c "$(echo alias.q)=switch" q feature/x`,
	},
	worktrees.task,
);

checkGuard(
	"a backticked setting name cannot either",
	true,
	"bash",
	{
		command:
			`git -C "${worktrees.primary}" -c \`echo alias.q\`=switch q feature/x`,
	},
	worktrees.task,
);

checkGuard(
	"a substituted --config-env name cannot either",
	true,
	"bash",
	{
		command:
			`SWV=switch git -C "${worktrees.primary}" ` +
			'--config-env="$(echo alias.q)=SWV" q feature/x',
	},
	worktrees.task,
);

checkGuard(
	"a -c setting that expands whole is refused",
	true,
	"bash",
	{ command: 'git -c "$setting" q feature/x' },
	worktrees.primary,
);

// A `cd` through a symlink arrives where the symlink points, so the shell
// really is in the task worktree and the work that follows is sanctioned.
checkGuard(
	"a rewrite after a cd through a symlinked task worktree passes",
	false,
	"bash",
	{ command: `cd "${worktrees.taskLink}" && git rm -r tracked.txt` },
	worktrees.primary,
);

checkGuard(
	"a cd into a path that exists but is a file is refused",
	true,
	"bash",
	{
		command: `cd "${resolve(worktrees.primary, "tracked.txt")}"\ngit switch feature/x`,
	},
	worktrees.primary,
	UNANCHORED_PATH_BLOCK_REASON,
);

// The whole widened set stays available where the work belongs.
checkGuard(
	"the widened set passes inside an attached feature worktree",
	false,
	"bash",
	{
		command:
			"git restore tracked.txt && git stash pop && " +
			"git merge feature/another-task && git rebase master && " +
			"git cherry-pick HEAD~1 && git revert HEAD && " +
			"git apply ../fix.patch && git clean -fd && git pull",
	},
	worktrees.task,
);

checkGuard(
	"git restore in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git restore tracked.txt" },
	worktrees.primary,
);

checkGuard(
	"git restore --staged --worktree is blocked, as it writes both",
	true,
	"bash",
	{ command: "git restore --staged --worktree tracked.txt" },
	worktrees.primary,
);

checkGuard(
	"a bundled -SW is read as --staged --worktree and blocked",
	true,
	"bash",
	{ command: "git restore -SW tracked.txt" },
	worktrees.primary,
);

checkGuard(
	"git restore --staged in the primary worktree passes",
	false,
	"bash",
	{ command: "git restore --staged tracked.txt" },
	worktrees.primary,
);

checkGuard(
	"git stash in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git stash" },
	worktrees.primary,
);

checkGuard(
	"git stash pop in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git stash pop" },
	worktrees.primary,
);

checkGuard(
	"git stash apply in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git stash apply stash@{0}" },
	worktrees.primary,
);

checkGuard(
	"git stash push in the primary worktree is blocked",
	true,
	"bash",
	{ command: 'git stash push -m "wip" tracked.txt' },
	worktrees.primary,
);

checkGuard(
	"a stash subcommand the guard has never met is blocked",
	true,
	"bash",
	{ command: "git stash some-future-verb" },
	worktrees.primary,
);

checkGuard(
	"git stash list in the primary worktree passes",
	false,
	"bash",
	{ command: "git stash list" },
	worktrees.primary,
);

checkGuard(
	"git stash show in the primary worktree passes",
	false,
	"bash",
	{ command: "git stash show -p stash@{0}" },
	worktrees.primary,
);

checkGuard(
	"git stash drop in the primary worktree passes",
	false,
	"bash",
	{ command: "git stash drop stash@{0}" },
	worktrees.primary,
);

checkGuard(
	"git merge in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git merge feature/another-task" },
	worktrees.primary,
);

checkGuard(
	"git merge --abort in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git merge --abort" },
	worktrees.primary,
);

checkGuard(
	"git merge-base in the primary worktree passes",
	false,
	"bash",
	{ command: "git merge-base master HEAD" },
	worktrees.primary,
);

checkGuard(
	"git rebase in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git rebase master" },
	worktrees.primary,
);

checkGuard(
	"git rebase --continue in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git rebase --continue" },
	worktrees.primary,
);

checkGuard(
	"git pull in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git pull origin master" },
	worktrees.primary,
);

checkGuard(
	"git fetch in the primary worktree passes",
	false,
	"bash",
	{ command: "git fetch origin master" },
	worktrees.primary,
);

checkGuard(
	"git cherry-pick in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git cherry-pick HEAD~1" },
	worktrees.primary,
);

checkGuard(
	"git revert in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git revert --no-commit HEAD" },
	worktrees.primary,
);

checkGuard(
	"git am in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git am ../patch.mbox" },
	worktrees.primary,
);

checkGuard(
	"git apply in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git apply ../fix.patch" },
	worktrees.primary,
);

checkGuard(
	"git apply --index is blocked, as it writes the working tree too",
	true,
	"bash",
	{ command: "git apply --index ../fix.patch" },
	worktrees.primary,
);

checkGuard(
	"git apply --check in the primary worktree passes",
	false,
	"bash",
	{ command: "git apply --check ../fix.patch" },
	worktrees.primary,
);

checkGuard(
	"git apply --cached in the primary worktree passes",
	false,
	"bash",
	{ command: "git apply --cached ../fix.patch" },
	worktrees.primary,
);

checkGuard(
	"git clean -fd in the primary worktree is blocked",
	true,
	"bash",
	{ command: "git clean -fd" },
	worktrees.primary,
);

checkGuard(
	"git clean --dry-run in the primary worktree passes",
	false,
	"bash",
	{ command: "git clean --dry-run" },
	worktrees.primary,
);

checkGuard(
	"git clean -n in the primary worktree passes",
	false,
	"bash",
	{ command: "git clean -n" },
	worktrees.primary,
);

checkGuard(
	"an ordinary read of the primary worktree still passes",
	false,
	"bash",
	{ command: "git status --porcelain && git log --oneline -1 && git diff" },
	worktrees.primary,
);

checkGuard(
	"a -C rewrite cannot reach the primary from a feature worktree",
	true,
	"bash",
	{ command: `git -C "${worktrees.primary}" reset --hard HEAD~1` },
	worktrees.task,
);

checkGuard(
	"a cd then rewrite cannot reach the primary from a feature worktree",
	true,
	"bash",
	{ command: `cd "${worktrees.primary}" && git stash pop` },
	worktrees.task,
);

checkGuard(
	"--work-tree cannot direct a rewrite into primary files",
	true,
	"bash",
	{
		command:
			`git --git-dir="${resolve(worktrees.task, ".git")}" ` +
			`--work-tree="${worktrees.primary}" restore tracked.txt`,
	},
	worktrees.task,
);

checkGuard(
	"a relative GIT_DIR resolves against the -C directory, not the shell's",
	true,
	"bash",
	{
		command:
			`GIT_DIR=.git git -C "${worktrees.primary}" ` +
			"switch feature/wrong-place",
	},
	worktrees.root,
);

checkGuard(
	"an unresolvable GIT_DIR falls back to the working-directory check",
	true,
	"bash",
	{
		command:
			`GIT_DIR="${resolve(worktrees.root, "nonexistent.git")}" ` +
			"git switch feature/wrong-place",
	},
	worktrees.primary,
);

checkGuard(
	"the last GIT_DIR assignment wins, as the shell exports it",
	true,
	"bash",
	{
		command:
			`GIT_DIR="${resolve(worktrees.root, "nonexistent.git")}" ` +
			`GIT_DIR="${resolve(worktrees.primary, ".git")}" ` +
			"git switch feature/wrong-place",
	},
	worktrees.task,
);

checkGuard(
	"a relative GIT_WORK_TREE resolves against the -C directory too",
	true,
	"bash",
	{
		command:
			"GIT_WORK_TREE=primary git " +
			`--git-dir="${resolve(worktrees.task, ".git")}" ` +
			`-C "${worktrees.root}" switch feature/wrong-place`,
	},
	worktrees.task,
);

checkGuard(
	"--git-dir written before -C still resolves against the -C directory",
	true,
	"bash",
	{
		command:
			`git --git-dir=.git -C "${worktrees.primary}" ` +
			"switch feature/wrong-place",
	},
	worktrees.task,
);

checkGuard(
	"--work-tree written before -C still resolves against the -C directory",
	true,
	"bash",
	{
		command:
			"git --work-tree=primary " +
			`--git-dir="${resolve(worktrees.task, ".git")}" ` +
			`-C "${worktrees.root}" switch feature/wrong-place`,
	},
	worktrees.task,
);

check("the stale worktree record precedes the detached worktree", () => {
	const listing = runGit(
		staleWorktrees.primary,
		"worktree",
		"list",
		"--porcelain",
	);
	assert.ok(
		listing.indexOf("agone") < listing.indexOf("zdetached"),
		"the fixture must list the stale record first",
	);
});

checkGuard(
	"a stale worktree record cannot let a detached-worktree write through",
	true,
	"write",
	{ path: resolve(staleWorktrees.detached, "a.txt"), content: "unsafe\n" },
	staleWorktrees.detached,
);

// --- a detached primary keeps the attach the block reason prescribes --------
checkGuard(
	"attaching a detached primary worktree in place passes",
	false,
	"bash",
	{ command: "git switch -c feature/detached-primary master" },
	detachedPrimary.primary,
);

checkGuard(
	"a write in a detached primary worktree is still blocked",
	true,
	"write",
	{ path: "new.txt", content: "unsafe\n" },
	detachedPrimary.primary,
);

// The exemption is for a session sitting in the detached primary, which has
// nowhere else to attach it. Reaching that primary from a task worktree is
// ordinary primary-checkout work, and is blocked whatever its branch state.
checkGuard(
	"a detached primary reached by -C from a task worktree is blocked",
	true,
	"bash",
	{ command: `git -C "${detachedPrimary.primary}" switch master` },
	detachedPrimary.task,
);

checkGuard(
	"an explicit work tree naming a detached primary is blocked",
	true,
	"bash",
	{
		command:
			`git --work-tree="${detachedPrimary.primary}" ` +
			`--git-dir="${resolve(detachedPrimary.task, ".git")}" ` +
			"switch feature/wrong-place",
	},
	detachedPrimary.task,
);

// The exemption is for the attach, so it is granted to the two subcommands
// that perform one. A rewrite that is not an attach destroys the detached
// checkout's work exactly as it would an attached one.
checkGuard(
	"a reset inside a detached primary worktree is blocked",
	true,
	"bash",
	{ command: "git reset --hard HEAD~1" },
	detachedPrimary.primary,
);

checkGuard(
	"a stash pop inside a detached primary worktree is blocked",
	true,
	"bash",
	{ command: "git stash pop" },
	detachedPrimary.primary,
);

// The exemption is for the attach, and so is tested on the form. A pathspec
// checkout and a forcing switch attach nothing and spend the checkout's
// uncommitted work, so neither rides it.
checkGuard(
	"a pathspec checkout inside a detached primary is blocked",
	true,
	"bash",
	{ command: "git checkout -- tracked.txt" },
	detachedPrimary.primary,
);

checkGuard(
	"a commit-and-pathspec checkout inside a detached primary is blocked",
	true,
	"bash",
	{ command: "git checkout HEAD -- tracked.txt" },
	detachedPrimary.primary,
);

checkGuard(
	"a forcing checkout inside a detached primary is blocked",
	true,
	"bash",
	{ command: "git checkout --force master" },
	detachedPrimary.primary,
);

checkGuard(
	"a discarding switch inside a detached primary is blocked",
	true,
	"bash",
	{ command: "git switch --discard-changes master" },
	detachedPrimary.primary,
);

checkGuard(
	"a detaching switch inside a detached primary is blocked",
	true,
	"bash",
	{ command: "git switch --detach master" },
	detachedPrimary.primary,
);

checkGuard(
	"attaching a detached primary to an existing branch passes",
	false,
	"bash",
	{ command: "git switch master" },
	detachedPrimary.primary,
);

checkGuard(
	"attaching a detached primary with checkout -b passes",
	false,
	"bash",
	{ command: "git checkout -b feature/detached-primary master" },
	detachedPrimary.primary,
);

checkGuard(
	"attaching a detached primary from one of its subdirectories passes",
	false,
	"bash",
	{
		command: `cd "${resolve(detachedPrimary.primary, ".git")}/.." && ` +
			"git switch -c feature/detached-primary master",
	},
	detachedPrimary.primary,
);

// --- write is guarded exactly as edit is -----------------------------------
checkGuard(
	"a write keyed file_path cannot reach the primary worktree",
	true,
	"write",
	{ file_path: resolve(worktrees.primary, "new.txt"), content: "unsafe\n" },
	worktrees.task,
);

checkGuard(
	"a write with no recognized path key falls back to the working directory",
	true,
	"write",
	{ content: "unsafe\n" },
	worktrees.primary,
);

// The same hole one layer up: a payload naming no path at all, with no
// working directory to fall back to, names no repository the guard can check.
checkGuard(
	"a write naming no path and no working directory is refused",
	true,
	"write",
	{ content: "unsafe\n" },
	undefined,
	UNANCHORED_PATH_BLOCK_REASON,
);

// --- grouped commands ------------------------------------------------------
checkGuard(
	"a subshell around cd keeps the switch rooted in the task worktree",
	false,
	"bash",
	{
		command:
			`(cd "${worktrees.detached}" && git switch -c feature/detached-fix master)`,
	},
	worktrees.primary,
);

checkGuard(
	"a brace group around cd keeps the switch rooted in the task worktree",
	false,
	"bash",
	{
		command:
			`{ cd "${worktrees.detached}" && git switch -c feature/detached-fix master; }`,
	},
	worktrees.primary,
);

checkGuard(
	"a cd inside a subshell stops applying when the subshell closes",
	false,
	"bash",
	{
		command:
			`cd "${worktrees.detached}" && (cd "${worktrees.primary}" && true) && ` +
			"git switch -c feature/detached-fix master",
	},
	worktrees.primary,
);

// A function body is stored, not run: its `cd` never moves the shell that
// defines the function, so the switch that follows still runs in the primary.
checkGuard(
	"a cd in a function body does not move the tracked directory",
	true,
	"bash",
	{
		command:
			`f() { cd "${worktrees.task}"; }\n` +
			"git switch master\n",
	},
	worktrees.primary,
);

checkGuard(
	"a cd in a subshell function body does not move it either",
	true,
	"bash",
	{
		command:
			`f() ( cd "${worktrees.task}" )\n` + "git switch master\n",
	},
	worktrees.primary,
);

checkGuard(
	"a keyword function body does not move the tracked directory",
	true,
	"bash",
	{
		command:
			`function f() { cd "${worktrees.task}"; }\n` +
			"git switch master\n",
	},
	worktrees.primary,
);

// --- the inversion: what the guard cannot read, it refuses ------------------
// The recognizer no longer looks for proof that a command is dangerous. It
// looks for proof that every command it will run has been placed, and refuses
// where it has none. These are the constructs that leaves it refusing, and the
// ordinary ones it must still let through.

check("the unreadable denial tells the model to write the command literally", () => {
	assert.match(UNREADABLE_COMMAND_BLOCK_REASON, /refused rather than allowed/iu);
	assert.match(UNREADABLE_COMMAND_BLOCK_REASON, /literally/iu);
	assert.match(UNREADABLE_COMMAND_BLOCK_REASON, /eval/iu);
});

for (const [name, command] of [
	["a string run by eval", "eval \"$script\""],
	["a string run by bash -c", "bash -c \"$script\""],
	["a string run by sh -c", "sh -c \"$script\""],
	["an executable that expands", "$g switch master"],
	["an executable that a substitution produces", "$(echo git) switch master"],
]) {
	// Refused from the task worktree, not only from the primary: the string or
	// the program may name the primary checkout itself, and `git -C <primary>`
	// reaches it from any directory at all.
	checkGuard(
		`${name} is refused even from a task worktree`,
		true,
		"bash",
		{ command },
		worktrees.task,
		UNREADABLE_COMMAND_BLOCK_REASON,
	);
}

checkGuard(
	"a quote that never closes is refused rather than half-read",
	true,
	"bash",
	{ command: 'git status "' },
	worktrees.task,
	UNREADABLE_COMMAND_BLOCK_REASON,
);

checkGuard(
	"a parenthesis that never closes is refused too",
	true,
	"bash",
	{ command: "echo $(git status" },
	worktrees.task,
	UNREADABLE_COMMAND_BLOCK_REASON,
);

// The cost the inversion accepts, stated rather than discovered: a command
// naming its interpreter through a variable is refused wherever it runs. It is
// a visible false positive with an obvious repair, which is the whole bargain —
// the alternative is a silent hole of exactly the shape four rounds kept
// finding.
checkGuard(
	"an ordinary command whose interpreter expands is refused as well",
	true,
	"bash",
	{ command: '"$PYTHON" -m pytest' },
	worktrees.task,
	UNREADABLE_COMMAND_BLOCK_REASON,
);

// Arithmetic is not a command, so a variable inside it is not an executable.
checkGuard(
	"arithmetic holding an expansion is not a command the guard must read",
	false,
	"bash",
	{ command: "n=1\necho $(( $n + 1 ))\n" },
	worktrees.task,
);

checkGuard(
	"arithmetic still cannot hide a substitution that moves a branch",
	true,
	"bash",
	{ command: `echo $(( $(cd "${worktrees.primary}" && git switch master) + 1 ))` },
	worktrees.task,
);

for (const [name, command] of [
	["a control-flow condition", "if git switch master; then true; fi"],
	["a loop condition", "while git switch master; do break; done"],
	["a negated command", "! git switch master"],
	["a literal eval", "eval 'git switch master'"],
	["a literal bash -c", "bash -c 'git switch master'"],
	["a wrapper that execs its argument", "timeout 10 git switch master"],
]) {
	// Each of these reads as a call to a keyword or a wrapper unless the
	// recognizer looks past it to the command it governs.
	checkGuard(
		`${name} does not hide a branch move in the primary`,
		true,
		"bash",
		{ command },
		worktrees.primary,
	);
}

for (const [name, command] of [
	["a cd with a double dash", `cd -- "${worktrees.primary}" && git switch master`],
	["a cd with an option", `cd -P "${worktrees.primary}" && git switch master`],
	["a pushd", `pushd "${worktrees.primary}" && git switch master`],
]) {
	// A `cd` the walker reads is followed into the primary checkout, whatever
	// options it carries.
	checkGuard(
		`${name} is followed into the primary checkout`,
		true,
		"bash",
		{ command },
		worktrees.task,
	);
}

for (const [name, command] of [
	["a cd whose target expands", `x="${worktrees.primary}"\ncd $x\ngit switch master\n`],
	["a cd that may not have happened", `cd "${worktrees.primary}" || true\ngit switch master\n`],
	["a cd with no argument at all", "cd\ngit switch master\n"],
]) {
	// A `cd` form the walker does not recognize leaves the directory unknown,
	// and a branch move with an unknown directory cannot be placed at all —
	// which is the unanchored refusal, not the worktree one.
	checkGuard(
		`${name} leaves the directory unknown rather than stale`,
		true,
		"bash",
		{ command },
		worktrees.task,
		UNANCHORED_PATH_BLOCK_REASON,
	);
}

checkGuard(
	"a function defined and then called moves the directory out of reach",
	true,
	"bash",
	{
		command:
			`f() { cd "${worktrees.primary}"; }\n` + "f\n" + "git switch master\n",
	},
	worktrees.task,
	UNANCHORED_PATH_BLOCK_REASON,
);

// Ordinary work in a task worktree is what the guard exists to leave alone.
for (const [name, command] of [
	["a read-only Git query", "git status --porcelain"],
	["an ordinary substitution", "echo $(date)"],
	["a literal interpreter", "python3 -c 'print(1)'"],
	["a branch move in the task worktree itself", "git switch -c feature/next"],
	["a cd within the task worktree", "cd subdir && git status"],
]) {
	checkGuard(`${name} still runs in a task worktree`, false, "bash", { command }, worktrees.task);
}

// --- a substitution is a substitution wherever it is written ---------------
for (const [name, command] of [
	["inside double quotes", `echo "$(git -C '${worktrees.primary}' switch master)"`],
	["as an assignment's value", `x="$(cd '${worktrees.primary}' && git switch master)"`],
	["in backticks", `echo \`cd "${worktrees.primary}" && git switch master\``],
]) {
	// The backtick spelling was tokenized and the `$(…)` one inside a quoted
	// string was not, so the same command passed or failed on its punctuation.
	checkGuard(
		`a branch move in a substitution ${name} is still a branch move`,
		true,
		"bash",
		{ command },
		worktrees.task,
	);
}

checkGuard(
	"a word the guard cannot read does not hide the git behind it",
	true,
	"bash",
	{ command: `env -u NOPE* git -C "${worktrees.primary}" switch master` },
	worktrees.task,
);

for (const [name, command] of [
	["after a condition that failed", `false && cd "${worktrees.task}"\ngit switch master\n`],
	["after a condition that succeeded", `true || cd "${worktrees.task}"\ngit switch master\n`],
]) {
	// Whether such a `cd` ran depends on an exit status the guard cannot know,
	// so the directory is unknown rather than moved — and the branch move that
	// follows cannot be placed.
	checkGuard(
		`a cd ${name} does not move the tracked directory`,
		true,
		"bash",
		{ command },
		worktrees.primary,
		UNANCHORED_PATH_BLOCK_REASON,
	);
}

checkGuard(
	"a cd downstream of a pipe never moved the shell at all",
	true,
	"bash",
	{ command: `echo x | cd "${worktrees.task}"\ngit switch master\n` },
	worktrees.primary,
);

// --- a substitution is a word, never the end of its command -----------------
for (const [name, command, reason] of [
	// An unreadable `-C` leaves the repository unplaceable, which is the
	// unanchored refusal.
	["quoted in a -C value", `git -C "$(echo '${worktrees.primary}')" switch master`, UNANCHORED_PATH_BLOCK_REASON],
	["unquoted in a -C value", `git -C $(echo ${worktrees.primary}) switch master`, UNANCHORED_PATH_BLOCK_REASON],
	["in backticks in a -C value", `git -C \`echo ${worktrees.primary}\` switch master`, UNANCHORED_PATH_BLOCK_REASON],
	["appended to a -C value", `git -C "${worktrees.primary}$(echo /.)" switch master`, UNANCHORED_PATH_BLOCK_REASON],
	// A repository selector or an option the guard cannot read is the
	// unreadable refusal instead.
	["in a GIT_DIR value", `GIT_DIR="$(echo '${worktrees.primary}')/.git" git switch master`, UNREADABLE_COMMAND_BLOCK_REASON],
	["standing in for the option itself", `git "$(echo -C)" '${worktrees.primary}' switch master`, UNREADABLE_COMMAND_BLOCK_REASON],
]) {
	// Ending the command at the substitution split `git -C` away from `switch`
	// and left neither half recognizable. The word is set aside and resumed, so
	// the invocation stays whole and what it cannot read is refused.
	checkGuard(
		`a substitution ${name} does not break the command around it`,
		true,
		"bash",
		{ command },
		worktrees.task,
		reason,
	);
}

checkGuard(
	"a git that is an argument does not shadow the git that runs",
	true,
	"bash",
	{ command: `find . -name git -exec git -C "${worktrees.primary}" switch master \\;` },
	worktrees.task,
);

checkGuard(
	"a substitution in an ordinary argument is still allowed",
	false,
	"bash",
	{ command: 'git commit -m "$(date)"' },
	worktrees.task,
);

// --- here-document bodies are data, not commands ---------------------------
checkGuard(
	"a here-document carrying a git switch line is not a branch switch",
	false,
	"bash",
	{ command: "cat > setup.sh <<'EOF'\ngit switch feature/not-executed\nEOF\n" },
	worktrees.primary,
);

checkGuard(
	"a tab-stripped here-document body is skipped too",
	false,
	"bash",
	{ command: "cat > setup.sh <<-'EOF'\n\tgit switch feature/not-executed\n\tEOF\n" },
	worktrees.primary,
);

checkGuard(
	"a here-document body cannot redirect the guard, and the next command is checked",
	true,
	"bash",
	{
		command:
			`cat > setup.sh <<'EOF'\ncd "${worktrees.detached}"\nEOF\n` +
			"git switch -c feature/wrong-place master\n",
	},
	worktrees.primary,
);

checkGuard(
	"a spaced here-document delimiter still skips its body",
	false,
	"bash",
	{ command: "cat > setup.sh << EOF\ngit switch feature/not-executed\nEOF\n" },
	worktrees.primary,
);

checkGuard(
	"a here-document on an explicit file descriptor skips its body",
	false,
	"bash",
	{ command: "cat > setup.sh 2<<EOF\ngit switch feature/not-executed\nEOF\n" },
	worktrees.primary,
);

checkGuard(
	"stacked here-documents skip both bodies and the command after them runs",
	true,
	"bash",
	{
		command:
			"cat setup.sh <<A <<B\ngit switch feature/not-executed\nA\n" +
			"git switch feature/not-executed\nB\ngit switch master\n",
	},
	worktrees.primary,
);

checkGuard(
	"a here-document inside a subshell skips its body",
	false,
	"bash",
	{
		command:
			"(cat > setup.sh <<'EOF'\ngit switch feature/not-executed\nEOF\n)\n",
	},
	worktrees.primary,
);

// An arithmetic left shift is not a redirection. Read as one, its delimiter
// line never arrives and every later command goes untokenized.
checkGuard(
	"an arithmetic left shift does not unguard the commands after it",
	true,
	"bash",
	{ command: "echo $((1 << 2))\ngit switch master\n" },
	worktrees.primary,
);

checkGuard(
	"an arithmetic evaluation does not unguard the commands after it",
	true,
	"bash",
	{ command: "(( x = 1 << 2 ))\ngit switch master\n" },
	worktrees.primary,
);

checkGuard(
	"a spaced arithmetic expansion does not unguard the commands after it",
	true,
	"bash",
	{ command: "echo $(( 1 << 4 ))\ngit switch master\n" },
	worktrees.primary,
);

checkGuard(
	"a here-document whose delimiter never arrives does not swallow the rest",
	true,
	"bash",
	{ command: "cat > setup.sh <<EOF\ngit switch master\n" },
	worktrees.primary,
);

// --- a missing working directory neither throws nor blinds the guard -------
// These two pinned the opposite expectation until the guard was made
// consistent with `gitOutput`: where the guard cannot determine the answer it
// refuses. A relative path with no working directory names no repository the
// guard can check, so the mutation is refused rather than allowed unchecked.
checkGuard(
	"a relative edit path without a working directory is refused",
	true,
	"edit",
	{ path: "tracked.txt", old_string: "a", new_string: "b" },
	undefined,
	UNANCHORED_PATH_BLOCK_REASON,
);

checkGuard(
	"a bash branch switch without any working directory is refused",
	true,
	"bash",
	{ command: "git switch feature/wrong-place" },
	undefined,
	UNANCHORED_PATH_BLOCK_REASON,
);

checkGuard(
	"a bash command that moves no branch still passes without a working directory",
	false,
	"bash",
	{ command: "git status --short" },
	undefined,
);

// With no directory anywhere there is no config to read, so the word stands
// as itself. A rewrite the guard does recognize is still refused as
// unanchored, which is the case above.
checkGuard(
	"an unrecognized subcommand without a working directory is left unresolved",
	false,
	"bash",
	{ command: "git co feature/x" },
	undefined,
);

check("the unplaceable-mutation denial says what to do instead", () => {
	assert.match(UNANCHORED_PATH_BLOCK_REASON, /refused rather than allowed/iu);
	assert.match(UNANCHORED_PATH_BLOCK_REASON, /absolute path/iu);
});

checkGuard(
	"an absolute primary path is blocked without a working directory",
	true,
	"write",
	{ path: resolve(worktrees.primary, "new.txt"), content: "unsafe\n" },
	undefined,
);

// --- a relative tool cwd is read against the session, not this process -----
checkGuard(
	"a relative tool cwd of . resolves to the session's directory",
	true,
	"bash",
	{ command: "git switch feature/wrong-place", cwd: "." },
	worktrees.primary,
);

checkGuard(
	"a relative tool cwd resolves against the session's directory",
	true,
	"bash",
	{ command: "git switch feature/wrong-place", cwd: "primary" },
	worktrees.root,
);

// --- Git that cannot be consulted fails closed and says so ----------------
/**
 * Fire one write through the guard in a child process whose PATH is `binDir`
 * alone. A fake or absent `git` cannot be installed in this process, and the
 * guard's stderr is what proves the failure is visible to an operator.
 */
function guardWithPath(binDir, target) {
	const child = spawnSync(
		process.execPath,
		[
			"--input-type=module",
			"-e",
			[
				`const mod = await import(${JSON.stringify(pathToFileURL(EXTENSION).href)});`,
				"const handlers = new Map();",
				"const node = (m) => ({ describe: () => node(m), min: () => node(m), max: () => node(m), int: () => node(m) });",
				"const pi = { zod: { object: (s) => s, string: () => node({}), number: () => node({}) },",
				"  on: (e, h) => handlers.set(e, h), registerTool: () => {}, setSessionName: async () => {},",
				"  sendMessage: () => {}, setTimeout: () => 1, clearTimer: () => {} };",
				"mod.default(pi);",
				`const target = ${JSON.stringify(target)};`,
				'const decision = handlers.get("tool_call")(',
				'  { type: "tool_call", toolCallId: "child", toolName: "write", input: { path: "new.txt", content: "x" } },',
				"  { cwd: target, ui: {} },",
				");",
				"process.stdout.write(JSON.stringify(decision ?? null));",
			].join("\n"),
		],
		{ encoding: "utf8", env: { ...process.env, PATH: binDir } },
	);
	assert.equal(child.status, 0, `child exited ${child.status}: ${child.stderr}`);
	return { decision: JSON.parse(child.stdout), stderr: child.stderr };
}

/** Two PATH directories: one with no `git`, one whose `git` always exits 128. */
function makeFakeBinFixture() {
	const root = mkdtempSync(resolve(tmpdir(), "daily-driver-bin-"));
	const absent = resolve(root, "absent");
	const refusing = resolve(root, "refusing");
	mkdirSync(absent);
	mkdirSync(refusing);
	writeFileSync(resolve(refusing, "git"), "#!/bin/sh\nexit 128\n", { mode: 0o755 });
	return { root, absent, refusing };
}

const fakeBin = makeFakeBinFixture();

check("a missing git binary fails closed and reports why", () => {
	const { decision, stderr } = guardWithPath(fakeBin.absent, worktrees.primary);
	assert.deepEqual(decision, {
		block: true,
		reason: GIT_UNAVAILABLE_BLOCK_REASON,
	});
	assert.match(stderr, /worktree guard could not run/u, "the failure is visible");
	assert.match(GIT_UNAVAILABLE_BLOCK_REASON, /could not be consulted/iu);
});

check("git answering 'not a repository' still fails open", () => {
	const { decision } = guardWithPath(fakeBin.refusing, worktrees.primary);
	assert.equal(decision, null, "a non-zero exit is Git's own answer, not a fault");
});

// --- set_session_title ------------------------------------------------------
check("set_session_title calls pi.setSessionName", async () => {
	const s = makeSession();
	const def = s.tools.get("daily_driver_set_session_title");
	assert.ok(def, "daily_driver_set_session_title is registered");
	const result = await def.execute("c1", { title: "Fix the parser" }, undefined, undefined, {});
	assert.deepEqual(s.rec.sessionNames, ["Fix the parser"]);
	assert.deepEqual(result.details, { titled: "Fix the parser" });
});

// --- get_session ------------------------------------------------------------
check("get_session reads the session manager and the serving model", async () => {
	const s = makeSession();
	const def = s.tools.get("daily_driver_get_session");
	assert.ok(def, "daily_driver_get_session is registered");
	const ctx = {
		model: { id: "zai/glm-5.3" },
		sessionManager: {
			getSessionId: () => "0199c0a2-7d17-7b13-a2f4-6f21f5b4e9a8",
			getSessionName: () => "Fix the parser",
		},
	};
	const result = await def.execute("c0", {}, undefined, undefined, ctx);
	assert.deepEqual(result.details, {
		sessionId: "0199c0a2-7d17-7b13-a2f4-6f21f5b4e9a8",
		sessionName: "Fix the parser",
		model: "zai/glm-5.3",
	});
});

check("get_session tolerates an unnamed session and no model", async () => {
	const s = makeSession();
	const def = s.tools.get("daily_driver_get_session");
	const ctx = { sessionManager: { getSessionId: () => "s1", getSessionName: () => undefined } };
	const result = await def.execute("c0b", {}, undefined, undefined, ctx);
	assert.deepEqual(result.details, { sessionId: "s1", sessionName: null, model: null });
});

// --- schedule emits exactly once --------------------------------------------
check("schedule emits exactly one reminder after the delay", async () => {
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	assert.ok(schedule, "daily_driver_schedule is registered");
	const { triggerId } = (await schedule.execute("c2", { delaySeconds: 5, message: "Update the changelog" }, undefined, undefined, s.pi)).details;
	assert.ok(triggerId, "schedule returns a triggerId");

	// Before the delay: nothing sent.
	assert.equal(s.rec.sent.length, 0, "nothing sent before the delay");
	// Advance only partway: still nothing.
	s.timers.advance(3000);
	assert.equal(s.rec.sent.length, 0, "nothing sent before full delay");

	// Advance to expiry: exactly one, user-attributed follow-up.
	const fired = s.timers.advance(2000);
	assert.equal(fired.length, 1, "exactly one timer fires");
	assert.equal(s.rec.sent.length, 1, "exactly one message sent");
	const { msg, opts } = s.rec.sent[0];
	assert.equal(msg.customType, REMINDER_CUSTOM_TYPE);
	assert.equal(msg.content, "Update the changelog");
	assert.equal(msg.display, true);
	assert.equal(msg.attribution, "user");
	assert.equal(opts.deliverAs, "followUp");
});

// --- schedule bounds --------------------------------------------------------
check("schedule schema bounds delaySeconds to 1..86400", () => {
	// The schema is the contract Wave 2 consumes; assert its constraints exist.
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	const delay = schedule.parameters.delaySeconds._meta();
	assert.equal(delay.type, "number", "delaySeconds must be a number");
	assert.equal(delay.int, true, "delaySeconds must be an integer");
	assert.equal(delay.min, 1, "delaySeconds minimum is 1");
	assert.equal(delay.max, 86400, "delaySeconds maximum is 86400");
});

// --- cancel prevents emission -----------------------------------------------
check("cancel prevents the reminder from emitting", async () => {
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	const cancel = s.tools.get("daily_driver_cancel_schedule");
	const { triggerId } = (await schedule.execute("c3", { delaySeconds: 10, message: "Don't send" }, undefined, undefined, s.pi)).details;
	const cancelled = (await cancel.execute("c4", { triggerId }, undefined, undefined, {})).details.cancelled;
	assert.equal(cancelled, true, "a live trigger cancels");
	// Advance well past the delay: still nothing.
	s.timers.advance(60_000);
	assert.equal(s.rec.sent.length, 0, "cancelled reminder must not emit");
});

// --- cancel unknown / already-fired returns clean false ---------------------
check("cancel of an unknown id returns clean false", async () => {
	const s = makeSession();
	const cancel = s.tools.get("daily_driver_cancel_schedule");
	const r = await cancel.execute("c5", { triggerId: "no-such-trigger" }, undefined, undefined, {});
	assert.deepEqual(r.details, { cancelled: false });
});

check("cancel of an already-fired id returns clean false", async () => {
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	const cancel = s.tools.get("daily_driver_cancel_schedule");
	const { triggerId } = (await schedule.execute("c6", { delaySeconds: 1, message: "Once" }, undefined, undefined, s.pi)).details;
	s.timers.advance(1000); // fires
	assert.equal(s.rec.sent.length, 1);
	const r = await cancel.execute("c7", { triggerId }, undefined, undefined, {});
	assert.deepEqual(r.details, { cancelled: false }, "already-fired id is not live");
	// And no second emission.
	s.timers.advance(1000);
	assert.equal(s.rec.sent.length, 1);
});

// --- session_shutdown clears bookkeeping ------------------------------------
check("session_shutdown clears the trigger map", async () => {
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	const cancel = s.tools.get("daily_driver_cancel_schedule");
	const { triggerId } = (await schedule.execute("c8", { delaySeconds: 100, message: "Later" }, undefined, undefined, s.pi)).details;
	s.fire("session_shutdown", {}, {});
	// The runtime clears managed timers on shutdown and our handler drops the
	// map. Either way the trigger is no longer live: cancel returns clean
	// false and nothing fires.
	s.timers.clearAll();
	const r = await cancel.execute("c9", { triggerId }, undefined, undefined, {});
	assert.deepEqual(r.details, { cancelled: false });
	s.timers.advance(200_000);
	assert.equal(s.rec.sent.length, 0);
});

// --- package.json omp wiring -------------------------------------------------
check("package.json wires the extension and is a module", () => {
	const pkg = JSON.parse(readFileSync(resolve(ROOT, "package.json"), "utf8"));
	assert.equal(pkg.name, "daily-driver");
	assert.equal(pkg.type, "module");
	assert.equal(pkg.private, true);
	assert.deepEqual(pkg.omp, { extensions: ["./extensions/daily-driver.js"] });
});

await Promise.all(checks);
rmSync(worktrees.root, { recursive: true, force: true });
rmSync(staleWorktrees.root, { recursive: true, force: true });
rmSync(detachedPrimary.root, { recursive: true, force: true });
rmSync(fakeBin.root, { recursive: true, force: true });

console.log(results.join("\n"));
console.log("");
if (failures > 0) {
	console.error(`${failures} check(s) failed`);
	process.exit(1);
}
console.log(`all ${results.length} checks passed; Omp runtime adapter behaves as specified`);