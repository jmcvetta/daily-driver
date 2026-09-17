#!/usr/bin/env node
/**
 * Behavioural check for the Omp runtime adapter (extensions/daily-driver.js).
 *
 * Imports the extension factory with a fake `ExtensionAPI` and asserts the
 * runtime-adapter contract #145 delivers:
 *
 *   - Omp's `ask` tool is blocked with actionable text;
 *   - direct writes, edits, and branch switches in a primary worktree are
 *     blocked, as are file mutations in a detached worktree;
 *   - attached feature-worktree mutations, worktree creation, detached branch
 *     attachment, non-Git paths, and synthetic devices pass;
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
import { execFileSync } from "node:child_process";
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
import { fileURLToPath } from "node:url";

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
	REMINDER_CUSTOM_TYPE,
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
	runGit(primary, "worktree", "add", "-b", "feature/worktree-guard", task);
	runGit(primary, "worktree", "add", "--detach", detached);
	const primaryFileLink = resolve(task, "primary-file-link.txt");
	symlinkSync(resolve(primary, "tracked.txt"), primaryFileLink);
	return { root, primary, task, detached, outside, primaryFileLink };
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

function checkGuard(name, blocked, toolName, input, cwd) {
	check(name, () => {
		const decision = guardDecision(toolName, input, cwd);
		if (blocked) {
			assert.deepEqual(decision, {
				block: true,
				reason: WORKTREE_BLOCK_REASON,
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
	"a primary checkout path restore is not mistaken for a branch switch",
	false,
	"bash",
	{ command: "git checkout -- tracked.txt" },
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

console.log(results.join("\n"));
console.log("");
if (failures > 0) {
	console.error(`${failures} check(s) failed`);
	process.exit(1);
}
console.log(`all ${results.length} checks passed; Omp runtime adapter behaves as specified`);