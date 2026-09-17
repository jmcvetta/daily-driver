/**
 * Omp runtime adapter for daily-driver.
 *
 * This is the thin Oh My Pi half of the daily-driver plugin. Claude Code gets
 * the same behaviour from `hooks/hooks.json` + `hooks/ask-in-chat.py`; this
 * module brings that behaviour to Omp (Oh My Pi) as an `ExtensionAPI` factory,
 * where hooks are not the mechanism. The two harnesses share the skills and
 * the one marketplace catalog (`.claude-plugin/marketplace.json` — Omp reads
 * that Claude-compatible catalog, so there is deliberately no
 * `.omp-plugin/marketplace.json`).
 *
 * Three jobs:
 *
 * 1. Block Omp's `ask` tool, the way Claude Code denies `AskUserQuestion`.
 *    The model is told not to retry and to ask the question in chat instead,
 *    putting the question, the options, and the recommendation in the reply.
 *    See `docs/notes/0009-deny-the-question-widget.md` for the reasoning on
 *    the Claude side; the same reason closes the Omp widget: on a phone it is
 *    harder to work with than prose, and the operator's answer is the same
 *    every time.
 *
 * 2. Block direct file mutations and branch switches in a repository's
 *    primary checkout, plus file mutations in a detached worktree. The
 *    model-directed `task-worktree` workflow still chooses the task identity
 *    and establishes or reuses its dedicated worktree; this guard makes
 *    forgetting it fail before the user's checkout is changed.
 *
 * 3. Provide session-title, scheduled-reminder, and session-info tools that
 *    Omp's `ExtensionAPI` makes natural. `daily_driver_set_session_title`,
 *    `daily_driver_schedule` / `daily_driver_cancel_schedule`, and
 *    `daily_driver_get_session`, are the Omp runtime-adapter surface that
 *    Wave 2 (harness-portable skills) consumes.
 *
 * This file has no third-party dependencies: it runs as a plain `.js` module
 * under Omp, with no build step and no package install between this repo and
 * a user's `~/.omp`. All per-session state lives in the factory closure so two
 * sessions in one process never share a trigger map.
 */

import { execFileSync } from "node:child_process";
import { existsSync, realpathSync, statSync } from "node:fs";
import { basename, dirname, isAbsolute, resolve } from "node:path";

/**
 * What the model is told when it calls Omp's `ask` tool. Mirrors the wording
 * of `hooks/ask-in-chat.py`'s REASON so the two harnesses deny the widget the
 * same way.
 */
export const ASK_BLOCK_REASON =
	"The ask tool is closed in this configuration. Calling it again will be " +
	"denied in the same way, so do not retry it.\n\n" +
	"Ask the same question in your chat reply instead. Write the question as " +
	"prose, give the options as a short list, and name the one you recommend " +
	"and why. The user answers in chat.\n\n" +
	"Check first whether the question needs asking at all. The " +
	"`judgement-call` skill's gate settles most of these — where the correct, " +
	"standard way already picks the answer, make the call, say in one line " +
	"which way it went, and carry on. This adapter governs how a question that " +
	"survives that gate is put, not whether it is worth putting.";

/** What an unsafe repository mutation is told to do instead. */
export const WORKTREE_BLOCK_REASON =
	"Direct file changes are blocked in the primary checkout and in detached " +
	"worktrees, and branch switches are blocked in the primary checkout. Do " +
	"not retry the mutation there. Invoke the `task-worktree` skill, establish " +
	"the task's feature branch in its dedicated worktree (attaching this " +
	"worktree in place when it is already dedicated), and repeat the operation " +
	"with its path rooted there.";

/** What a mutation is told when Git itself could not be consulted. */
export const GIT_UNAVAILABLE_BLOCK_REASON =
	"Git could not be consulted, so this operation cannot be checked against " +
	"the task worktree boundary. It is refused rather than allowed unchecked. " +
	"Either `git` is missing from PATH, or the repository query timed out. Do " +
	"not retry it blind: tell the user, so the cause is fixed before " +
	"repository work continues.";

/**
 * Git was never consulted: `git` is missing from PATH, or a query was killed
 * by the timeout. Distinct from Git answering "not a repository", which is an
 * answer the guard can act on.
 */
class GitUnavailableError extends Error {
	/** @param {string} message Why Git could not be consulted. */
	constructor(message) {
		super(message);
		this.name = "GitUnavailableError";
	}
}

