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
import { MODEL_CLASS_ROLE_DEFAULTS, MODEL_CLASS_ROLE_TAGS, installModelClassDefaults } from "../extensions/role-default-helper.mjs";
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
 * Build a fake ExtensionAPI. `pi.on` records handlers by event; registered
 * tools, session entries, statuses, and timers remain observable offline.
 */
function fakeApi(overrides = {}) {
	const handlers = new Map();
	const calls = { sessionNames: [], sent: [], entries: [...(overrides.entries ?? [])], statuses: [], sessionName: overrides.sessionName };
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
			const registered = handlers.get(event) ?? [];
			registered.push(handler);
			handlers.set(event, registered);
		},
		registerTool(def) {
			tools.set(def.name, def);
		},
		async appendEntry(customType, data) {
			calls.entries.push({ type: "custom", customType, data });
		},
		async setSessionName(name) {
			calls.sessionNames.push(name);
			calls.sessionName = name;
		},
		sendMessage(msg, opts) {
			calls.sent.push({ msg, opts });
		},
		setTimeout: timers.setTimeout,
		clearTimer: timers.clearTimer,
		...overrides,
	};

	const fire = (event, payload, ctx) => {
		const registered = handlers.get(event);
		if (!registered) throw new Error(`no handler for ${event}`);
		const results = registered.map((handler) => handler(payload, ctx));
		return results.length === 1 ? results[0] : Promise.all(results);
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
	TITLE_BLOCK_REASON,
	UNANCHORED_PATH_BLOCK_REASON,
	UNREADABLE_COMMAND_BLOCK_REASON,
	WORKTREE_BLOCK_REASON,
	default: dailyDriverExtension,
} = module_;

function makeSession(overrides = {}, dependencies = {}) {
	const { pi, rec, tools, timers, fire } = fakeApi(overrides);
	dailyDriverExtension(pi, dependencies);
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
	const secondTask = resolve(root, "second-task");
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
	runGit(primary, "branch", "feature/worktree-guard");
	runGit(primary, "branch", "feature/second-task");
	runGit(primary, "worktree", "add", secondTask, "feature/second-task");
	runGit(primary, "worktree", "add", task, "feature/worktree-guard");
	runGit(primary, "worktree", "add", "--detach", detached);
	const primaryFileLink = resolve(task, "primary-file-link.txt");
	symlinkSync(resolve(primary, "tracked.txt"), primaryFileLink);
	const primaryDirectoryLink = resolve(task, "primary-directory-link");
	symlinkSync(primary, primaryDirectoryLink, "dir");
	// A symlinked route to the task worktree: a symlinked worktrees root, a
	// symlinked home, `/tmp` on macOS. A `cd` through one really does arrive.
	const taskLink = resolve(root, "task-link");
	symlinkSync(task, taskLink);
	return {
		root,
		primary,
		task,
		secondTask,
		taskLink,
		detached,
		outside,
		primaryFileLink,
		primaryDirectoryLink,
	};
}

const worktrees = makeWorktreeFixture();

/**
 * A checkout whose worktree listing carries two stale records — a worktree
 * removed from disk, and one whose path is now an ordinary file — both
 * ordered before a live detached worktree, so they are read first during
 * classification. Git fails the same way on each.
 */
function makeStaleWorktreeFixture() {
	const root = mkdtempSync(resolve(tmpdir(), "daily-driver-stale-"));
	const primary = resolve(root, "primary");
	const gone = resolve(root, "agone");
	const goneFile = resolve(root, "bgonefile");
	const detached = resolve(root, "zdetached");
	mkdirSync(primary);
	runGit(primary, "init", "-b", "master");
	runGit(primary, "config", "user.name", "Extension Check");
	runGit(primary, "config", "user.email", "extension-check@example.invalid");
	writeFileSync(resolve(primary, "tracked.txt"), "primary\n");
	runGit(primary, "add", "tracked.txt");
	runGit(primary, "commit", "-m", "Initial fixture");
	runGit(primary, "worktree", "add", "-b", "feature/gone", gone);
	runGit(primary, "worktree", "add", "-b", "feature/gone-file", goneFile);
	runGit(primary, "worktree", "add", "--detach", detached);
	rmSync(gone, { recursive: true, force: true });
	rmSync(goneFile, { recursive: true, force: true });
	writeFileSync(goneFile, "a file where a worktree was\n");
	return { root, primary, detached };
}

const staleWorktrees = makeStaleWorktreeFixture();

/**
 * A bare repository. Git locates it but answers that the operation must be
 * run in a work tree, which is an answer the guard acts on rather than a
 * failure to answer.
 */
function makeBareRepository() {
	const root = mkdtempSync(resolve(tmpdir(), "daily-driver-bare-"));
	runGit(root, "init", "--bare", "-b", "master");
	return root;
}

const bareRepository = makeBareRepository();

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

// --- task-class defaults are installed at session start ---------------------
const modelClassSettings = new Map();
function fakeModelClassSettings(cwd) {
	if (modelClassSettings.has(cwd)) return modelClassSettings.get(cwd).settings;
	const state = { modelRoles: {}, modelTags: {}, mutations: [] };
	state.settings = {
		getModelRole: (role) => state.modelRoles[role],
		overrideModelRoles: (roles) => {
			Object.assign(state.modelRoles, roles);
			state.mutations.push(["roles", roles]);
		},
	};
	modelClassSettings.set(cwd, state);
	return state.settings;
}
const fakeModelTagsSetting = {
	get(settings) {
		const state = [...modelClassSettings.values()].find((candidate) => candidate.settings === settings);
		assert.ok(state, "model-tag handle receives the settings instance");
		return state.modelTags;
	},
	override(settings, tags) {
		const state = [...modelClassSettings.values()].find((candidate) => candidate.settings === settings);
		assert.ok(state, "model-tag handle receives the settings instance");
		Object.assign(state.modelTags, tags);
		state.mutations.push(["tags", tags]);
	},
};

