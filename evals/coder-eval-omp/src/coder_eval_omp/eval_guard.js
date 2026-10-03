/**
 * The Omp eval arm's sandbox guard: an extension loaded with `-e` into every
 * `omp --mode rpc` the `omp` agent kind starts, in both arms.
 *
 * `omp --tools` filters built-in tools, and on Omp 18.4.10 it leaves two paths
 * open (issue #461). `read`, `grep` and `glob` resolve Omp's `pr://` and
 * `issue://` schemes, which reach GitHub with the ambient token. And with
 * `read` on, Omp adds a device-only `write` that only Omp's own check keeps off
 * the filesystem. `fetch.enabled: false` in the throwaway config closes
 * http(s); this guard closes the rest, and refuses before any request goes out.
 *
 * Two rules, in one `tool_call` handler:
 *
 * 1. Every tool except `bash`: any string anywhere in the input that names a
 *    `<scheme>://` outside `ALLOWED_SCHEMES` is refused. Substrings, not whole
 *    strings, because Omp splits a `;` list and resolves each part; Omp's own
 *    `readTier` takes the same fail-closed approach. `bash` is out of scope: a
 *    row that allows `Bash` has the network on both harnesses.
 * 2. Where the row's grant has no `write`, a `write` whose path is not an
 *    `xd://` device is refused. The adapter passes the grant in
 *    `CODER_EVAL_OMP_TOOLS`. The adapter always sets it, so a guard that finds
 *    it unset is misconfigured, and refuses every `write`, devices included.
 *
 * No dependencies, for the reason `extensions/daily-driver.js` gives.
 */

/** Schemes a row may name: Omp's local ones, none of which leaves the machine. */
export const ALLOWED_SCHEMES = new Set(["skill", "rule", "xd", "proc", "omp"]);

/** The environment variable that carries the row's Omp tool grant, comma-joined. */
export const TOOLS_ENV = "CODER_EVAL_OMP_TOOLS";

// RFC 3986's scheme grammar, so that `inside.txt;issue://` yields `issue`.
const SCHEME_PATTERN = /([a-z][a-z0-9+.-]*):\/\//gi;

/** Every string inside `value`, at any depth. */
function* strings(value) {
	if (typeof value === "string") {
		yield value;
	} else if (Array.isArray(value)) {
		for (const item of value) yield* strings(item);
	} else if (value !== null && typeof value === "object") {
		for (const item of Object.values(value)) yield* strings(item);
	}
}

/** The first scheme in `input` outside the allow list, lowercased, or null. */
export function refusedScheme(input) {
	for (const text of strings(input)) {
		for (const match of text.matchAll(SCHEME_PATTERN)) {
			const scheme = match[1].toLowerCase();
			if (!ALLOWED_SCHEMES.has(scheme)) return scheme;
		}
	}
	return null;
}

/** The row's Omp tool grant, read from `env`, or null where it is unset. */
export function grantedTools(env) {
	const raw = env[TOOLS_ENV];
	if (typeof raw !== "string") return null;
	return new Set(
		raw
			.split(",")
			.map((name) => name.trim())
			.filter(Boolean),
	);
}

/** The refusal for one tool call, or undefined to let it run. */
export function guardToolCall(event, env) {
	if (event.toolName === "bash") return undefined;
	const scheme = refusedScheme(event.input);
	if (scheme !== null) {
		return {
			block: true,
			reason:
				`${scheme}:// is outside this eval's sandbox: the eval guard refuses ` +
				`any ${scheme}:// target, so do not retry it. Work from the local files instead.`,
		};
	}
	if (event.toolName === "write") {
		const granted = grantedTools(env);
		if (granted === null) {
			return {
				block: true,
				reason:
					`The eval guard cannot read this row's tool grant (${TOOLS_ENV} is unset), ` +
					"so it refuses every write. Do not retry it.",
			};
		}
		const path = event.input?.path;
		if (!granted.has("write") && (typeof path !== "string" || !path.startsWith("xd://"))) {
			return {
				block: true,
				reason:
					"This eval row does not grant write, so the eval guard limits `write` " +
					"to xd:// devices and refuses every other path. Do not retry it.",
			};
		}
	}
	return undefined;
}

/** The extension factory Omp calls with its `ExtensionAPI`. */
export default function evalGuardExtension(pi) {
	pi.on("tool_call", (event) => guardToolCall(event, process.env));
}