/**
 * The customType namespacing scheduled reminders. Omp delivers a reminder as
 * a custom message via `pi.sendMessage`; a distinct namespaced customType is
 * what keeps `daily-driver` reminders identifiable and separate from
 * user/assistant turns.
 */
export const REMINDER_CUSTOM_TYPE = "daily-driver.reminder";

/**
 * Return command output, or null where `cwd` is not a usable Git repository.
 * The guard must fail open outside Git: ordinary files and synthetic tool
 * devices are not task worktrees. A non-zero exit is that answer from Git
 * itself; every other failure means Git never answered, which is a
 * `GitUnavailableError` so the caller can fail closed instead of mistaking an
 * unconsulted guard for a path outside Git.
 */
function gitOutput(cwd, ...args) {
	try {
		return execFileSync("git", ["-C", cwd, ...args], {
			encoding: "utf8",
			stdio: ["ignore", "pipe", "ignore"],
			timeout: 3000,
		}).trim();
	} catch (err) {
		if (typeof err?.status === "number") return null;
		const detail =
			err?.code === "ENOENT" ? "git is not on PATH" : `${err?.code ?? err}`;
		throw new GitUnavailableError(
			`git ${args.join(" ")} in ${cwd} could not be run: ${detail}`,
		);
	}
}

/** Find and canonicalize the nearest existing directory for a Git lookup. */
function existingDirectory(path) {
	let candidate = path;
	try {
		if (existsSync(candidate)) {
			const canonical = realpathSync(candidate);
			return statSync(canonical).isDirectory()
				? canonical
				: dirname(canonical);
		}
	} catch {
		candidate = dirname(candidate);
	}

	while (!existsSync(candidate)) {
		const parent = dirname(candidate);
		if (parent === candidate) return null;
		candidate = parent;
	}
	try {
		return realpathSync(candidate);
	} catch {
		return null;
	}
}

/** Parse `git worktree list --porcelain -z` into ordered worktree records. */
function worktreeRecords(listing) {
	const records = [];
	let record = null;
	for (const field of listing?.split("\0") ?? []) {
		if (field.startsWith("worktree ")) {
			if (record) records.push(record);
			record = { root: field.slice("worktree ".length), branch: "" };
		} else if (record && field.startsWith("branch ")) {
			record.branch = field.slice("branch ".length);
		}
	}
	if (record) records.push(record);
	return records;
}

/** Canonicalize one path. Null where it cannot be resolved. */
function resolvedPath(path) {
	try {
		return realpathSync(path);
	} catch {
		return null;
	}
}

/**
 * Build guard state for one root from an ordered worktree listing. A stale
 * record — a worktree deleted but not pruned — is skipped rather than fatal,
 * so one such entry cannot abort classification for every path.
 */
function stateForWorktree(records, currentRoot) {
	if (records.length === 0 || !currentRoot) return null;
	const normalizedRoot = resolvedPath(currentRoot);
	const primaryRoot = resolvedPath(records[0].root);
	if (!normalizedRoot || !primaryRoot) return null;
	const current = records.find(
		(record) => resolvedPath(record.root) === normalizedRoot,
	);
	if (!current) return null;
	return { root: normalizedRoot, primaryRoot, branch: current.branch };
}

/**
 * Anchor one tool-supplied path to the tool's working directory. Null where a
 * relative path arrives without a usable working directory: the guard cannot
 * tell which repository such a path names, and a guess would be worse than an
 * unclassified path. An absolute path needs no anchor and is always usable.
 */
function anchoredPath(cwd, path) {
	if (isAbsolute(path)) return path;
	return typeof cwd === "string" && cwd.length > 0 ? resolve(cwd, path) : null;
}

/**
 * Describe the worktree containing one local path. Null means the path is not
 * in a Git worktree, so this policy does not own it.
 */
function worktreeState(path, cwd) {
	if (
		typeof path !== "string" ||
		path.length === 0 ||
		/^[a-z][a-z0-9+.-]*:\/\//iu.test(path)
	) {
		return null;
	}

	const target = anchoredPath(cwd, path);
	if (target === null) return null;
	const anchor = existingDirectory(target);
	if (!anchor) return null;
	const root = gitOutput(anchor, "rev-parse", "--show-toplevel");
	if (!root) return null;
	const listing = gitOutput(root, "worktree", "list", "--porcelain", "-z");
	return stateForWorktree(worktreeRecords(listing), root);
}