check("session_start uses Omp's model-tag handle and does not restore a cleared role", async () => {
	const s = makeSession(
		{ settingsManagerFactory: fakeModelClassSettings },
		{ modelTagsSetting: fakeModelTagsSetting },
	);
	await s.fire("session_start", {}, { cwd: "/fixture" });
	const state = modelClassSettings.get("/fixture");
	assert.equal(state.settings.get, undefined, "Omp Settings does not expose generic get");
	assert.deepEqual(state.modelRoles, MODEL_CLASS_ROLE_DEFAULTS);
	assert.deepEqual(state.modelTags, MODEL_CLASS_ROLE_TAGS);
	assert.equal(state.mutations.filter(([kind]) => kind === "roles").length, 1);
	assert.equal(state.mutations.filter(([kind]) => kind === "tags").length, 1);

	state.modelRoles.implementation = "";
	await s.fire("session_start", {}, { cwd: "/fixture" });
	assert.equal(state.modelRoles.implementation, "", "same settings instance is not initialized twice");
});

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

// --- the title gate: the first issue comment and first dispatch wait -------
const ISSUE_TITLE = "#52 Rotate the Aurora access token";
const EPIC_TITLE = "⛵ EPIC #12 Rotate the tokens";
const GH_COMMENT = "gh issue comment 52 -b 'Claiming it.'";

/** A tool context whose session reads `name`; `undefined` is an unnamed session. */
function namedCtx(name) {
	return { cwd: "/tmp", ui: {}, sessionManager: { getSessionName: () => name } };
}

/** A main-session context whose title and persisted branch entries are mutable. */
function startupCtx(session, sessionId = "main-session", agentKind = "main") {
	return {
		cwd: "/tmp",
		ui: {},
		agent: { kind: agentKind },
		sessionManager: {
			getSessionId: () => sessionId,
			getSessionName: () => session.rec.sessionName,
			getBranch: () => session.rec.entries,
		},
	};
}

const epicMetadata = `# Issue #582: Enforce epic titling
State: OPEN
Labels: task, epic
URL: https://github.com/example/project/issues/582

## Body
embark 999 is quoted issue text.
`;

/** Return the custom state recorded for an active-session fixture. */
function startupState(session) {
	return session.rec.entries.at(-1)?.data?.state;
}

let nextTitleCall = 1;

