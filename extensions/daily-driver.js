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
 * 2. Block direct file mutations and the Git commands that rewrite a
 *    repository's primary working tree, plus file mutations in a detached
 *    worktree. The model-directed `task-worktree` workflow still chooses the
 *    task identity and establishes or reuses its dedicated worktree; this
 *    guard makes forgetting it fail before the user's checkout is changed.
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
	"Direct `write` and `edit` calls are blocked in the primary checkout and " +
	"in detached worktrees, and so is every Git command that rewrites the " +
	"primary " +
	"checkout's working tree \u2014 `checkout`, `switch`, `reset --hard`, " +
	"`restore`, `stash`, `merge`, `rebase`, `pull`, `apply`, `am`, " +
	"`cherry-pick`, `revert` and `clean` among them. Do not retry the " +
	"mutation there. Invoke the `task-worktree` skill, establish the task's " +
	"feature branch in its dedicated worktree (attaching this worktree in " +
	"place when it is already dedicated), and repeat the operation with its " +
	"path rooted there.";

/** What a mutation whose repository could not be located is told. */
export const UNANCHORED_PATH_BLOCK_REASON =
	"This operation could not be placed in a repository, so it cannot be " +
	"checked against the task worktree boundary. It is refused rather than " +
	"allowed unchecked: a relative path arrived with no working directory to " +
	"read it against. Repeat the operation with an absolute path, or from a " +
	"working directory, rooted in the task worktree.";

/** What a command the guard could not read is told. */
export const UNREADABLE_COMMAND_BLOCK_REASON =
	"This command could not be read well enough to tell whether it changes " +
	"the primary checkout, so it is refused rather than allowed unchecked. " +
	"The guard enumerates the commands a shell call will run; a command it " +
	"cannot enumerate is refused wherever it might be running in the primary " +
	"checkout. Repeat the operation written literally \u2014 no `eval`, no " +
	"executable named by a variable, no unterminated quote \u2014 from a " +
	"working directory rooted in the task worktree.";

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
 * A command whose executed commands the guard could not enumerate: an
 * executable that expands, a string run by `eval`, an unterminated quote. It
 * is the inversion's error — the guard refuses what it cannot read, rather
 * than allowing what it did not recognize as dangerous.
 */
class UnreadableCommandError extends Error {
	/** @param {string} message Why the command could not be read. */
	constructor(message) {
		super(message);
		this.name = "UnreadableCommandError";
	}
}

/**
 * A path the guard cannot place in any repository: a relative path with no
 * working directory to read it against. Distinct from a path Git places
 * outside every worktree, which is an answer the guard can act on.
 */