/** Describe the worktree whose HEAD is selected by an explicit Git directory. */
function worktreeStateFromGitDir(gitDir, cwd) {
	const absoluteGitDir = gitOutput(
		cwd,
		`--git-dir=${gitDir}`,
		"rev-parse",
		"--absolute-git-dir",
	);
	if (!absoluteGitDir) return null;
	const listing = gitOutput(
		cwd,
		`--git-dir=${absoluteGitDir}`,
		"worktree",
		"list",
		"--porcelain",
		"-z",
	);
	const records = worktreeRecords(listing);
	let selectedRoot = null;
	try {
		const selectedGitDir = realpathSync(absoluteGitDir);
		for (const record of records) {
			const recordGitDir = gitOutput(
				record.root,
				"rev-parse",
				"--absolute-git-dir",
			);
			if (recordGitDir && realpathSync(recordGitDir) === selectedGitDir) {
				selectedRoot = record.root;
				break;
			}
		}
	} catch (err) {
		if (err instanceof GitUnavailableError) throw err;
		return null;
	}
	return stateForWorktree(records, selectedRoot);
}

/** Remove the quoting accepted around paths in textual edit formats. */
function normalizeEditPath(path) {
	const trimmed = path.trim();
	if (trimmed.length < 2) return trimmed;
	const quote = trimmed[0];
	return (quote === '"' || quote === "'") && trimmed.at(-1) === quote
		? trimmed.slice(1, -1)
		: trimmed;
}

/** Paths encoded inside hashline, apply-patch, or sloppy edit payloads. */
function textualEditPaths(input) {
	if (typeof input !== "string") return [];
	const paths = [];
	let hashlineSection = false;
	for (const rawLine of input.replace(/^\uFEFF/u, "").split(/\r?\n/u)) {
		const hashline = /^\[(.+)#[0-9a-f]{4}\]$/iu.exec(rawLine);
		if (hashline) {
			paths.push(normalizeEditPath(hashline[1]));
			hashlineSection = true;
			continue;
		}
		const applyPatch = /^\*\*\* (?:Add|Delete|Update) File: (.+)$/u.exec(rawLine);
		if (applyPatch) {
			paths.push(normalizeEditPath(applyPatch[1]));
			hashlineSection = false;
			continue;
		}
		const applyPatchMove = /^\*\*\* Move to: (.+)$/u.exec(rawLine);
		if (applyPatchMove) {
			paths.push(normalizeEditPath(applyPatchMove[1]));
			continue;
		}
		const sloppy = /^<SM:EDIT\s+path=(?:"([^"]+)"|'([^']+)')(?:\s+all)?>$/u.exec(
			rawLine,
		);
		if (sloppy) {
			paths.push(sloppy[1] ?? sloppy[2]);
			hashlineSection = false;
			continue;
		}
		if (hashlineSection) {
			const move = /^MV\s+(.+)$/u.exec(rawLine.trim());
			if (move) paths.push(normalizeEditPath(move[1]));
		}
	}
	return paths.filter((path) => path.length > 0);
}

/**
 * Local file paths a mutating tool call is about to change. `write` and `edit`
 * are read the same way on purpose: a payload spelling its target `file_path`
 * rather than `path` names the same file whichever tool carries it, so one
 * weaker branch would be a way around the other.
 */
function mutationPaths(event, cwd) {
	if (event.toolName !== "write" && event.toolName !== "edit") return [];

	const paths = [];
	for (const key of ["path", "file_path", "_path"]) {
		if (typeof event.input?.[key] === "string") paths.push(event.input[key]);
	}
	if (Array.isArray(event.input?.paths)) {
		paths.push(...event.input.paths.filter((path) => typeof path === "string"));
	}
	if (Array.isArray(event.input?.edits)) {
		for (const edit of event.input.edits) {
			if (!edit || typeof edit !== "object") continue;
			for (const key of ["path", "rename", "move"]) {
				if (typeof edit[key] === "string") paths.push(edit[key]);
			}
		}
	}
	for (const key of ["input", "_input"]) {
		paths.push(...textualEditPaths(event.input?.[key]));
	}
	// A malformed or future edit format has no trustworthy target metadata.
	// Its only safe anchor is the tool's working directory. Where even that is
	// missing there is nothing to classify, and `worktreeState` says so.
	if (paths.length > 0) return [...new Set(paths)];
	return typeof cwd === "string" && cwd.length > 0 ? [cwd] : [];
}