/** Drive the canonical issue read and deliver its real-shaped result. */
function deliverEpicRead(session, ctx, issue = epicMetadata, callId = "epic-read", path = "issue://582") {
	session.fire("tool_call", {
		type: "tool_call",
		toolName: "read",
		toolCallId: callId,
		input: { path },
	}, ctx);
	session.fire("tool_result", {
		type: "tool_result",
		toolName: "read",
		toolCallId: callId,
		input: { path },
		content: [{ type: "text", text: issue }],
		isError: false,
	}, ctx);
}
/** This prevents an explicit embark from reaching dispatch before the epic title is fixed. */
check("explicit embark is gated at the requested epic read and title", async () => {
	const s = makeSession();
	const ctx = startupCtx(s);
	await s.tools.get("daily_driver_set_session_title").execute(
		"stale",
		{ title: "⛵ EPIC #999 Old epic title" },
		undefined,
		undefined,
		namedCtx(undefined),
	);
	s.fire("before_agent_start", { prompt: "embark 582. No agent is currently working on it." }, ctx);
	assert.equal(startupState(s).status, "awaiting");
	assert.equal(titleCall(s, "task", {}, ctx).block, true);
	const docsBeforeIdentity = titleCall(s, "read", { path: "skill://session-title" }, ctx);
	assert.equal(docsBeforeIdentity.block, true);
	deliverEpicRead(s, ctx);
	assert.equal(startupState(s).status, "required");
	const blocked = titleCall(s, "read", { path: "skills/undertake/SKILL.md" }, ctx);
	assert.equal(blocked.block, true);
	assert.match(blocked.reason, /#582: "Enforce epic titling"/);
	assert.equal(titleCall(s, "write", {
		path: "xd://daily_driver_set_session_title",
		content: JSON.stringify({ title: "⛵ EPIC #999 Wrong epic" }),
	}, ctx).block, true);
	assert.equal(titleCall(s, "write", {
		path: "xd://daily_driver_set_session_title",
		content: JSON.stringify({ title: "⛵ EPIC #582 Enforce epic titling" }),
	}, ctx), undefined);
	const setter = s.tools.get("daily_driver_set_session_title");
	const rejected = await setter.execute("wrong", { title: "#582 Enforce epic titling" }, undefined, undefined, ctx);
	assert.equal(rejected.isError, true);
	assert.equal(s.rec.sessionNames.length, 1, "the old title call did not change the active epic title");
	const titled = await setter.execute(
		"right",
		{ title: "⛵ EPIC #582 Enforce epic titling" },
		undefined,
		undefined,
		ctx,
	);
	assert.equal(titled.details.titled, "⛵ EPIC #582 Enforce epic titling");
	assert.equal(s.rec.sessionName, "⛵ EPIC #582 Enforce epic titling");
	assert.equal(startupState(s).status, "satisfied");
	assert.equal(titleCall(s, "read", { path: "skills/undertake/SKILL.md" }, ctx), undefined);
});

/** This prevents skill-body examples from activating while preserving real command forms. */
check("explicit request parsing excludes mentions and accepts supported references", () => {
	const cases = [
		["embark 445. No agent is currently working on it.", 445],
		["/embark #446", 446],
		["embark issue://owner/repo/447", 447],
		["embark https://github.com/owner/repo/issues/448", 448],
		[
			'[IMPORTANT: User invoked the "embark" skill; follow its instructions. Full skill below.]\n' +
				"skill body contains a fake `embark 999` example.\n\n---\n\n" +
				"[Skill directory: /tmp/skills]\n" +
				"Resolve relative paths against this directory.\n" +
				"User: embark 449",
			449,
		],
		[
			'[IMPORTANT: User invoked the "embark" skill; follow its instructions. Full skill below.]\n' +
				"skill body contains no user request.\n\n[Skill directory: /tmp/skills]\n" +
				"Resolve relative paths against this directory.\nUser: issue://owner/repo/450",
			450,
		],
	];
	for (const [prompt, number] of cases) {
		const s = makeSession();
		const ctx = startupCtx(s);
		s.fire("before_agent_start", { prompt }, ctx);
		assert.equal(startupState(s).target.number, number, prompt);
	}
	for (const prompt of [
		"Please read the embark skill",
		"Discuss embark 445 with me",
		'The command is "embark 445"',
		"embark without an issue",
	]) {
		const s = makeSession();
		s.fire("before_agent_start", { prompt }, startupCtx(s));
		assert.equal(startupState(s), undefined, prompt);
	}
});

/** This prevents any discovery or dispatch call from preceding the canonical issue read. */
check("awaiting startup permits only the exact requested issue read", () => {
	const s = makeSession();
	const ctx = startupCtx(s, "first-read-session");
	s.fire("before_agent_start", { prompt: "embark 582" }, ctx);
	assert.equal(titleCall(s, "read", { path: "issue://582" }, ctx), undefined);
	for (const [tool, input] of [
		["read", { path: "README.md" }],
		["read", { path: "issue://583" }],
		["grep", { pattern: "epic" }],
		["glob", { pattern: "issues/**" }],
		["task", { tasks: [] }],
		["write", { path: "notes.md", content: "x" }],
	]) {
		const result = titleCall(s, tool, input, ctx);
		assert.equal(result.block, true, `${tool}: ${JSON.stringify(input)}`);
		assert.match(result.reason, /read the requested issue first/iu);
	}
});

/** This prevents child, malformed and stale issue results from releasing dispatch. */
check("only matching complete epic metadata arms the immediate barrier", () => {
	const s = makeSession();
	const ctx = startupCtx(s, "metadata-session");
	s.fire("before_agent_start", { prompt: "embark 582" }, ctx);
	deliverEpicRead(s, ctx, epicMetadata.replace("Labels: task, epic", "Labels: task"));
	assert.equal(startupState(s).status, "inactive");

	const pending = makeSession();
	const pendingCtx = startupCtx(pending, "pending-session");
	pending.fire("before_agent_start", { prompt: "embark 582" }, pendingCtx);
	deliverEpicRead(pending, pendingCtx, epicMetadata.replace("# Issue #582:", "# Issue #581:"));
	assert.equal(startupState(pending).status, "awaiting");
	assert.equal(titleCall(pending, "task", {}, pendingCtx).block, true);

	const stale = makeSession();
	const staleCtx = startupCtx(stale, "stale-session");
	stale.fire("before_agent_start", { prompt: "embark 582" }, staleCtx);
	deliverEpicRead(
		stale,
		staleCtx,
		"> WARNING: Live GitHub refresh failed; this issue content is cached and may be stale.\n" + epicMetadata,
	);
	assert.equal(startupState(stale).status, "awaiting");
});

/** This prevents malformed and failed reads from being mistaken for epic identity. */
check("malformed or failed issue reads leave embark awaiting", () => {
	const malformed = makeSession();
	const malformedCtx = startupCtx(malformed, "malformed-session");
	malformed.fire("before_agent_start", { prompt: "embark 582" }, malformedCtx);
	deliverEpicRead(malformed, malformedCtx, epicMetadata.replace("\n## Body\n", ""));
	assert.equal(startupState(malformed).status, "awaiting");

	const failed = makeSession();
	const failedCtx = startupCtx(failed, "failed-session");
	failed.fire("before_agent_start", { prompt: "embark 582" }, failedCtx);
	failed.fire("tool_call", {
		type: "tool_call",
		toolName: "read",
		toolCallId: "failed-read",
		input: { path: "issue://582" },
	}, failedCtx);
	failed.fire("tool_result", {
		type: "tool_result",
		toolName: "read",
		toolCallId: "failed-read",
		input: { path: "issue://582" },
		content: [{ type: "text", text: "not found" }],
		isError: true,
	}, failedCtx);
	assert.equal(startupState(failed).status, "awaiting");
});

/** This prevents a same-number issue in another repository from becoming the active epic. */
check("an explicit repository must match before epic metadata can arm", () => {
	const s = makeSession();
	const ctx = startupCtx(s, "repo-session");
	s.fire("before_agent_start", { prompt: "embark issue://owner/repo/582" }, ctx);
	deliverEpicRead(s, ctx, epicMetadata, "wrong-repository", "issue://other/repo/582");
	assert.equal(startupState(s).status, "awaiting");
	deliverEpicRead(s, ctx, epicMetadata, "wrong-response-repository", "issue://owner/repo/582");
	assert.equal(startupState(s).status, "awaiting");
	const matching = epicMetadata.replace("https://github.com/example/project", "https://github.com/owner/repo");
	deliverEpicRead(s, ctx, matching, "matching-repository", "issue://owner/repo/582");
	assert.equal(startupState(s).status, "required");
});

/** This prevents an earlier valid epic title from masking a new undertaking. */
check("a fresh embark target requires its own epic title", () => {
	const s = makeSession({ sessionName: "⛵ EPIC #582 Old title" });
	const ctx = startupCtx(s, "new-epic-session");
	s.fire("before_agent_start", { prompt: "embark 582" }, ctx);
	deliverEpicRead(s, ctx);
	assert.equal(startupState(s).status, "satisfied");
	assert.equal(s.rec.sessionNames.length, 0, "an already-correct title is not set twice");
	s.fire("before_agent_start", { prompt: "embark 583" }, ctx);
	assert.equal(startupState(s).status, "awaiting");
	assert.equal(startupState(s).target.number, 583);
});

/** This prevents a failed title write from releasing calls or losing resume state. */
check("pending title state survives setter failure and session resume", async () => {
	const first = makeSession({
		setSessionName: async () => {
			throw new Error("fixture setter failure");
		},
	});
	const ctx = startupCtx(first, "resumed-session");
	first.fire("before_agent_start", { prompt: "embark 582" }, ctx);
	deliverEpicRead(first, ctx);
	await assert.rejects(
		first.tools.get("daily_driver_set_session_title").execute(
			"failed-title",
			{ title: "⛵ EPIC #582 Epic title" },
			undefined,
			undefined,
			ctx,
		),
		/fixture setter failure/u,
	);
	assert.equal(startupState(first).status, "required");
	const resumed = makeSession({ entries: first.rec.entries });
	const resumedCtx = startupCtx(resumed, "resumed-session");
	assert.equal(titleCall(resumed, "read", { path: "README.md" }, resumedCtx).block, true);
});

/** This prevents unrelated tools and another session from inheriting title-recovery access. */
check("epic title recovery is session-scoped and respects exact routes", async () => {
	const s = makeSession();
	const ctx = startupCtx(s, "session-a");
	s.fire("before_agent_start", { prompt: "embark 582" }, ctx);
	deliverEpicRead(s, ctx);
	for (const path of [
		"xd://other/daily_driver_set_session_title",
		"xd://daily_driver_set_session_title/extra",
	]) {
		const denied = titleCall(s, "read", { path }, ctx);
		assert.equal(denied.block, true, path);
	}
	for (const path of [
		"skill://session-title",
		"skill://session-title/references/omp.md",
		"xd://daily_driver_get_session",
		"xd://daily_driver_set_session_title",
		"issue://582",
	]) {
		assert.equal(titleCall(s, "read", { path }, ctx), undefined, path);
	}
	const other = startupCtx(s, "session-b");
	assert.equal(titleCall(s, "read", { path: "skills/embark/SKILL.md" }, other), undefined);
	assert.equal(startupState(s).status, "required");
});

/** This prevents a subagent from renaming the orchestrator that spawned it. */
check("subagents do not acquire the parent session's embark title requirement", () => {
	const s = makeSession();
	s.fire("before_agent_start", { prompt: "embark 582" }, startupCtx(s, "sub-session", "sub"));
	assert.equal(startupState(s), undefined);
});

/** This prevents a missing Omp session API from silently claiming enforcement. */
check("missing main-session APIs report that early enforcement is unavailable", () => {
	const s = makeSession();
	const errors = [];
	const originalError = console.error;
	console.error = (...args) => errors.push(args.join(" "));
	try {
		s.fire("before_agent_start", { prompt: "embark 582" }, { agent: { kind: "main" } });
	} finally {
		console.error = originalError;
	}
	assert.ok(errors.some((message) => /embark title enforcement unavailable/iu.test(message)));
	assert.equal(startupState(s), undefined);
});

/** This prevents a stale embark title requirement from blocking a replacement workflow. */
check("explicit undertake and stand-down commands supersede startup state", () => {
	for (const prompt of [
		"undertake 583",
		"/stand-down",
		'[IMPORTANT: User invoked the "undertake" skill; follow its instructions.]\nUser: 583',
		'[IMPORTANT: User invoked the "stand-down" skill; follow its instructions.]\nUser:',
	]) {
		const s = makeSession();
		const ctx = startupCtx(s, `supersede-${prompt}`);
		s.fire("before_agent_start", { prompt: "embark 582" }, ctx);
		deliverEpicRead(s, ctx);
		assert.equal(startupState(s).status, "required");
		s.fire("before_agent_start", { prompt }, ctx);
		assert.equal(startupState(s).status, "inactive", prompt);
	}
});

function titleCall(session, toolName, input, ctx) {
	return session.fire(
		"tool_call",
		{ type: "tool_call", toolCallId: `title-${nextTitleCall++}`, toolName, input },
		ctx,
	);
}

function assertTitleBlocked(decision) {
	assert.deepEqual(decision, { block: true, reason: TITLE_BLOCK_REASON });
}

check("the title reason names the call, both forms, session-title and no retry", () => {
	assert.match(TITLE_BLOCK_REASON, /do not retry/i);
	assert.match(TITLE_BLOCK_REASON, /daily_driver_set_session_title\(\{ title \}\)/);
	assert.match(TITLE_BLOCK_REASON, /succeeds/);
	assert.match(TITLE_BLOCK_REASON, /`session-title`/);
	// The two forms are asserted against the skill that owns them, so a change
	// to either turns this red rather than silently splitting the gate from it.
	const skill = readFileSync(resolve(ROOT, "skills", "session-title", "SKILL.md"), "utf8");
	for (const form of ["#{number} {shortened issue title}", "⛵ EPIC #{number} {shortened epic title}"]) {
		assert.ok(TITLE_BLOCK_REASON.includes(form), `reason quotes ${form}`);
		assert.ok(skill.includes(form), `session-title still states ${form}`);
	}
});

check("a gh issue comment is blocked in an unnamed session", () => {
	const s = makeSession();
	assertTitleBlocked(titleCall(s, "bash", { command: GH_COMMENT }, namedCtx(undefined)));
	assertTitleBlocked(titleCall(s, "bash", { command: "gh pr comment 7 --body hi" }, namedCtx(undefined)));
});

check("a gh issue comment passes after daily_driver_set_session_title", async () => {
	const s = makeSession();
	const ctx = namedCtx(undefined);
	assertTitleBlocked(titleCall(s, "bash", { command: GH_COMMENT }, ctx));
	await s.tools.get("daily_driver_set_session_title").execute("t", { title: ISSUE_TITLE }, undefined, undefined, ctx);
	assert.equal(titleCall(s, "bash", { command: GH_COMMENT }, ctx), undefined);
	assert.equal(titleCall(s, "task", { tasks: [] }, ctx), undefined);
});

check("the recorded call is per session", async () => {
	const titled = makeSession();
	await titled.tools.get("daily_driver_set_session_title").execute("t", { title: ISSUE_TITLE }, undefined, undefined, namedCtx(undefined));
	const other = makeSession();
	assertTitleBlocked(titleCall(other, "bash", { command: GH_COMMENT }, namedCtx(undefined)));
});

check("a name already in either form passes without a call", () => {
	for (const name of [ISSUE_TITLE, EPIC_TITLE]) {
		const s = makeSession();
		assert.equal(titleCall(s, "bash", { command: GH_COMMENT }, namedCtx(name)), undefined, name);
		assert.equal(titleCall(s, "task", {}, namedCtx(name)), undefined, name);
	}
});

check("a name outside both forms is blocked", () => {
	for (const name of ["Fix the parser", "#52", "#52 ", "EPIC #12 Rotate", "", undefined]) {
		const s = makeSession();
		assertTitleBlocked(titleCall(s, "bash", { command: GH_COMMENT }, namedCtx(name)));
	}
});

check("the dispatch tool is gated the same way", () => {
	const s = makeSession();
	assertTitleBlocked(titleCall(s, "task", { tasks: [{ id: "a" }] }, namedCtx("Fix the parser")));
});

check("gh api POSTing to a comments path is gated; reads and other gh calls are not", () => {
	const s = makeSession();
	const unnamed = namedCtx(undefined);
	for (const command of [
		"gh api repos/o/r/issues/52/comments -f body=hi",
		"gh api -X POST repos/o/r/issues/52/comments",
		"gh api --method POST repos/o/r/issues/52/comments",
		"gh api --method=POST repos/o/r/issues/52/comments",
		"gh api -XPOST repos/o/r/issues/52/comments",
		"gh issue -R o/r comment 52 -b done",
		"gh issue comment 52 --repo o/r -b done",
		"gh -R o/r pr comment 7 -b done",
		"cd /tmp && gh issue comment 52 -b done",
		"bash -c 'gh issue comment 52 -b done'",
		"timeout 30 gh pr comment 7 -b done",
	]) {
		assertTitleBlocked(titleCall(s, "bash", { command }, unnamed));
	}
	for (const command of [
		"gh issue view 52",
		"gh issue view 52 --comments",
		"gh issue view -R o/r 52",
		"gh issue -R o/r view 52 --comments",
		"gh issue list",
		"gh pr checks",
		"gh pr view 7 --json comments",
		"gh api repos/o/r/issues/52/comments",
		"gh api -X GET repos/o/r/issues/52/comments",
		"gh api -X POST repos/o/r/issues",
		"gh api -f title=x repos/o/r/issues",
		"gh api -X POST repos/o/r/pulls/7/comments/99/replies",
		"gh issue create -t x -b y",
		"echo gh-issue-comment",
		"git commit -m 'gh issue comment'",
	]) {
		assert.equal(titleCall(s, "bash", { command }, unnamed), undefined, command);
	}
});

check("a context with no readable name and no recorded call is allowed, loudly", () => {
	const s = makeSession();
	const lines = [];
	const original = console.error;
	console.error = (...args) => lines.push(args.join(" "));
	try {
		assert.equal(titleCall(s, "bash", { command: GH_COMMENT }, { cwd: "/tmp", ui: {} }), undefined);
	} finally {
		console.error = original;
	}
	assert.ok(lines.some((line) => /title gate/.test(line)), "the operator is told on stderr");
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
			assert.equal(decision?.block, true);
			assert.equal(typeof decision.reason, "string");
		} else {
			assert.equal(decision, undefined);
		}
	});
}