class UnanchoredPathError extends Error {
	/** @param {string} message Which operation could not be placed. */
	constructor(message) {
		super(message);
		this.name = "UnanchoredPathError";
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
 * tell which repository such a path names, and a guess would be worse than no
 * answer. An absolute path needs no anchor and is always usable.
 */
function anchoredPath(cwd, path) {
	if (isAbsolute(path)) return path;
	return typeof cwd === "string" && cwd.length > 0 ? resolve(cwd, path) : null;
}

/**
 * Resolve one path against a Git working directory that may itself be
 * unknown. An absolute path needs no base; a relative one without a base
 * cannot be placed, and null says so.
 */
function resolveAgainst(base, value) {
	if (isAbsolute(value)) return resolve(value);
	return base === null ? null : resolve(base, value);
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
	// An unplaceable path is refused rather than allowed unchecked, the way an
	// unanswerable Git query is.
	if (target === null) {
		throw new UnanchoredPathError(
			`the relative path ${path} arrived with no working directory`,
		);
	}
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
	// missing, the mutation cannot be placed in any repository, so it is
	// refused rather than allowed unchecked — the same answer an unplaceable
	// relative path gets.
	if (paths.length > 0) return [...new Set(paths)];
	if (typeof cwd === "string" && cwd.length > 0) return [cwd];
	throw new UnanchoredPathError(
		`a ${event.toolName} names no path, and there is no working directory`,
	);
}

/**
 * Advance past the here-document bodies owed by one command line. Returns the
 * index of the first character after the last body, so the caller resumes
 * tokenizing the next command rather than the text being written.
 *
 * A delimiter whose line never arrives means the operator was not a
 * here-document after all. The start index is returned in that case, so the
 * remaining lines are scanned as commands rather than swallowed as a body.
 */
function skipHeredocBodies(command, start, heredocs) {
	let position = start;
	for (const { delimiter, stripTabs } of heredocs) {
		let terminated = false;
		while (position < command.length) {
			const newline = command.indexOf("\n", position);
			const end = newline < 0 ? command.length : newline;
			const line = command.slice(position, end);
			position = Math.min(end + 1, command.length);
			if ((stripTabs ? line.replace(/^\t+/u, "") : line) === delimiter) {
				terminated = true;
				break;
			}
		}
		if (!terminated) return start;
	}
	return position;
}

/**
 * True where `(` at `index` opens a function definition's empty parameter
 * list — `name ()` or `function name ()` — rather than a subshell. What
 * follows such a header is a body that is stored, not run.
 */
function opensFunctionDefinition(words, wordStarted, command, index) {
	const count = words.length + (wordStarted ? 1 : 0);
	if (count !== 1 && !(count === 2 && words[0].text === "function")) {
		return false;
	}
	return /^\s*\)/u.test(command.slice(index + 1, index + 64));
}

/**
 * Keywords that introduce a command rather than being one. Stripping them
 * leaves the command they govern visible: without this, `if git switch master`
 * reads as a call to `if` and the branch move behind it is never examined.
 */
const CONTROL_KEYWORDS = new Set([
	"!",
	"case",
	"do",
	"done",
	"elif",
	"else",
	"esac",
	"fi",
	"if",
	"select",
	"then",
	"time",
	"until",
	"while",
]);

/**
 * One word of a command, and whether its text is the whole story. A word is
 * literal when nothing in it expands: no `$`, no backtick, no glob, no leading
 * `~`. Only a literal word may be read as a path, an executable name, or a Git
 * subcommand; anything else is a value the guard cannot know, and the caller
 * refuses rather than guesses.
 */
function shellWord(text, literal) {
	return { text, literal };
}

/**
 * Split a literal shell command into executable segments.
 *
 * The recognizer's contract is that it either enumerates every command the
 * shell will run, or says it could not. Command substitutions, arithmetic,
 * process substitutions and subshells are all parenthesized, so they are all
 * emitted as groups and their contents tokenized like any other command: a
 * `cd` inside one is seen, and stops applying where the group closes. Nothing
 * is treated as opaque text, because opaque text is where a command hides.
 *
 * A segment carries the words of one command and the separator that ended it.
 * A group emits a wordless `open` or `close` marker instead, which is how a
 * caller tracking the working directory learns where a `cd` stops applying.
 *
 * Returns the segments, the names of any functions defined along the way, and
 * `unreadable`: a reason string where the scan could not be completed, which
 * the caller must treat as a refusal rather than as an empty command.
 */
function shellSegments(command) {
	const segments = [];
	const functions = [];
	let words = [];
	let word = "";
	let wordStarted = false;
	let wordLiteral = true;
	let quote = null;
	let backtick = false;
	let heredocWord = false;
	let heredocStripTabs = false;
	let awaitingHeredocDelimiter = false;
	const pendingHeredocs = [];
	// A `{` that follows a function header opens a body that is stored rather
	// than run. The stack remembers which open brace is such a body, so the
	// matching `}` closes the right one. An unclosed body leaves the stack
	// short, which needs no handling: bash rejects it as a syntax error, so
	// nothing in it runs.
	let pendingFunctionBody = false;
	const braceStack = [];
	// What each open paren opened. Arithmetic holds no commands, so the caller
	// must not read its words as one.
	const groupKinds = [];
	// A substitution may open inside a double-quoted string — `"$(…)"` — and the
	// string resumes where it closes. The quote in force is stacked with the
	// group so the text after the `)` is still read as quoted.
	const quoteStack = [];
	// The word a substitution opened inside, set aside until it closes.
	const wordStateStack = [];
	let depth = 0;

	const finishWord = () => {
		if (!wordStarted) return;
		if (awaitingHeredocDelimiter) {
			pendingHeredocs.push({ delimiter: word, stripTabs: heredocStripTabs });
			awaitingHeredocDelimiter = false;
		} else if (heredocWord) {
			// The operator may carry a file descriptor: `2<<EOF` names EOF too.
			const rest = word.slice(word.indexOf("<<") + 2);
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
		words.push(shellWord(word, wordLiteral));
		word = "";
		wordStarted = false;
		wordLiteral = true;
	};
	const openGroup = (kind, separator, inWord = wordStarted) => {
		// A substitution is a word of the command carrying it — `git -C "$(…)"
		// switch` — never the end of that command. Ending it here would split
		// `git -C` away from `switch` and leave both halves unrecognizable, so
		// the enclosing word is set aside and resumed when the group closes,
		// whether or not any of it had been typed yet. Only a `(` standing where
		// a command starts is a subshell, and that one does end the command
		// before it.
		if (inWord) {
			wordStateStack.push({ words, word, wordLiteral });
			words = [];
			word = "";
			wordStarted = false;
			wordLiteral = true;
		} else {
			finishSegment(separator);
			wordStateStack.push(null);
		}
		segments.push({
			words: [],
			separator: null,
			group: "open",
			arithmetic: kind === "arithmetic",
		});
		groupKinds.push(kind);
		quoteStack.push(quote);
		quote = null;
		depth += kind === "arithmetic" ? 2 : 1;
	};
	const closeGroup = (separator) => {
		finishSegment(separator);
		segments.push({ words: [], separator: null, group: "close" });
		const kind = groupKinds.pop();
		quote = quoteStack.length > 0 ? quoteStack.pop() : null;
		depth -= kind === "arithmetic" ? 2 : 1;
		const enclosing = wordStateStack.pop();
		if (enclosing) {
			words = enclosing.words;
			word = enclosing.word;
			wordStarted = true;
			// Whatever the substitution produced, the word is no longer the
			// guard's to read.
			wordLiteral = false;
		} else {
			wordLiteral = true;
		}
	};
	const finishSegment = (separator) => {
		finishWord();
		// `{` and `}` group commands; neither is part of the command itself. A
		// brace group holding a function body is emitted as a group instead, so a
		// `cd` stored in it never moves the shell that defines the function.
		const closers = [];
		while (words[0]?.text === "{") {
			words.shift();
			const storedBody = pendingFunctionBody;
			pendingFunctionBody = false;
			braceStack.push(storedBody);
			if (storedBody) {
				segments.push({ words: [], separator: null, group: "open" });
			}
		}
		while (words.at(-1)?.text === "}") {
			words.pop();
			if (braceStack.pop()) {
				closers.push({ words: [], separator: null, group: "close" });
			}
		}
		while (words[0]?.literal && CONTROL_KEYWORDS.has(words[0].text)) {
			words.shift();
		}
		if (words.length > 0) segments.push({ words, separator });
		segments.push(...closers);
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
				// A backslash-newline is a line continuation: it joins the lines
				// and contributes no character to the word.
				if (next !== "\n") {
					word += next;
					wordStarted = true;
				}
				index++;
			}
			continue;
		}
		if (quote === '"') {
			if (char === "$" && command[index + 1] === "(") {
				// A substitution inside a quoted string is still a substitution:
				// leaving it as word text is how `"$(git switch …)"` walked past
				// the guard while the backtick spelling of it did not.
				wordLiteral = false;
				const arithmetic = command[index + 2] === "(";
				openGroup(arithmetic ? "arithmetic" : "command", "(");
				index += arithmetic ? 2 : 1;
				continue;
			}
			if (char === '"') quote = null;
			else if (char === "$" || char === "`") wordLiteral = false;
			if (char !== '"' && char !== "`") word += char;
			wordStarted = true;
			if (char !== "`") continue;
		} else if (char === "'" || char === '"') {
			quote = char;
			wordStarted = true;
			continue;
		}
		if (char === "`") {
			// A backtick substitution runs commands in a subshell, exactly as
			// `$(…)` does. It is emitted as a group so its `cd` cannot leak out.
			if (backtick) closeGroup(null);
			// A backtick opens a word even where none has been typed: after
			// `git -C ` the word is empty, and treating that as a command
			// boundary hid the `switch` that followed the closing backtick.
			else openGroup("command", null, true);
			backtick = !backtick;
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
		if (char === "(" && command[index + 1] === "(") {
			// `((…))` evaluates arithmetic and `$((…))` expands it. Neither runs
			// the words inside as a command, but either may hold a `$(…)` that
			// does, so the span is tokenized like any other group and marked as
			// arithmetic for the caller.
			openGroup("arithmetic", "(");
			index++;
			continue;
		}
		if (
			char === ")" &&
			command[index + 1] === ")" &&
			groupKinds.at(-1) === "arithmetic"
		) {
			closeGroup(")");
			index++;
			continue;
		}
		if (char === "(" || char === ")") {
			if (
				char === "(" &&
				opensFunctionDefinition(words, wordStarted, command, index)
			) {
				pendingFunctionBody = true;
				// The name is the word the header just ended on, which may still
				// be the one being accumulated.
				if (wordStarted) {
					if (wordLiteral) functions.push(word);
				} else if (words.at(-1)?.literal) {
					functions.push(words.at(-1).text);
				}
				// A definition header is not a call to the function it names.
				// Emitting it as one would make every definition look like an
				// invocation of its own body.
				words = [];
				word = "";
				wordStarted = false;
				wordLiteral = true;
			} else if (char === "(") {
				// Any other `(` opens something that runs in a subshell of its
				// own — a command substitution, arithmetic, a process
				// substitution, a plain subshell, or a function body written as
				// one. None of them is a stored brace body.
				pendingFunctionBody = false;
			}
			if (char === "(") openGroup("command", char);
			else closeGroup(char);
			continue;
		}
		if (char === ";" || char === "&" || char === "|") {
			const doubled = command[index + 1] === char;
			finishSegment(doubled ? char + char : char);
			if (doubled) index++;
			continue;
		}
		if (char === "$" || char === "*" || char === "?") wordLiteral = false;
		if (char === "~" && !wordStarted) wordLiteral = false;
		word += char;
		wordStarted = true;
		// `<<` outside quotes opens a here-document, with an optional file
		// descriptor in front of it; `<<<` is a here-string and has no body.
		// Only an unquoted operator counts, so `echo "<<EOF"` is the prose it
		// looks like.
		if (char === "<") heredocWord = /^\d*<<$/u.test(word);
	}
	finishSegment(null);

	let unreadable = null;
	if (quote !== null || quoteStack.some((held) => held !== null)) {
		unreadable = "a quote is never closed";
	}
	else if (backtick) unreadable = "a backtick substitution is never closed";
	else if (depth > 0) unreadable = "a parenthesis is never closed";
	return { segments, functions, unreadable };
}

function isEnvironmentAssignment(word) {
	return /^[A-Za-z_][A-Za-z0-9_]*=/u.test(word.text);
}

/**
 * Every position where a literal `git` executable could stand in one command's
 * words.
 *
 * The search is positional rather than a list of known wrappers, so `xargs git
 * switch`, `timeout 5 git switch` and `sudo -u x git switch` are all found
 * without the guard having to have met the wrapper before. A word it cannot
 * read does not stop the scan: `env -u NOPE* git switch` runs git whatever the
 * unreadable word turns out to be. Nor does an earlier `git` that turns out to
 * be an argument — `find . -name git -exec git -C <primary> switch \\;` runs the
 * second one, so each candidate is read in turn.
 */
function gitWordIndices(words) {
	const found = [];
	for (let index = 0; index < words.length; index++) {
		if (words[index].literal && basename(words[index].text) === "git") {
			found.push(index);
		}
	}
	return found;
}

/**
 * Read one environment assignment that precedes the Git executable. A shell
 * exports the last assignment of a name, so the scan runs right to left. A
 * non-literal value is reported as such, because a selector whose value the
 * guard cannot read must not be resolved as if it were a path.
 */
function environmentValue(words, end, name) {
	const prefix = `${name}=`;
	for (let index = end - 1; index >= 0; index--) {
		if (words[index].text.startsWith(prefix)) {
			return words[index].literal
				? words[index].text.slice(prefix.length)
				: UNREADABLE;
		}
	}
	return null;
}

/** A selector whose value the guard cannot read. Distinct from absent. */
const UNREADABLE = Symbol("unreadable");

/**
 * Resolve one path selector against the Git working directory. Null stays
 * null; an unreadable selector and a relative selector with no working
 * directory to read it against both resolve to null, which the caller treats
 * as a repository it could not place.
 */
function selectedPath(gitCwd, value) {
	if (value === null) return null;
	if (value === UNREADABLE) return UNREADABLE;
	return resolveAgainst(gitCwd, value);
}

/**
 * Config names that can rename a subcommand: an alias directly, and an
 * include that can carry one in another file.
 */
const RENAMES_SUBCOMMANDS = /^(alias\.|include\.path|includeIf\.)/iu;

/**
 * True where one `-c`/`--config-env` setting may rename the subcommand that
 * follows it.
 *
 * A literal setting is read: `git -c core.pager=less log` names `core.pager`,
 * which renames nothing. Anything else is not read at all, because a word's
 * text is not the word Git will see — the tokenizer pulls a substitution out
 * of it, so `"$(echo alias.q)=switch"` arrives here as `=switch` and any test
 * on that text answers about a name that was never there. That is the hole
 * the first attempt at this left open, and inspecting the text more closely
 * would not have closed it.
 *
 * Refusing an unreadable setting costs little, because it is not refused
 * everywhere: the caller marks the invocation as a working-tree rewrite and
 * the ordinary placement decides. `git -c core.pager="$PAGER" log` runs in a
 * task worktree and outside Git; in the primary checkout it is refused, which
 * is where the guard is meant to be an obstacle.
 */
function mayRenameSubcommand(word) {
	if (!word.literal) return true;
	return RENAMES_SUBCOMMANDS.test(word.text.split("=")[0]);
}

/**
 * The config setting one word carries, in any of the four spellings Git takes
 * it in — `-c x=y`, `-cx=y`, `--config-env x=y`, `--config-env=x=y` — or null
 * where the word carries none. `consumed` says how many further words the
 * spelling took.
 */
function configSetting(word, literal, words, index) {
	if (["-c", "--config-env"].includes(word)) {
		const next = words[index + 1];
		return next === undefined ? null : { word: next, consumed: 1 };
	}
	if (word.startsWith("--config-env=")) {
		return {
			word: { text: word.slice("--config-env=".length), literal },
			consumed: 0,
		};
	}
	if (word.startsWith("-c") && word.length > 2 && !word.startsWith("-c=")) {
		return { word: { text: word.slice(2), literal }, consumed: 0 };
	}
	return null;
}

/** An invocation whose subcommand the guard could not read. */
function unreadableInvocation(
	gitCwd,
	gitDir,
	workTree,
	environmentGitDir,
	environmentWorkTree,
) {
	return {
		subcommand: UNREADABLE,
		unreadable: true,
		args: [],
		cwd: gitCwd,
		gitDir: selectedPath(gitCwd, gitDir ?? environmentGitDir),
		workTree: selectedPath(gitCwd, workTree ?? environmentWorkTree),
	};
}

/**
 * Resolve one Git invocation's subcommand and repository selectors, reading
 * the subcommand word as it stands. `gitInvocation` is what callers want: it
 * resolves a subcommand that turns out to be a configured alias as well.
 */
function parseGitInvocation(words, shellCwd, start) {
	let index = start;
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
	// Set by a `-c`/`--config-env` setting that may rename the subcommand, so
	// the word read as the subcommand below may be an alias for a guarded one.
	let mayRename = false;
	index++;
	for (; index < words.length; index++) {
		const { text: word, literal } = words[index];
		const value = (raw, isLiteral) => (isLiteral ? raw : UNREADABLE);
		if (word === "-C" && words[index + 1] !== undefined) {
			const next = words[++index];
			gitCwd = next.literal ? resolveAgainst(gitCwd, next.text) : null;
			continue;
		}
		if (word.startsWith("-C") && word.length > 2) {
			gitCwd = literal ? resolveAgainst(gitCwd, word.slice(2)) : null;
			continue;
		}
		if (word === "--work-tree" && words[index + 1] !== undefined) {
			const next = words[++index];
			workTree = value(next.text, next.literal);
			continue;
		}
		if (word.startsWith("--work-tree=")) {
			workTree = value(word.slice("--work-tree=".length), literal);
			continue;
		}
		if (word === "--git-dir" && words[index + 1] !== undefined) {
			const next = words[++index];
			gitDir = value(next.text, next.literal);
			continue;
		}
		if (word.startsWith("--git-dir=")) {
			gitDir = value(word.slice("--git-dir=".length), literal);
			continue;
		}
		// An alias renames a subcommand, so a command that sets one on its own
		// line carries a subcommand this recognizer cannot read: `git -c
		// alias.q=switch q` is `git switch`. Every spelling of the two flags
		// that carry a setting is read for that, attached and separate alike.
		const setting = configSetting(word, literal, words, index);
		if (setting !== null) {
			index += setting.consumed;
			if (mayRenameSubcommand(setting.word)) mayRename = true;
			continue;
		}
		if (["--exec-path", "--namespace"].includes(word)) {
			index++;
			continue;
		}
		if (!literal) {
			// It could be an option, and `-C <primary>` is an option. Whether
			// this word is a flag or the subcommand cannot be told apart, so
			// neither is assumed.
			return unreadableInvocation(gitCwd, gitDir, workTree, environmentGitDir, environmentWorkTree);
		}
		if (word.startsWith("-")) continue;
		return {
			subcommand: word,
			unreadable: false,
			mayRename,
			args: words.slice(index + 1),
			cwd: gitCwd,
			gitDir: selectedPath(gitCwd, gitDir ?? environmentGitDir),
			workTree: selectedPath(gitCwd, workTree ?? environmentWorkTree),
		};
	}
	// `git` with no subcommand at all moves nothing.
	return null;
}

/**
 * How many alias expansions the resolver follows before it gives up. An alias
 * may name another alias, and Git expands the chain; a chain longer than this
 * is a loop or an abuse, and is refused rather than followed.
 */
const ALIAS_EXPANSION_LIMIT = 10;

/**
 * True where the recognizer already places this subcommand, in either set.
 *
 * It is also the word that can never be an alias: Git ignores an alias that
 * hides an existing command, so a guarded word always means the command it
 * names. Asking Git about one would cost a lookup to learn nothing.
 */
function recognizedSubcommand(word) {
	return REWRITES_ALWAYS.has(word) || REWRITE_FORM.has(word);
}

/**
 * The configured expansion of one alias, or null where the word names none.
 *
 * The lookup runs in the invocation's own directory where it has one, because
 * that is the repository whose config Git would read. A config read Git cannot answer at
 * all is a `GitUnavailableError` from `gitOutput`, not an absent alias: the
 * guard must not fail open on a Git it could not consult.
 *
 * One `git config` lookup was measured at about 3ms in a container running
 * this repository, and it is spent once per unrecognized subcommand — `git
 * status`, `git log`, `git diff` — rather than on every Git word. That is the
 * price of reading `git co` as the `git checkout` it is.
 *
 * A directory that does not exist is no alias: Git would fail to start there,
 * so the command the guard is reading rewrites nothing.
 */
function aliasExpansion(cwd, word) {
	const anchor = existingDirectory(cwd);
	if (anchor === null) return null;
	return gitOutput(anchor, "config", "--get", `alias.${word}`);
}

/**
 * Split an alias expansion into words the way Git does, or null where the
 * guard cannot read it.
 *
 * Null covers the two unreadable cases: a `!` expansion, which Git hands to a
 * shell rather than to itself, and an unbalanced quote, which Git rejects
 * outright. Everything else is plain text from the config file, so every word
 * it yields is literal — Git performs no expansion of its own on it.
 */
function splitAliasExpansion(text) {
	if (text.startsWith("!")) return null;
	const words = [];
	let word = "";
	let started = false;
	let quote = null;
	for (let index = 0; index < text.length; index++) {
		const character = text[index];
		if (quote === null && /\s/u.test(character)) {
			if (started) words.push(word);
			word = "";
			started = false;
			continue;
		}
		started = true;
		if (character === "\\" && quote !== "'") {
			if (++index >= text.length) return null;
			word += text[index];
			continue;
		}
		if (quote === null && (character === "'" || character === '"')) {
			quote = character;
			continue;
		}
		if (character === quote) {
			quote = null;
			continue;
		}
		word += character;
	}
	if (quote !== null) return null;
	if (started) words.push(word);
	return words;
}

/**
 * An invocation whose subcommand may stand for a guarded one, marked the way
 * an unreadable `-c` setting is: the word decides nothing, so the ordinary
 * placement decides instead. Refusing it everywhere would deny `git lg` in a
 * task worktree, where the guard has no business refusing anything.
 */
function renamingInvocation(invocation) {
	return { ...invocation, mayRename: true };
}

/**
 * Resolve one Git invocation, reading a subcommand that is a configured alias
 * as the command it expands to.
 *
 * An alias makes the subcommand word arbitrary, so matching the literal word
 * leaves every guarded command a spelling that walks through unseen: `git co
 * master` is `git checkout master` to Git and an unrecognized word to a guard
 * that only reads the word. The expansion is re-parsed as a whole invocation
 * rather than read for its first word, because it can carry options of its
 * own — `alias.co = -C /elsewhere checkout` selects another repository, and
 * `alias.x = -c alias.y=switch y` renames again.
 *
 * Two cases cannot be resolved and are marked as renaming rather than
 * answered: an expansion Git hands to a shell, and a chain longer than the
 * limit. A third has no lookup to make at all — an invocation whose own
 * directory expanded, and a shell whose directory the walker lost — and the
 * fallback is the directory the tool was called in, which is the repository
 * whose config the aliases almost certainly come from. With no directory
 * anywhere the word stands unresolved: the guard cannot place such a command
 * either way, and a rewrite it does recognize is already refused as
 * unanchored.
 */
function gitInvocation(words, shellCwd, start, toolCwd) {
	let invocation = parseGitInvocation(words, shellCwd, start);
	for (let expansions = 0; ; expansions++) {
		if (invocation === null || invocation.unreadable || invocation.mayRename) {
			return invocation;
		}
		if (recognizedSubcommand(invocation.subcommand)) return invocation;
		const lookupCwd = invocation.cwd ?? toolCwd ?? null;
		if (lookupCwd === null) return invocation;
		if (expansions >= ALIAS_EXPANSION_LIMIT) return renamingInvocation(invocation);
		const expansion = aliasExpansion(lookupCwd, invocation.subcommand);
		if (expansion === null) return invocation;
		const expanded = splitAliasExpansion(expansion);
		if (expanded === null) return renamingInvocation(invocation);
		const next = parseGitInvocation(
			[
				shellWord("git", true),
				...expanded.map((text) => shellWord(text, true)),
				...invocation.args,
			],
			invocation.cwd,
			0,
		);
		// The expansion is read against the invocation's own directory, which
		// may be unknown; the lookup directory stands in for the config, never
		// for the place the command runs.
		// An alias of options alone — `alias.p = -p` — runs no subcommand, so
		// it moves nothing, and an expansion that selects no repository leaves
		// the selectors the original invocation carried in force.
		if (next === null) return null;
		invocation = {
			...next,
			gitDir: next.gitDir ?? invocation.gitDir,
			workTree: next.workTree ?? invocation.workTree,
		};
	}
}

/**
 * Git subcommands that rewrite tracked files in the primary working tree in
 * every form they take, so no argument reading places them.
 *
 * The test is whether the command rewrites tracked files in the working tree,
 * not whether it moves HEAD: that is what puts `merge` and `rebase` here
 * beside `switch`, and what #289 recorded after the first guard recognized
 * only the two commands #269 named. `git merge --quit` and `git rebase --quit`
 * do leave the working tree alone, and are denied with the rest: an
 * exhaustively enumerated harmless form nobody runs buys a reader two more
 * branches to check.
 */
const REWRITES_ALWAYS = new Set([
	"am",
	"cherry-pick",
	"merge",
	"pull",
	"rebase",
	"revert",
	"switch",
]);

/**
 * Forms of `checkout` and `switch` that overwrite the working tree instead of
 * attaching it: the force spellings, and `--detach`, which is the opposite of
 * the attach the exemption exists for.
 */
const ATTACH_OVERWRITES = new Set([
	"--detach",
	"--discard-changes",
	"--force",
	"-f",
]);

/**
 * True where this invocation is the in-place attach `WORKTREE_BLOCK_REASON`
 * prescribes, which is the only thing a detached primary is exempt for.
 *
 * The test is on the form, not on the subcommand: `git checkout -- a.txt` and
 * `git switch --discard-changes master` are a `checkout` and a `switch` that
 * attach nothing and destroy the checkout's uncommitted work, so exempting
 * them would reopen inside a detached primary exactly the inconsistency #289
 * closed in an attached one.
 *
 * `switch` never takes a pathspec, so any non-forcing form of it attaches.
 * `checkout` does, and a bare operand is a branch name or a path with nothing
 * in the text to tell them apart — so only the explicit branch-creating forms
 * qualify, and `git checkout master` inside a detached primary is refused in
 * favour of the `git switch master` that says the same thing unambiguously.
 */
function attachesBranch(invocation) {
	const { subcommand, args } = invocation;
	if (subcommand !== "switch" && subcommand !== "checkout") return false;
	if (args.some((arg) => !arg.literal)) return false;
	const words = args.map((arg) => arg.text);
	if (
		words.some(
			(word) =>
				ATTACH_OVERWRITES.has(word) ||
				(shortBundle(word) && word.includes("f")),
		)
	) {
		return false;
	}
	if (subcommand === "switch") return true;
	return words.includes("-b") || words.includes("-B");
}

/**
 * One command's option words, ending where `--` ends them. After the
 * separator every word is an operand, whatever it starts with, so a file
 * called `-hard` is never read as `--hard`'s neighbour.
 */
function optionWords(args) {
	const options = [];
	for (const arg of args) {
		if (arg === "--") break;
		if (arg.startsWith("-") && arg !== "-") options.push(arg);
	}
	return options;
}

/** A bundle of single-letter options, which `-SW` and `-fd` both are. */
function shortBundle(option) {
	return /^-[A-Za-z]+$/u.test(option);
}

/**
 * `git reset` touches the working tree in `--hard`, `--merge` and `--keep`,
 * and only there. The safe forms are enumerated rather than the destructive
 * ones, so a form this guard has never met — a new mode, a misread bundle —
 * lands on the destructive side.
 */
const RESET_KEEPS_WORKTREE = new Set([
	"--mixed",
	"--patch",
	"--quiet",
	"--soft",
	"-p",
	"-q",
]);

function resetRewrites(args) {
	return !optionWords(args).every((option) =>
		RESET_KEEPS_WORKTREE.has(option),
	);
}

/**
 * `git restore` writes the working tree unless `--staged` is given alone:
 * `--staged --worktree` writes both. Those two flags decide it between them,
 * so an option the guard has not met cannot change the answer and is not made
 * to.
 */
function restoreRewrites(args) {
	let staged = false;
	let worktree = false;
	for (const option of optionWords(args)) {
		if (option === "--staged") staged = true;
		else if (option === "--worktree") worktree = true;
		else if (shortBundle(option)) {
			if (option.includes("S")) staged = true;
			if (option.includes("W")) worktree = true;
		}
	}
	return !staged || worktree;
}

/** `git apply` forms that inspect the patch or the index and write no file. */
const APPLY_READS_ONLY = new Set([
	"--check",
	"--numstat",
	"--stat",
	"--summary",
]);

function applyRewrites(args) {
	const options = optionWords(args);
	if (options.some((option) => APPLY_READS_ONLY.has(option))) return false;
	// `--cached` applies to the index alone; `--index` applies to both, and
	// Git refuses the two together.
	return !(options.includes("--cached") && !options.includes("--index"));
}

/**
 * `git clean` deletes untracked files rather than rewriting tracked ones, so
 * it fails the letter of the test above and meets its reason exactly: it
 * destroys uncommitted work in the checkout this guard exists to protect.
 * `-n` and `--dry-run` only report.
 */
function cleanRewrites(args) {
	return !optionWords(args).some(
		(option) =>
			option === "--dry-run" || (shortBundle(option) && option.includes("n")),
	);
}

/**
 * `git checkout` with any operand at all writes the working tree: a branch
 * name moves HEAD and the files with it, and a pathspec overwrites the files
 * named. The pathspec form was allowed until #289, which is the boundary that
 * issue called inconsistent — `git checkout -- a.txt` is `git restore a.txt`
 * spelled the old way, and denying one while allowing the other says nothing
 * a reader can act on. Bare `git checkout` reports and changes nothing.
 */
function checkoutRewrites(args) {
	return args.length > 0;
}

/**
 * `git rm` deletes tracked files from the working tree and `git mv` renames
 * them in place. Both are everyday porcelain, and both spend the user's
 * uncommitted work. `--cached` keeps `rm` to the index; `-n` and `--dry-run`
 * report and write nothing.
 */
function reportsOnly(args) {
	return optionWords(args).some(
		(option) =>
			option === "--dry-run" || (shortBundle(option) && option.includes("n")),
	);
}

function rmRewrites(args) {
	return !(optionWords(args).includes("--cached") || reportsOnly(args));
}

function mvRewrites(args) {
	return !reportsOnly(args);
}

/**
 * A subcommand-shaped command: the first operand names the verb, and the
 * verbs that leave the working tree alone are the ones enumerated. A verb the
 * guard has never met, and a command with no verb at all, are destructive.
 */
function verbRewrites(readOnly) {
	return (args) => {
		for (const arg of args) {
			if (arg === "--") continue;
			if (arg.startsWith("-") && arg !== "-") continue;
			return !readOnly.has(arg);
		}
		return true;
	};
}

/**
 * The `git stash` verbs that leave the working tree alone. Everything else
 * writes it — `pop` and `apply` restore files, `push` and `save` remove them,
 * `branch` checks one out, and a bare `git stash` is `push`.
 */
const STASH_READS_ONLY = new Set([
	"clear",
	"create",
	"drop",
	"list",
	"show",
	"store",
]);

/**
 * `git bisect start`, `good`, `bad`, `run`, `reset`, `replay` and `skip` all
 * check a commit out; the reporting verbs do not.
 */
const BISECT_READS_ONLY = new Set(["log", "terms", "view", "visualize"]);

/** `git sparse-checkout set` and friends add and remove working-tree files. */
const SPARSE_CHECKOUT_READS_ONLY = new Set(["list"]);

/**
 * `git submodule update`, `deinit` and `foreach` all write working trees
 * nested inside this one. `init` and the reporting verbs write config or
 * nothing.
 */
const SUBMODULE_READS_ONLY = new Set(["init", "status", "summary"]);

/** Subcommands destructive in one form and harmless in another. */
const REWRITE_FORM = new Map([
	["apply", applyRewrites],
	["bisect", verbRewrites(BISECT_READS_ONLY)],
	["checkout", checkoutRewrites],
	["clean", cleanRewrites],
	["mv", mvRewrites],
	["reset", resetRewrites],
	["restore", restoreRewrites],
	["rm", rmRewrites],
	["sparse-checkout", verbRewrites(SPARSE_CHECKOUT_READS_ONLY)],
	["stash", verbRewrites(STASH_READS_ONLY)],
	["submodule", verbRewrites(SUBMODULE_READS_ONLY)],
]);

/**
 * True where this Git invocation would rewrite the working tree it runs in.
 *
 * The recognizer fails closed twice over: a subcommand it could not read is
 * destructive, and so is a recognized subcommand carrying a word it could not
 * read — `git reset "$mode"` may be `--hard`. A subcommand outside both sets
 * is not a guess that it is safe: it is the statement that no form of it
 * writes the working tree, which is why each one is enumerated from the
 * manual rather than assumed.
 */
function rewritesWorkingTree(invocation) {
	if (invocation.subcommand === UNREADABLE) return true;
	// A setting the guard could not read, or an alias it could not resolve,
	// may have renamed a guarded subcommand into the word it just read, so
	// the word decides nothing.
	if (invocation.mayRename) return true;
	if (REWRITES_ALWAYS.has(invocation.subcommand)) return true;
	const form = REWRITE_FORM.get(invocation.subcommand);
	if (form === undefined) return false;
	if (invocation.args.some((arg) => !arg.literal)) return true;
	return form(invocation.args.map((arg) => arg.text));
}

/**
 * True where a working-tree rewrite would change a guarded primary checkout.
 * An attached primary is always guarded. A detached primary is exempt in one
 * case only: a command that attaches a branch, operating from inside it.
 * `WORKTREE_BLOCK_REASON` prescribes attaching such a worktree in place, so
 * denying that attach would leave the model nothing to do. Reaching a detached
 * primary from another worktree is not that attach, and neither is a `git
 * reset --hard`, a `git checkout -- a.txt` or a `git switch
 * --discard-changes` run inside one: the exemption is for the attach, so
 * `attachesBranch` decides it on the invocation's form rather than on its
 * subcommand.
 */
function movesGuardedPrimary(state, shellCwd, attaches) {
	if (state === null || state.root !== state.primaryRoot) return false;
	if (state.branch.length > 0) return true;
	if (!attaches) return true;
	const from = worktreeState(".", shellCwd);
	return from === null || from.root !== state.primaryRoot;
}

/**
 * Commands that run a string the guard has not read. Where the string is one
 * literal word it is tokenized like any other command; where it is not, the
 * guard has no way to know what runs.
 */
const STRING_INTERPRETERS = new Set(["bash", "dash", "eval", "ksh", "sh", "zsh"]);

/** Commands that move the shell itself somewhere the guard cannot follow. */
const DIRECTORY_UNKNOWNS = new Set([".", "popd", "source"]);

/**
 * Where a `cd` or `pushd` leaves the shell. Returns the resolved directory, or
 * null where the guard cannot know it: an argument that expands, no argument
 * at all (`$HOME`), `cd -` (the previous directory), or any form not
 * recognized. A stale directory is what lets a later branch move look safe, so
 * every unrecognized form answers "unknown" rather than "unchanged".
 */
function directoryAfterChange(base, words) {
	const operands = [];
	for (const word of words.slice(1)) {
		if (word.text === "--") continue;
		if (word.literal && /^-[LPe@]+$/u.test(word.text)) continue;
		operands.push(word);
	}
	if (operands.length !== 1) return null;
	const [target] = operands;
	if (!target.literal || target.text === "-") return null;
	const moved = resolveAgainst(base, target.text);
	// A `cd` into something that is not a directory fails, and the shell stays
	// where it was — but reading it as unchanged is the stale answer #272's
	// note rules out, and reading it as moved places every later command in a
	// directory the shell never entered. Unknown is the answer that holds
	// whichever way the `cd` went.
	//
	// Both sides of the test are canonical, because `existingDirectory` walks
	// up and canonicalizes: comparing it against the uncanonical path would
	// call every symlinked directory nonexistent, and a symlinked worktrees
	// root is an ordinary thing to have.
	if (moved === null || existingDirectory(moved) !== resolvedPath(moved)) {
		return null;
	}
	return moved;
}

/**
 * A command that would rewrite the primary checkout's working tree, or one
 * unreadable enough that it might.
 *
 * The walk is the inversion this guard turns on: it does not look for proof
 * that a command is dangerous, it looks for proof that every command is
 * placed. A command whose executable, arguments, or working directory the
 * recognizer cannot read is refused where it could be running in the primary
 * checkout, rather than allowed because nothing matched a dangerous shape.
 */
function rewritesPrimaryWorkingTree(event, cwd) {
	if (event.toolName !== "bash" || typeof event.input?.command !== "string") {
		return false;
	}

	// A relative tool cwd is relative to the session's directory, never to the
	// directory this Node process happens to run in. It is null where there is
	// no session directory to read it against: a command that rewrites no
	// working tree still passes, and one that rewrites a working tree is
	// refused below, because the repository it would change cannot be
	// identified.
	const toolCwd = anchoredPath(
		cwd,
		typeof event.input.cwd === "string" ? event.input.cwd : ".",
	);
	return walkShellCommand(event.input.command, toolCwd);
}

/** Walk one command's segments, tracking the shell's working directory. */
function walkShellCommand(command, toolCwd) {
	const { segments, functions, unreadable } = shellSegments(command);
	if (unreadable !== null) {
		throw new UnreadableCommandError(unreadable);
	}
	const defined = new Set(functions);
	let shellCwd = toolCwd;
	const shellCwdStack = [];
	// Words inside `$((…))` are arithmetic, not a command. Reading them as one
	// would refuse `$(( $n + 1 ))` for naming an executable that expands.
	const arithmeticStack = [];

	// The separator that ended the previous command, which is what says whether
	// the next one runs at all.
	let previousSeparator = null;

	for (const segment of segments) {
		if (segment.group === "open") {
			shellCwdStack.push(shellCwd);
			arithmeticStack.push(segment.arithmetic === true);
			previousSeparator = null;
			continue;
		}
		if (segment.group === "close") {
			// A `cd` inside a subshell stops applying when the subshell ends.
			if (shellCwdStack.length > 0) shellCwd = shellCwdStack.pop();
			arithmeticStack.pop();
			previousSeparator = null;
			continue;
		}
		const enteredAfter = previousSeparator;
		previousSeparator = segment.separator;
		if (arithmeticStack.at(-1) === true) continue;

		for (const start of gitWordIndices(segment.words)) {
			const invocation = gitInvocation(segment.words, shellCwd, start, toolCwd);
			if (invocation === null || !rewritesWorkingTree(invocation)) continue;
			if (invocation.unreadable) {
				throw new UnreadableCommandError(
					"a git invocation carries an option the guard cannot read",
				);
			}
			if (invocation.cwd === null) {
				throw new UnanchoredPathError(
					"a working-tree rewrite arrived with no working directory to place it in",
				);
			}
			if (invocation.gitDir === UNREADABLE || invocation.workTree === UNREADABLE) {
				throw new UnreadableCommandError(
					"a working-tree rewrite selects its repository with a value that expands",
				);
			}
			const gitDirState = invocation.gitDir
				? worktreeStateFromGitDir(invocation.gitDir, invocation.cwd)
				: null;
			// A Git directory that resolves to no repository must not skip the
			// cwd check. Skipping it lets an unresolvable selector fail open.
			const repositoryState = gitDirState ?? worktreeState(".", invocation.cwd);
			const attaches = attachesBranch(invocation);
			if (movesGuardedPrimary(repositoryState, shellCwd, attaches)) return true;
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

		// The executable, once any leading environment assignments are past.
		let position = 0;
		while (
			position < segment.words.length &&
			isEnvironmentAssignment(segment.words[position])
		) {
			position++;
		}
		const executable = segment.words[position];
		if (executable === undefined) continue;
		if (!executable.literal) {
			// Everywhere, not only in the primary checkout: the program a word
			// expands to may be `git`, and `git -C <primary> switch` reaches the
			// primary from any directory at all.
			throw new UnreadableCommandError(
				"a command names an executable that expands",
			);
		}

		const name = basename(executable.text);
		const operands = segment.words.slice(position + 1);

		if (STRING_INTERPRETERS.has(name)) {
			// `sh -c '…'` and `eval '…'` run a string. One literal string is
			// read like any other command; anything else is unreadable. `eval`
			// runs in the current shell, so its directory changes carry; `sh -c`
			// runs a child, so they do not.
			const script = operands.filter(
				(operand) => !(operand.literal && operand.text.startsWith("-")),
			);
			if (script.length === 0) continue;
			if (script.length > 1 || !script[0].literal) {
				// A shell running more shell is squarely inside what this guard
				// reads, so an unreadable script is refused wherever it runs: the
				// string may name the primary checkout itself.
				throw new UnreadableCommandError(
					"a command runs a string the guard cannot read",
				);
			}
			if (name === "eval") {
				if (walkShellCommand(script[0].text, shellCwd)) return true;
				shellCwd = null;
			} else if (walkShellCommand(script[0].text, shellCwd)) {
				return true;
			}
			continue;
		}

		if (DIRECTORY_UNKNOWNS.has(name) || defined.has(name)) {
			// A sourced file and a function body are commands the guard has not
			// read, and both can move the shell that runs them.
			shellCwd = null;
			continue;
		}

		if (name === "cd" || name === "pushd") {
			if (
				segment.separator === "|" ||
				segment.separator === "&" ||
				enteredAfter === "|" ||
				enteredAfter === "|&"
			) {
				// A `cd` on either side of a pipe, or in a background job, runs
				// in a subshell of its own, so the shell that continues never
				// moves.
				continue;
			}
			if (enteredAfter === "&&" || enteredAfter === "||") {
				// Whether this `cd` ran at all depends on an exit status the
				// guard cannot know. `false && cd elsewhere` leaves the shell
				// where it was, and reading the `cd` as having happened is how a
				// later working-tree rewrite in the primary looked like one
				// somewhere else.
				shellCwd = null;
				continue;
			}
			const moved = directoryAfterChange(shellCwd, segment.words.slice(position));
			// `cd x || y` may or may not have moved; either answer would be a
			// guess, so the directory becomes unknown.
			shellCwd = segment.separator === "||" ? null : moved;
		}
	}
	return false;
}

/** True when a mutation would bypass the task worktree boundary. */
function blocksTaskWorktree(event, cwd) {
	if (rewritesPrimaryWorkingTree(event, cwd)) return true;
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
			if (err instanceof UnanchoredPathError) {
				return { block: true, reason: UNANCHORED_PATH_BLOCK_REASON };
			}
			if (err instanceof UnreadableCommandError) {
				return { block: true, reason: UNREADABLE_COMMAND_BLOCK_REASON };
			}
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