/**
 * Advance past the here-document bodies owed by one command line. Returns the
 * index of the first character after the last body, so the caller resumes
 * tokenizing the next command rather than the text being written.
 */
function skipHeredocBodies(command, start, heredocs) {
	let position = start;
	for (const { delimiter, stripTabs } of heredocs) {
		while (position < command.length) {
			const newline = command.indexOf("\n", position);
			const end = newline < 0 ? command.length : newline;
			const line = command.slice(position, end);
			position = Math.min(end + 1, command.length);
			if ((stripTabs ? line.replace(/^\t+/u, "") : line) === delimiter) break;
		}
	}
	return position;
}

/**
 * Split a literal shell command into executable segments. This is deliberately
 * a command recognizer, not a shell security boundary: expansions stay opaque,
 * while quoting, escaping, comments, here-document bodies, and ordinary
 * command separators keep prose such as `echo "git switch"` from looking
 * executable.
 *
 * A segment carries the words of one command and the separator that ended it.
 * A subshell emits a wordless `group` marker instead, which is how a caller
 * tracking the working directory learns where a `cd` stops applying.
 */
function shellSegments(command) {
	const segments = [];
	let words = [];
	let word = "";
	let wordStarted = false;
	let quote = null;
	let heredocWord = false;
	let heredocStripTabs = false;
	let awaitingHeredocDelimiter = false;
	const pendingHeredocs = [];

	const finishWord = () => {
		if (!wordStarted) return;
		if (awaitingHeredocDelimiter) {
			pendingHeredocs.push({ delimiter: word, stripTabs: heredocStripTabs });
			awaitingHeredocDelimiter = false;
		} else if (heredocWord) {
			const rest = word.slice(2);
			heredocStripTabs = rest.startsWith("-");
			const delimiter = heredocStripTabs ? rest.slice(1) : rest;
			if (delimiter.length > 0) {
				pendingHeredocs.push({ delimiter, stripTabs: heredocStripTabs });
			} else {
				// `<< EOF`: the delimiter is the next word.
				awaitingHeredocDelimiter = true;
			}
		}
		heredocWord = false;
		words.push(word);
		word = "";
		wordStarted = false;
	};
	const finishSegment = (separator) => {
		finishWord();
		// `{` and `}` group commands; neither is part of the command itself.
		while (words[0] === "{") words.shift();
		if (words.at(-1) === "}") words.pop();
		if (words.length > 0) segments.push({ words, separator });
		words = [];
	};

	for (let index = 0; index < command.length; index++) {
		const char = command[index];
		if (quote === "'") {
			if (char === "'") quote = null;
			else word += char;
			wordStarted = true;
			continue;
		}
		if (char === "\\") {
			const next = command[index + 1];
			if (next !== undefined) {
				word += next;
				wordStarted = true;
				index++;
			}
			continue;
		}
		if (quote === '"') {
			if (char === '"') quote = null;
			else word += char;
			wordStarted = true;
			continue;
		}
		if (char === "'" || char === '"') {
			quote = char;
			wordStarted = true;
			continue;
		}
		if (char === "#" && !wordStarted) {
			while (index + 1 < command.length && command[index + 1] !== "\n") index++;
			continue;
		}
		if (/\s/u.test(char)) {
			if (char !== "\n") {
				finishWord();
				continue;
			}
			finishSegment("\n");
			if (pendingHeredocs.length > 0) {
				// The body is data being written, not commands to recognize.
				index = skipHeredocBodies(command, index + 1, pendingHeredocs) - 1;
				pendingHeredocs.length = 0;
			}
			continue;
		}
		if (char === "(" || char === ")") {
			finishSegment(char);
			segments.push({
				words: [],
				separator: null,
				group: char === "(" ? "open" : "close",
			});
			continue;
		}
		if (char === ";" || char === "&" || char === "|") {
			const doubled = command[index + 1] === char;
			finishSegment(doubled ? char + char : char);
			if (doubled) index++;
			continue;
		}
		word += char;
		wordStarted = true;
		// `<<` outside quotes opens a here-document; `<<<` is a here-string and
		// has no body. Only an unquoted operator counts, so `echo "<<EOF"` is
		// the prose it looks like.
		if (char === "<") heredocWord = word === "<<";
	}
	finishSegment(null);
	return segments;
}

function isEnvironmentAssignment(word) {
	return /^[A-Za-z_][A-Za-z0-9_]*=/u.test(word);
}