check("relative edit from primary cwd reports the classified target and branch", () => {
	const decision = guardDecision(
		"edit",
		{
			input:
				"*** Begin Patch\n[tracked.txt#ABCD]\n" +
				"PUT 1.=1:\n+unsafe\n*** End Patch\n",
		},
		worktrees.primary,
	);
	assert.equal(decision.block, true);
	assert.match(decision.reason, /Blocked edit: the target is in the primary checkout/u);
	assert.match(decision.reason, /Supplied target: tracked\.txt/u);
	assert.match(decision.reason, new RegExp(`Tool cwd: ${worktrees.primary}`));
	assert.match(decision.reason, new RegExp(`Resolved target: ${resolve(worktrees.primary, "tracked.txt")}`));
	assert.match(decision.reason, new RegExp(`Containing worktree: ${worktrees.primary}`));
	assert.match(decision.reason, /Branch state: attached \(refs\/heads\/master\)/u);
	assert.doesNotMatch(decision.reason, /detached worktree/u);
});

check("multi-file edit reports the first disallowed target, not an allowed target", () => {
	const allowed = resolve(worktrees.task, "tracked.txt");
	const blocked = resolve(worktrees.primary, "tracked.txt");
	const decision = guardDecision(
		"edit",
		{
			input:
				`*** Begin Patch\n[${allowed}#ABCD]\nPUT 1.=1:\n+safe\n` +
				`[${blocked}#ABCD]\nPUT 1.=1:\n+unsafe\n*** End Patch\n`,
		},
		worktrees.task,
	);
	assert.equal(decision.block, true);
	assert.match(decision.reason, new RegExp(`Supplied target: ${blocked}`));
	assert.match(decision.reason, new RegExp(`Resolved target: ${blocked}`));
});

check("unparsed edit target identifies cwd fallback without inventing a file", () => {
	const decision = guardDecision("edit", { input: "unrecognized edit payload" }, worktrees.primary);
	assert.equal(decision.block, true);
	assert.match(decision.reason, /no file target was parsed; used tool cwd fallback/u);
	assert.match(decision.reason, new RegExp(`Resolved target: ${worktrees.primary}`));
	assert.doesNotMatch(decision.reason, /Supplied target:/u);
});

check("detached primary rejection distinguishes primary root from branch state", () => {
	const decision = guardDecision(
		"write",
		{ path: "tracked.txt", content: "unsafe\n" },
		detachedPrimary.primary,
	);
	assert.equal(decision.block, true);
	assert.match(decision.reason, /primary checkout/u);
	assert.match(decision.reason, /Branch state: detached \(no branch attached\)/u);
	assert.doesNotMatch(decision.reason, /detached worktree/u);
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

// HOME is a fixture directory, not the user's home. The edit header has the
// spelling Omp emits after read, while the tool cwd stays in the primary.
function homeEdit(target) {
	return {
		input:
			`*** Begin Patch\n[~/${target}#ABCD]\n` +
			"PUT 1.=1:\n+safe\n*** End Patch\n",
	};
}

for (const [name, blocked, target] of [
	["an existing feature branch reattached in a worktree accepts a home-shortened edit", false, "task/tracked.txt"],
	["a home-shortened edit into the primary remains blocked", true, "primary/tracked.txt"],
	["a home-shortened edit into a detached worktree remains blocked", true, "detached/tracked.txt"],
	["a home-shortened symlink into the primary remains blocked", true, "task/primary-file-link.txt"],
	["a native edit with a doubled home slash still guards the primary", true, resolve(worktrees.primary, "tracked.txt")],
]) {
	check(name, () => {
		const previousHome = process.env.HOME;
		process.env.HOME = worktrees.root;
		try {
			const decision = guardDecision("edit", homeEdit(target), worktrees.primary);
			if (blocked) {
				assert.equal(decision?.block, true);
				assert.match(decision.reason, /Containing worktree:/u);
			} else {
				assert.equal(decision, undefined);
			}
		} finally {
			if (previousHome === undefined) delete process.env.HOME;
			else process.env.HOME = previousHome;
		}
	});
}

// Omp's JavaScript write and bash resolvers keep doubled slashes after HOME.
// The native edit resolver instead interprets the remainder as absolute.
for (const [name, toolName, input] of [
	["a doubled home slash cannot write to the primary", "write", { path: "~//primary/tracked.txt", content: "unsafe\n" }],
	["a doubled home slash cannot select the primary as bash cwd", "bash", { command: "git switch feature/wrong-place", cwd: "~//primary" }],
]) {
	check(name, () => {
		const previousHome = process.env.HOME;
		process.env.HOME = worktrees.root;
		try {
			const decision = guardDecision(toolName, input, worktrees.task);
			assert.equal(decision?.block, true);
			if (toolName === "bash") {
				assert.equal(decision.reason, WORKTREE_BLOCK_REASON);
			} else {
				assert.match(decision.reason, /primary checkout/u);
				assert.match(decision.reason, /Resolved target:/u);
			}
		} finally {
			if (previousHome === undefined) delete process.env.HOME;
			else process.env.HOME = previousHome;
		}
	});
}

checkGuard(
	"an attached-worktree symlink cannot redirect a write into the primary",
	true,
	"write",
	{ path: worktrees.primaryFileLink, content: "unsafe\n" },
	worktrees.task,
);

check("detached worktree rejection names its root and missing branch", () => {
	const decision = guardDecision(
		"write",
		{ path: "tracked.txt", content: "unsafe\n" },
		worktrees.detached,
	);
	assert.equal(decision.block, true);
	assert.match(decision.reason, /detached worktree/u);
	assert.match(decision.reason, new RegExp(`Containing worktree: ${worktrees.detached}`));
	assert.match(decision.reason, /Branch state: detached \(no branch attached\)/u);
});

check("symlinked primary target reports its canonical target", () => {
	const decision = guardDecision(
		"write",
		{ path: worktrees.primaryFileLink, content: "unsafe\n" },
		worktrees.task,
	);
	assert.equal(decision.block, true);
	assert.match(decision.reason, new RegExp(`Supplied target: ${worktrees.primaryFileLink}`));
	assert.match(decision.reason, new RegExp(`Resolved target: ${resolve(worktrees.primary, "tracked.txt")}`));
});


check("new target through symlinked parent reports canonical primary path", () => {
	const target = resolve(worktrees.primaryDirectoryLink, "new-file.txt");
	const canonicalTarget = resolve(worktrees.primary, "new-file.txt");
	const decision = guardDecision(
		"write",
		{ path: target, content: "unsafe\n" },
		worktrees.task,
	);
	assert.equal(decision.block, true);
	assert.match(decision.reason, new RegExp(`Supplied target: ${target}`));
	assert.match(decision.reason, new RegExp(`Resolved target: ${canonicalTarget}`));
	assert.match(decision.reason, new RegExp(`Containing worktree: ${worktrees.primary}`));
});
check("move destination into primary is the reported offending target", () => {
	const destination = resolve(worktrees.primary, "moved.txt");
	const decision = guardDecision(
		"edit",
		{
			input:
				`*** Begin Patch\n[${resolve(worktrees.task, "tracked.txt")}#ABCD]\n` +
				`MV ${destination}\n*** End Patch\n`,
		},
		worktrees.task,
	);
	assert.equal(decision.block, true);
	assert.match(decision.reason, new RegExp(`Supplied target: ${destination}`));
	assert.match(decision.reason, new RegExp(`Resolved target: ${destination}`));
});

check("absolute primary target from task cwd is explicitly identified", () => {
	const target = resolve(worktrees.primary, "tracked.txt");
	const decision = guardDecision(
		"edit",
		{ input: `*** Begin Patch\n[${target}#ABCD]\nPUT 1.=1:\n+unsafe\n*** End Patch\n` },
		worktrees.task,
	);
	assert.equal(decision.block, true);
	assert.match(decision.reason, new RegExp(`Supplied target: ${target}`));
	assert.match(decision.reason, new RegExp(`Tool cwd: ${worktrees.task}`));
});
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

check("the stale worktree records precede the detached worktree", () => {
	const listing = runGit(
		staleWorktrees.primary,
		"worktree",
		"list",
		"--porcelain",
	);
	assert.ok(
		listing.indexOf("agone") < listing.indexOf("bgonefile") &&
			listing.indexOf("bgonefile") < listing.indexOf("zdetached"),
		"the fixture must list both stale records first",
	);
});

checkGuard(
	"a stale worktree record cannot let a detached-worktree write through",
	true,
	"write",
	{ path: resolve(staleWorktrees.detached, "a.txt"), content: "unsafe\n" },
	staleWorktrees.detached,
);

// The selected Git directory is the detached worktree's, so classification
// must walk past the stale record to reach it. A `switch` there moves no
// primary checkout, so the guard's own answer is to pass it; a stale record
// must not turn that answer into "Git could not be consulted".
checkGuard(
	"a stale worktree record does not make --git-dir unreadable",
	false,
	"bash",
	{
		command:
			`git --git-dir="${resolve(staleWorktrees.detached, ".git")}" ` +
			"switch feature/wrong-place",
	},
	staleWorktrees.primary,
);

// --- a repository with no working tree is still Git answering ---------------
checkGuard(
	"a write inside the primary's .git directory passes",
	false,
	"write",
	{ path: resolve(worktrees.primary, ".git", "scratch.txt"), content: "x\n" },
	worktrees.primary,
);

checkGuard(
	"a write in a bare repository passes",
	false,
	"write",
	{ path: resolve(bareRepository, "scratch.txt"), content: "x\n" },
	worktrees.primary,
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

// Without the event shape, a direct parser check can pass while the service
// hook still refuses the documented command before it runs.
for (const command of [
	"bash scripts/pr-keep-current.sh 511",
	"printf 'keep-current-started\\n'; exec bash scripts/pr-keep-current.sh 511",
]) {
	checkGuard(
		`the keep-current service accepts ${command}`,
		false,
		"bash",
		{
			command,
			cwd: worktrees.task,
			name: "keep-current-511",
			ready: { log: "keep-current-started" },
		},
		worktrees.primary,
	);
}

// Service metadata must not exempt a wrapped command string that targets the
// primary checkout from the same guard that accepts the script invocation.
checkGuard(
	"a service wrapper cannot move the primary checkout",
	true,
	"bash",
	{
		command: `printf 'keep-current-started\\n'; exec bash -c 'git -C "${worktrees.primary}" switch master'`,
		cwd: worktrees.task,
		name: "keep-current-511",
		ready: { log: "keep-current-started" },
	},
	worktrees.primary,
);

/**
 * A generic refusal gives no clue which shell element failed; copying the
 * operand or environment into that clue instead leaks a secret.
 */
check("unreadable refusals identify the mode without copying secrets", () => {
	for (const [command, cause] of [
		["bash --unclassified-secret scripts/pr-keep-current.sh 511", /unclassified option/iu],
		["bash -c \"$PRIVATE_COMMAND\"", /-c needs a literal command string/iu],
		["env bash -", /commands from stdin/iu],
		["bash <<< 'private-command-secret'", /redirected input/iu],
		["$PRIVATE_PROGRAM switch master", /executable that expands/iu],
		["git status 'private-unterminated-secret", /quote is never closed/iu],
	]) {
		const decision = guardDecision(
			"bash",
			{
				command,
				cwd: worktrees.task,
				name: "keep-current-511",
				ready: { log: "keep-current-started" },
				env: { PRIVATE_KEY: "private-environment-secret" },
			},
			worktrees.primary,
		);
		assert.equal(decision?.block, true);
		assert.ok(decision.reason.startsWith(UNREADABLE_COMMAND_BLOCK_REASON));
		assert.match(decision.reason, cause);
		assert.ok(decision.reason.length < 700, "classification cause must be bounded");
		for (const secret of [
			"unclassified-secret", "PRIVATE_COMMAND", "private-command-secret",
			"PRIVATE_PROGRAM", "private-unterminated-secret", "private-environment-secret",
		]) {
			assert.ok(!decision.reason.includes(secret), "refusal must not copy command or environment values");
		}
	}
});

// Shell script arguments are operands to an opaque program, not more command
// strings. Without these cases, the guard rejects harmless status calls or
// mistakes stdin for a literal file and lets unread commands escape inspection.
for (const [name, cwd] of [
	["in an attached task worktree", worktrees.task],
	["in the primary worktree", worktrees.primary],
]) {
	checkGuard(
		`a literal file-based shell call with arguments passes ${name}`,
		false,
		"bash",
		{
			command:
				`OMP_WEB_PROVISION_KNOWN_HOSTS="$PWD/infra/ansible/inventory/operator.local.known_hosts" ` +
				"bash scripts/provision-disposable.sh status",
		},
		cwd,
	);
}

for (const [name, command, blocked] of [
	[
		"a shell with ordinary flags",
		"bash -eu scripts/provision-disposable.sh status",
		false,
	],
	["a shell with an option argument", "bash -o pipefail scripts/provision-disposable.sh status", false],
	["a shell script after --", "bash -- scripts/provision-disposable.sh status", false],
	[
		"a command string with $0 and later arguments",
		`bash -c 'git -C "${worktrees.primary}" switch master' arg0 extra`,
		true,
	],
	[
		"a command string with combined flags and later arguments",
		`bash -ec 'git -C "${worktrees.primary}" switch master' arg0 extra`,
		true,
	],
	["a shell reading commands from stdin", "bash -", true],
	["an unclassified shell option", "bash --unknown scripts/provision-disposable.sh status", true],
]) {
	checkGuard(
		`${name} ${blocked ? "is refused" : "passes"}`,
		blocked,
		"bash",
		{ command },
		worktrees.task,
	);
}

// An interpreter is classified wherever it stands in a command, so a wrapper in
// front of it does not hide it. Without these cases the guard reads only the
// first word, and `exec bash -c '<move>'` passes because `exec` is not a shell.
for (const [name, command] of [
	[
		"the documented keep-current launch",
		"printf 'keep-current-started\\n'; exec bash scripts/pr-keep-current.sh 686",
	],
	["a wrapped script file with an argument", "timeout 5 bash scripts/provision-disposable.sh status"],
	["a wrapped literal command string that moves nothing", "exec bash -c 'true'"],
	// `grep -n sh file` reads `sh` as a script file `file`, so it must keep passing.
	["an interpreter name used as a grep operand", "grep -n sh file"],
]) {
	checkGuard(
		`${name} passes from a task worktree`,
		false,
		"bash",
		{ command },
		worktrees.task,
	);
}

for (const [name, command] of [
	["a wrapped expanded command string", 'exec bash -c "$script"'],
	["a wrapped here-document fed to a shell", "exec bash <<'EOF'\ntrue\nEOF\n"],
	// A here-document fed to a bare interpreter reads as a script file named
	// `<<EOF` unless a redirection is refused where the script would stand.
	["a here-document fed to a shell", "bash <<'EOF'\ntrue\nEOF\n"],
	["a here-string fed to a shell", "bash <<< 'true'"],
	["a file redirected into a shell", "bash < script.sh"],
	["a wrapped shell reading stdin", "env bash -"],
	// The named cost: a word that only mentions an interpreter has no operands
	// to classify, so it is refused from any cwd. A visible false positive with
	// an obvious repair, in place of a silent hole.
	["an interpreter word that is only mentioned", "command -v bash"],
]) {
	checkGuard(
		`${name} is refused from a task worktree`,
		true,
		"bash",
		{ command },
		worktrees.task,
		UNREADABLE_COMMAND_BLOCK_REASON,
	);
}

for (const [name, command] of [
	["a wrapped bash -c", `exec bash -c 'git -C "${worktrees.primary}" switch master'`],
	["a wrapped sh -c", `timeout 5 sh -c 'git -C "${worktrees.primary}" switch master'`],
]) {
	// The wrapped string is walked like a bare one, so the move is still found.
	checkGuard(
		`${name} does not hide a branch move in the primary`,
		true,
		"bash",
		{ command },
		worktrees.task,
	);
}

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
 * The stderr each fake `git` directory writes, keyed by that directory.
 * `guardWithPath` hands it to the child in the environment rather than baking
 * it into the script, so Git's own punctuation stays out of the shell.
 */
const fakeGitMessages = new Map();

/**
 * The stderr registered for one fake `git` directory. An unregistered
 * directory throws rather than defaulting to no message: a silent empty
 * message is the vacuous pass these fixtures exist to rule out.
 */
function fakeGitMessage(binDir) {
	if (!fakeGitMessages.has(binDir)) {
		throw new Error(`no fake git message registered for ${binDir}`);
	}
	return fakeGitMessages.get(binDir);
}

/**
 * Fire one write through the guard in a child process whose PATH is `binDir`
 * alone. A fake or absent `git` cannot be installed in this process, and the
 * guard's stderr is what proves the failure is visible to an operator.
 * `env` overlays the child's environment, which is how the locale case sets
 * the ambient locale the guard must override. `call` replaces the write with
 * another tool call, which is how the config read is reached: it is a `bash`
 * command's alias lookup rather than a path placement.
 */
function guardWithPath(binDir, target, env = {}, call = null) {
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
				`const call = ${JSON.stringify(call ?? { toolName: "write", input: { path: "new.txt", content: "x" } })};`,
				'const decision = handlers.get("tool_call")(',
				'  { type: "tool_call", toolCallId: "child", toolName: call.toolName, input: call.input },',
				"  { cwd: target, ui: {} },",
				");",
				"process.stdout.write(JSON.stringify(decision ?? null));",
			].join("\n"),
		],
		{
			encoding: "utf8",
			env: {
				...process.env,
				PATH: binDir,
				DAILY_DRIVER_STDERR: fakeGitMessage(binDir),
				...env,
			},
		},
	);
	assert.equal(child.status, 0, `child exited ${child.status}: ${child.stderr}`);
	return { decision: JSON.parse(child.stdout), stderr: child.stderr };
}