/** Find a literal git executable after common non-interpreting wrappers. */
function gitWordIndex(words) {
	let index = 0;
	while (isEnvironmentAssignment(words[index] ?? "")) index++;
	if (words[index] === "command") index++;
	if (words[index] === "env") {
		index++;
		while (
			(words[index]?.startsWith("-") ?? false) ||
			isEnvironmentAssignment(words[index] ?? "")
		) {
			index++;
		}
	}
	return basename(words[index] ?? "") === "git" ? index : -1;
}

/**
 * Read one environment assignment that precedes the Git executable. A shell
 * exports the last assignment of a name, so the scan runs right to left.
 */
function environmentValue(words, end, name) {
	const prefix = `${name}=`;
	for (let index = end - 1; index >= 0; index--) {
		if (words[index].startsWith(prefix)) {
			return words[index].slice(prefix.length);
		}
	}
	return null;
}

/**
 * Resolve one path selector against the Git working directory. Null stays null.
 */
function selectedPath(gitCwd, value) {
	return value === null ? null : resolve(gitCwd, value);
}

/** Resolve one Git invocation's subcommand and repository selectors. */
function gitInvocation(words, shellCwd) {
	let index = gitWordIndex(words);
	if (index < 0) return null;
	let gitCwd = shellCwd;
	// `-C` sets the directory every other path selector is read against: a
	// relative --git-dir, --work-tree, GIT_DIR or GIT_WORK_TREE resolves
	// against the directory `-C` establishes, whatever the word order. So each
	// selector is captured raw here and resolved once, after the loop. A flag
	// overrides the matching environment variable.
	const environmentGitDir = environmentValue(words, index, "GIT_DIR");
	const environmentWorkTree = environmentValue(words, index, "GIT_WORK_TREE");
	let gitDir = null;
	let workTree = null;
	index++;
	for (; index < words.length; index++) {
		const word = words[index];
		if (word === "-C" && typeof words[index + 1] === "string") {
			gitCwd = resolve(gitCwd, words[++index]);
			continue;
		}
		if (word.startsWith("-C") && word.length > 2) {
			gitCwd = resolve(gitCwd, word.slice(2));
			continue;
		}
		if (word === "--work-tree" && typeof words[index + 1] === "string") {
			workTree = words[++index];
			continue;
		}
		if (word.startsWith("--work-tree=")) {
			workTree = word.slice("--work-tree=".length);
			continue;
		}
		if (word === "--git-dir" && typeof words[index + 1] === "string") {
			gitDir = words[++index];
			continue;
		}
		if (word.startsWith("--git-dir=")) {
			gitDir = word.slice("--git-dir=".length);
			continue;
		}
		if (["-c", "--config-env", "--exec-path", "--namespace"].includes(word)) {
			index++;
			continue;
		}
		if (word.startsWith("-")) continue;
		return {
			subcommand: word,
			args: words.slice(index + 1),
			cwd: gitCwd,
			gitDir: selectedPath(gitCwd, gitDir ?? environmentGitDir),
			workTree: selectedPath(gitCwd, workTree ?? environmentWorkTree),
		};
	}
	return null;
}

/** Checkout with an explicit pathspec edits files but does not move HEAD. */
function changesBranch(invocation) {
	if (invocation.subcommand === "switch") return true;
	if (invocation.subcommand !== "checkout" || invocation.args.length === 0) {
		return false;
	}
	if (
		invocation.args.some(
			(arg) =>
				arg === "-b" ||
				arg === "-B" ||
				arg === "--orphan" ||
				arg === "--detach" ||
				arg.startsWith("--orphan="),
		)
	) {
		return true;
	}
	if (invocation.args.includes("--")) return false;
	return !invocation.args.some((arg) =>
		["-p", "--patch", "--ours", "--theirs"].includes(arg),
	);
}

/**
 * True where a worktree state names a primary checkout that is on a branch.
 * A detached primary is the one case left open: writes there are blocked
 * already, and `WORKTREE_BLOCK_REASON` prescribes attaching the worktree in
 * place, so denying that attach too would leave the model nothing to do.
 */
function isAttachedPrimary(state) {
	return (
		state !== null &&
		state.root === state.primaryRoot &&
		state.branch.length > 0
	);
}