/**
 * PATH directories holding one fake `git` each. `absent` holds none at all;
 * every other entry exits 128 with the stderr Git itself writes for that
 * case, because the guard now reads the message rather than the status.
 */
function makeFakeBinFixture() {
	const root = mkdtempSync(resolve(tmpdir(), "daily-driver-bin-"));
	const absent = resolve(root, "absent");
	mkdirSync(absent);
	// Registered empty on purpose: there is no `git` here to print anything.
	fakeGitMessages.set(absent, "");
	/** Install a `git` that writes `stderr` to fd 2 and exits 128. */
	const refusing = (name, stderr) => {
		const dir = resolve(root, name);
		mkdirSync(dir);
		writeFileSync(
			resolve(dir, "git"),
			// The message reaches the script as $DAILY_DRIVER_STDERR, never
			// interpolated into it: a backtick or a quote in Git's own wording
			// would otherwise make the fixture a shell syntax error, and the
			// check would pass on that instead of on what it names.
			[
				"#!/bin/sh",
				'printf \'%s\\n\' "$DAILY_DRIVER_STDERR" >&2',
				"exit 128",
			].join("\n") + "\n",
			{ mode: 0o755 },
		);
		fakeGitMessages.set(dir, stderr);
		return dir;
	};
	return {
		root,
		absent,
		notARepository: refusing(
			"not-a-repository",
			"fatal: not a git repository (or any of the parent directories): .git",
		),
		dubiousOwnership: refusing(
			"dubious-ownership",
			"fatal: detected dubious ownership in repository at '/home/user/repo'",
		),
		unknownOption: refusing("unknown-option", "error: unknown option `z'"),
		silent: refusing("silent", ""),
		localeSensitive: localeSensitiveGit(root),
	};
}

/**
 * A `git` that speaks English only under `LC_ALL=C`. It stands in for a Git
 * whose messages are translated, so the fixture fails open only when the
 * guard pinned the locale for the call.
 */
function localeSensitiveGit(root) {
	const dir = resolve(root, "locale-sensitive");
	mkdirSync(dir);
	writeFileSync(
		resolve(dir, "git"),
		[
			"#!/bin/sh",
			'if [ "$LC_ALL" = C ] && [ -z "$LANGUAGE" ]; then',
			"  echo 'fatal: not a git repository (or any of the parent directories): .git' >&2",
			"else",
			"  echo 'schwerwiegend: kein Git-Repository' >&2",
			"fi",
			"exit 128",
		].join("\n") + "\n",
		{ mode: 0o755 },
	);
	// Registered empty on purpose: this script writes its own message and
	// ignores the variable.
	fakeGitMessages.set(dir, "");
	return dir;
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
	const { decision } = guardWithPath(fakeBin.notARepository, worktrees.primary);
	assert.equal(decision, null, "that message is Git's own answer, not a fault");
});

check("a dubious-ownership refusal fails closed", () => {
	const { decision, stderr } = guardWithPath(
		fakeBin.dubiousOwnership,
		worktrees.primary,
	);
	assert.deepEqual(
		decision,
		{ block: true, reason: GIT_UNAVAILABLE_BLOCK_REASON },
		"a safe.directory refusal is Git failing to answer, not answering",
	);
	assert.match(stderr, /dubious ownership/u, "the cause reaches the operator");
});