/** A checkout or switch that changes the primary HEAD or its files. */
function movesPrimaryBranch(event, cwd) {
	if (event.toolName !== "bash" || typeof event.input?.command !== "string") {
		return false;
	}

	// A relative tool cwd is relative to the session's directory, never to the
	// directory this Node process happens to run in.
	let shellCwd = anchoredPath(
		cwd,
		typeof event.input.cwd === "string" ? event.input.cwd : ".",
	);
	if (shellCwd === null) return false;
	const shellCwdStack = [];
	for (const segment of shellSegments(event.input.command)) {
		if (segment.group === "open") {
			shellCwdStack.push(shellCwd);
			continue;
		}
		if (segment.group === "close") {
			// A `cd` inside a subshell stops applying when the subshell ends.
			if (shellCwdStack.length > 0) shellCwd = shellCwdStack.pop();
			continue;
		}
		const invocation = gitInvocation(segment.words, shellCwd);
		if (invocation && changesBranch(invocation)) {
			const gitDirState = invocation.gitDir
				? worktreeStateFromGitDir(invocation.gitDir, invocation.cwd)
				: null;
			// A Git directory that resolves to no repository must not skip the
			// cwd check. Skipping it lets an unresolvable selector fail open.
			const repositoryState =
				gitDirState ?? worktreeState(".", invocation.cwd);
			if (isAttachedPrimary(repositoryState)) return true;
			if (invocation.workTree) {
				// Writing primary files from elsewhere is blocked whether or not
				// the primary is attached: an in-place attach never names a work
				// tree, so nothing legitimate is caught here.
				const workTreeState = worktreeState(".", invocation.workTree);
				if (
					workTreeState !== null &&
					workTreeState.root === workTreeState.primaryRoot
				) {
					return true;
				}
			}
		}

		if (
			segment.words.length === 2 &&
			segment.words[0] === "cd" &&
			["&&", ";", "\n"].includes(segment.separator)
		) {
			shellCwd = resolve(shellCwd, segment.words[1]);
		}
	}
	return false;
}

/** True when a mutation would bypass the task worktree boundary. */
function blocksTaskWorktree(event, cwd) {
	if (movesPrimaryBranch(event, cwd)) return true;
	for (const path of mutationPaths(event, cwd)) {
		const state = worktreeState(path, cwd);
		if (
			state &&
			(state.root === state.primaryRoot || state.branch.length === 0)
		) {
			return true;
		}
	}
	return false;
}

/**
 * New trigger ids. `crypto.randomUUID` is a modern Node global with no
 * import; fall back to a counter where the runtime lacks it (defensive, and
 * the only place randomness is needed).
 */
let __fallbackId = 0;
function newTriggerId() {
	if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
		return `dd-${crypto.randomUUID()}`;
	}
	return `dd-fallback-${++__fallbackId}`;
}