check("an option an older git rejects fails closed", () => {
	const { decision } = guardWithPath(fakeBin.unknownOption, worktrees.primary);
	assert.deepEqual(decision, {
		block: true,
		reason: GIT_UNAVAILABLE_BLOCK_REASON,
	});
});

check("the guard pins git's locale, so the message it matches is English", () => {
	// A `git` that answers "not a repository" only when the locale is pinned:
	// unpinned, it writes a translated message the guard must not read as an
	// answer. The child starts from a German locale, so fail-open here can
	// only mean the guard overrode it — an inherited `LC_ALL=C` cannot carry
	// the check.
	const { decision } = guardWithPath(fakeBin.localeSensitive, worktrees.primary, {
		LC_ALL: "de_DE.UTF-8",
		LANGUAGE: "de",
	});
	assert.equal(decision, null, "git ran under LC_ALL=C");
});

check("a config read Git declines fails closed", () => {
	// The alias lookup runs before any placement, so this is the config read
	// failing rather than the worktree query. An absent alias is an exit of 1
	// with nothing on stderr; a refusal is anything else, and must not be
	// read as "no alias, carry on".
	const { decision, stderr } = guardWithPath(
		fakeBin.dubiousOwnership,
		worktrees.primary,
		{},
		{ toolName: "bash", input: { command: "git lg -1" } },
	);
	assert.deepEqual(decision, {
		block: true,
		reason: GIT_UNAVAILABLE_BLOCK_REASON,
	});
	assert.match(stderr, /config --get alias\.lg/u, "the config read is named");
});

check("a non-zero exit with no message fails closed", () => {
	const { decision, stderr } = guardWithPath(fakeBin.silent, worktrees.primary);
	assert.deepEqual(decision, {
		block: true,
		reason: GIT_UNAVAILABLE_BLOCK_REASON,
	});
	assert.match(stderr, /exited 128/u, "the bare status is reported as such");
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

// --- legacy task worktree entries do not restore a separate status ----------
check("legacy worktree entries do not change cwd or create a task status", async () => {
	const s = makeSession(
		{ settingsManagerFactory: fakeModelClassSettings },
		{ modelTagsSetting: fakeModelTagsSetting },
	);
	const statuses = [];
	const ctx = {
		cwd: worktrees.primary,
		ui: { setStatus: (...args) => statuses.push(args) },
		sessionManager: {
			getBranch: () => [{
				type: "custom",
				customType: "daily-driver.task-worktree",
				data: { path: worktrees.task, branch: "feature/worktree-guard" },
			}],
		},
	};
	await s.fire("session_start", {}, ctx);
	assert.equal(ctx.cwd, worktrees.primary);
	assert.deepEqual(statuses, []);
	assert.deepEqual(s.rec.entries, []);
	assert.equal(s.tools.has("daily_driver_register_task_worktree"), false);
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