/** The `daily-driver` Omp extension factory. */
export default function dailyDriverExtension(pi) {
	const z = pi.zod;

	// Per-session trigger bookkeeping: triggerId -> { ctx, handle }. Managed
	// timers are cleared on session_shutdown by the runtime itself; this map
	// only exists to honour cancel_schedule, forget fired triggers, and be
	// dropped wholesale on shutdown.
	const TRIGGERS = new Map();

	/** Idempotently cancel a live trigger. Clean false otherwise. */
	function cancelTrigger(triggerId) {
		if (typeof triggerId !== "string" || triggerId.length === 0) {
			return false;
		}
		const entry = TRIGGERS.get(triggerId);
		if (!entry) {
			// Unknown, or already fired (firing removed the entry). Either
			// way there is nothing live to cancel — clean false, never throws.
			return false;
		}
		TRIGGERS.delete(triggerId);
		try {
			entry.ctx.clearTimer(entry.handle);
		} catch {
			// The runtime may already have cleared the timer (e.g. shutdown).
			// Nothing left to do; the entry is gone either way.
		}
		return true;
	}

	// Deny preferences and repository boundaries at execution time: unlike an
	// instruction, a blocked call cannot be ignored by a weaker model.
	pi.on("tool_call", (event, ctx) => {
		if (event.toolName === "ask") {
			return { block: true, reason: ASK_BLOCK_REASON };
		}
		try {
			if (blocksTaskWorktree(event, ctx?.cwd)) {
				return { block: true, reason: WORKTREE_BLOCK_REASON };
			}
		} catch (err) {
			if (!(err instanceof GitUnavailableError)) throw err;
			// Say so on stderr as well as to the model: an operator must be able
			// to tell a guarded session from one whose guard cannot run.
			console.error(
				`daily-driver: worktree guard could not run: ${err.message}`,
			);
			return { block: true, reason: GIT_UNAVAILABLE_BLOCK_REASON };
		}
		return undefined;
	});

	pi.registerTool({
		name: "daily_driver_set_session_title",
		label: "Set session title",
		description:
			"Set the title of the current session. Use it to keep the session " +
			"name meaningful while work is under way, so the session list shows " +
			"what this session is for.",
		parameters: z.object({
			title: z.string().describe("The new session title"),
		}),
		execute: async (_toolCallId, params, _signal, _onUpdate, _ctx) => {
			await pi.setSessionName(params.title);
			return {
				content: [{ type: "text", text: `Session titled: ${params.title}` }],
				details: { titled: params.title },
			};
		},
	});

	// The read half of the session surface. Claude Code answers
	// `mcp__Claude_Code_Remote__get_session`; Omp has no such call, and before
	// this tool it had no model-readable route to its own session id at all —
	// which made an undertake claim comment invent "session: unavailable"
	// diagnostics about a surface that does exist. The id lives in the
	// session manager, and the tool `ctx` exposes it read-only.
	pi.registerTool({
		name: "daily_driver_get_session",
		label: "Get session info",
		description:
			"Read this session's own id, name, and model. The id is what an " +
			"undertake claim comment records; the name and model are the " +
			"session's current values.",
		parameters: z.object({}),
		execute: async (_toolCallId, _params, _signal, _onUpdate, ctx) => {
			const model = ctx.model?.id ?? null;
			const info = {
				sessionId: ctx.sessionManager.getSessionId(),
				sessionName: ctx.sessionManager.getSessionName() ?? null,
				model,
			};
			return {
				content: [
					{
						type: "text",
						text: `Session ${info.sessionId}${info.sessionName ? ` (${info.sessionName})` : ""}, model ${model ?? "unknown"}`,
					},
				],
				details: info,
			};
		},
	});

	pi.registerTool({
		name: "daily_driver_schedule",
		label: "Schedule a reminder",
		description:
			"Schedule a reminder in this session, delivered as a follow-up " +
			"message after delaySeconds. Returns a triggerId you can pass to " +
			"daily_driver_cancel_schedule to cancel it before it fires.",
		parameters: z.object({
			delaySeconds: z
				.number()
				.int()
				.min(1)
				.max(86400)
				.describe("Seconds until the reminder fires, 1 to 86400"),
			message: z.string().describe("The reminder text to deliver"),
		}),
		execute: async (_toolCallId, params, _signal, _onUpdate, ctx) => {
			const triggerId = newTriggerId();
			const handle = ctx.setTimeout(
				() => {
					// Firing removes the trigger first so a cancel racing the
					// expiry is a clean false, never a double-send.
					TRIGGERS.delete(triggerId);
					pi.sendMessage(
						{
							customType: REMINDER_CUSTOM_TYPE,
							content: params.message,
							display: true,
							// User-attributed, the way the operator would have
							// typed it, rather than a tool the model ran.
							attribution: "user",
						},
						{ deliverAs: "followUp" },
					);
				},
				params.delaySeconds * 1000,
			);
			TRIGGERS.set(triggerId, { ctx, handle });
			return {
				content: [
					{
						type: "text",
						text: `Scheduled in ${params.delaySeconds}s as ${triggerId}`,
					},
				],
				details: { triggerId },
			};
		},
	});

	pi.registerTool({
		name: "daily_driver_cancel_schedule",
		label: "Cancel a scheduled reminder",
		description:
			"Idempotently cancel a reminder previously returned by " +
			"daily_driver_schedule. Returns whether a live trigger was " +
			"cancelled.",
		parameters: z.object({
			triggerId: z.string().describe("The triggerId to cancel"),
		}),
		execute: async (_toolCallId, params, _signal, _onUpdate, _ctx) => {
			const cancelled = cancelTrigger(params.triggerId);
			return {
				content: [
					{
						type: "text",
						text: cancelled
							? `Cancelled trigger ${params.triggerId}`
							: `No live trigger ${params.triggerId} to cancel`,
					},
				],
				details: { cancelled },
			};
		},
	});

	// Managed timers are cleared automatically on shutdown by the runtime;
	// this just forgets our per-trigger bookkeeping so nothing stale survives.
	pi.on("session_shutdown", () => {
		TRIGGERS.clear();
	});
}