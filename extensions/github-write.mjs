import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";

const FIELD_FLAGS = new Set(["-f", "-F", "--field", "--raw-field"]);
const VALUE_FLAGS = new Set([
	"-R", "--repo", "--hostname", "--config", "--json", "--jq", "--template", "-H", "--header",
]);
const BODY_COMMANDS = new Set(["create", "edit", "comment", "review"]);
const GH_BODY_ENDPOINT = /(?:^|\/)repos\/[^/]+\/[^/]+\/(?:issues(?:\/\d+)?(?:\/comments)?|pulls(?:\/\d+)?(?:\/(?:comments(?:\/\d+\/replies)?|reviews))?)(?:\?.*)?$/iu;
const COMPLETE_BLOCK = /(^|\r?\n)---\r?\nModel: ([^\r\n]*)\r?\nHarness: ([^\r\n]*)\r?\nsession: ([^\r\n]*)/gmu;

/** Direct body-bearing `gh` calls must use the attributed wrapper. */
export const GITHUB_WRITE_BLOCK_REASON =
	"Direct body-bearing `gh` writes are blocked. Call `daily_driver_gh_write` " +
	"with the `gh` arguments as an array; it adds and deduplicates provenance. " +
	"Keep read-only and non-body `gh` calls on their existing routes.";

function optionValues(args) {
	const operands = [];
	const bodyOptions = [];
	const fieldOptions = [];
	const inputOptions = [];
	let method = null;
	for (let index = 0; index < args.length; index++) {
		const value = args[index];
		if (typeof value !== "string") continue;
		if (value === "-X" || value === "--method") {
			method = args[index + 1] ?? null;
			index++;
			continue;
		}
		if (value.startsWith("--method=")) {
			method = value.slice("--method=".length);
			continue;
		}
		if (/^-X./u.test(value)) {
			method = value.slice(2);
			continue;
		}
		if (value === "--body" || value === "-b" || value === "--body-file") {
			bodyOptions.push({ flag: value, index, value: args[index + 1] ?? null });
			index++;
			continue;
		}
		if (value.startsWith("--body=") || value.startsWith("-b=")) {
			const offset = value.startsWith("--body=") ? 7 : 3;
			bodyOptions.push({ flag: value.slice(0, offset - 1), index, inline: true, value: value.slice(offset) });
			continue;
		}
		if (value.startsWith("--body-file=")) {
			bodyOptions.push({ flag: "--body-file", index, inline: true, value: value.slice(12) });
			continue;
		}
		if (value === "--input") {
			inputOptions.push({ index, value: args[index + 1] ?? null });
			index++;
			continue;
		}
		if (value.startsWith("--input=")) {
			inputOptions.push({ index, inline: true, value: value.slice(8) });
			continue;
		}
		if (FIELD_FLAGS.has(value)) {
			fieldOptions.push({ flag: value, index, value: args[index + 1] ?? null });
			index++;
			continue;
		}
		if (/^--(?:field|raw-field)=/u.test(value)) {
			const equals = value.indexOf("=");
			fieldOptions.push({ flag: value.slice(0, equals), index, inline: true, value: value.slice(equals + 1) });
			continue;
		}
		if (/^-f.+=/u.test(value) || /^-F.+=/u.test(value)) {
			fieldOptions.push({ flag: value.slice(0, 2), index, inline: true, value: value.slice(2) });
			continue;
		}
		if (VALUE_FLAGS.has(value)) {
			index++;
			continue;
		}
		if (value.startsWith("--")) continue;
		if (value.startsWith("-") && value.length > 1) continue;
		operands.push({ index, value });
	}
	return { operands, bodyOptions, fieldOptions, inputOptions, method };
}

function apiEndpoint(args) {
	const parsed = optionValues(args);
	const apiIndex = parsed.operands.findIndex((word) => word.value === "api");
	if (apiIndex < 0) return null;
	const path = parsed.operands.slice(apiIndex + 1).find((word) => GH_BODY_ENDPOINT.test(word.value));
	return path?.value ?? null;
}

/** Whether `args` names a body-bearing issue or pull-request write. */
export function isGitHubBodyWrite(args) {
	if (!Array.isArray(args) || args.some((arg) => typeof arg !== "string")) return false;
	const { operands, bodyOptions, fieldOptions, inputOptions, method } = optionValues(args);
	const [group, verb] = operands.map((word) => word.value);
	if ((group === "issue" || group === "pr") && BODY_COMMANDS.has(verb)) {
		return bodyOptions.length > 0;
	}
	if (group !== "api") return false;
	const endpoint = apiEndpoint(args);
	if (!endpoint || method?.toUpperCase() === "GET") return false;
	const hasBodyField = fieldOptions.some((option) => option.value?.split("=", 1)[0] === "body");
	const bodyEndpoint = /\/(?:issues\/\d+\/comments|pulls\/\d+\/(?:comments(?:\/\d+\/replies)?|reviews))$/iu.test(endpoint);
	return hasBodyField || (inputOptions.length > 0 && bodyEndpoint);
}

/** Whether `args` names an issue or pull-request comment write. */
export function isGitHubCommentWrite(args) {
	if (!Array.isArray(args) || args.some((arg) => typeof arg !== "string")) return false;
	const { operands, fieldOptions, inputOptions, method } = optionValues(args);
	const [group, verb] = operands.map((word) => word.value);
	if ((group === "issue" || group === "pr") && verb === "comment") return true;
	if (group !== "api") return false;
	const endpoint = apiEndpoint(args);
	if (!endpoint || !/\/(?:issues\/\d+\/comments|pulls\/\d+\/comments(?:\/\d+\/replies)?)$/iu.test(endpoint)) return false;
	if (method && method.toUpperCase() === "GET") return false;
	return inputOptions.length > 0 || fieldOptions.some((option) => option.value?.split("=", 1)[0] === "body");
}

function attributionBlock(body, attribution) {
	const tuples = new Set();
	const duplicateRanges = [];
	for (const match of body.matchAll(COMPLETE_BLOCK)) {
		const tuple = JSON.stringify([match[2], match[3], match[4]]);
		if (tuples.has(tuple)) {
			const start = match.index + match[1].length;
			duplicateRanges.push([start, start + match[0].length - match[1].length]);
		} else {
			tuples.add(tuple);
		}
	}
	let result = body;
	for (const [start, end] of duplicateRanges.reverse()) {
		result = result.slice(0, start) + result.slice(end);
	}
	const current = JSON.stringify([attribution.model, attribution.harness, attribution.session]);
	if (!tuples.has(current)) {
		const block = `---\nModel: ${attribution.model}\nHarness: ${attribution.harness}\nsession: ${attribution.session}`;
		const separator = result.length === 0 ? "" : result.endsWith("\n\n") ? "" : result.endsWith("\n") ? "\n" : "\n\n";
		result += `${separator}${block}`;
	}
	return result;
}

function readOmpVersion() {
	try {
		const output = execFileSync("omp", ["--version"], {
			encoding: "utf8",
			stdio: ["ignore", "pipe", "ignore"],
			timeout: 5000,
		});
		const version = output.trim().replace(/^omp[\/\s]+/iu, "");
		return version || "n/a";
	} catch {
		return "n/a";
	}
}

function putOptionValue(args, option, value) {
	if (option.inline) args[option.index] = `${args[option.index].slice(0, args[option.index].indexOf("=") + 1)}${value}`;
	else args[option.index + 1] = value;
}

function bodyFields(payload) {
	const targets = [];
	if (payload && typeof payload === "object" && !Array.isArray(payload)) {
		if (typeof payload.body === "string") targets.push(payload);
		if (Array.isArray(payload.comments)) {
			for (const comment of payload.comments) {
				if (comment && typeof comment === "object" && typeof comment.body === "string") targets.push(comment);
			}
		}
	}
	return targets;
}

function writePrivateFile(directory, name, content) {
	const path = join(directory, name);
	writeFileSync(path, content, { encoding: "utf8", mode: 0o600 });
	return path;
}

function bodyFileContents(path, stdin, cwd) {
	if (path === "-") {
		if (typeof stdin !== "string") throw new Error("The body input is `-`, but no `stdin` string was supplied.");
		return stdin;
	}
	return readFileSync(resolve(cwd || process.cwd(), path), "utf8");
}

function prepareArguments(args, stdin, attribution, cwd, directory) {
	const prepared = [...args];
	const parsed = optionValues(prepared);
	let bodyCount = 0;
	for (const option of parsed.bodyOptions) {
		if (option.value === null) throw new Error(`${option.flag} requires a value.`);
		let body;
		if (option.flag === "--body-file") {
			body = bodyFileContents(option.value, stdin, cwd);
			const path = writePrivateFile(directory, `body-${bodyCount}.txt`, attributionBlock(body, attribution));
			putOptionValue(prepared, option, path);
		} else {
			body = attributionBlock(option.value, attribution);
			putOptionValue(prepared, option, body);
		}
		bodyCount++;
	}

	for (const option of parsed.fieldOptions) {
		if (option.value === null) throw new Error(`${option.flag} requires a value.`);
		const separator = option.value.indexOf("=");
		if (separator < 0 || option.value.slice(0, separator) !== "body") continue;
		const next = `body=${attributionBlock(option.value.slice(separator + 1), attribution)}`;
		if (option.inline) {
			const old = prepared[option.index];
			const prefix = old.startsWith("--") ? `${old.slice(0, old.indexOf("=") + 1)}` : old.slice(0, 2);
			prepared[option.index] = `${prefix}${next}`;
		} else {
			prepared[option.index + 1] = next;
		}
		bodyCount++;
	}

	for (const [index, input] of parsed.inputOptions.entries()) {
		if (input.value === null) throw new Error("--input requires a file path or `-`.");
		const source = bodyFileContents(input.value, stdin, cwd);
		let payload;
		try {
			payload = JSON.parse(source);
		} catch {
			throw new Error("The JSON supplied through `gh api --input` is invalid.");
		}
		const targets = bodyFields(payload);
		if (targets.length === 0) throw new Error("The JSON supplied to this body-bearing API write has no string `body` field.");
		for (const target of targets) target.body = attributionBlock(target.body, attribution);
		const content = JSON.stringify(payload) + (source.endsWith("\n") ? "\n" : "");
		const path = writePrivateFile(directory, `input-${index}.json`, content);
		putOptionValue(prepared, input, path);
		bodyCount += targets.length;
	}
	if (bodyCount === 0) throw new Error("No supported body payload was found. Use `--body`, `--body-file`, a `body=` API field, or JSON `--input`.");
	return prepared;
}

function runProcess(spawnProcess, args, stdin, cwd, signal) {
	return new Promise((resolveRun, rejectRun) => {
		let child;
		try {
			child = spawnProcess("gh", args, {
				...(typeof cwd === "string" ? { cwd } : {}),
				...(signal ? { signal } : {}),
				stdio: ["pipe", "pipe", "pipe"],
				windowsHide: true,
			});
		} catch (error) {
			rejectRun(error);
			return;
		}
		const stdout = [];
		const stderr = [];
		child.stdout.on("data", (chunk) => stdout.push(Buffer.from(chunk)));
		child.stderr.on("data", (chunk) => stderr.push(Buffer.from(chunk)));
		child.once("error", rejectRun);
		child.once("close", (code, childSignal) => resolveRun({
			code,
			signal: childSignal,
			stdout: Buffer.concat(stdout).toString("utf8"),
			stderr: Buffer.concat(stderr).toString("utf8"),
		}));
		child.stdin.end(typeof stdin === "string" ? stdin : undefined);
	});
}

/** Create an Omp GitHub writer with one version read cached per extension instance. */
export function createGitHubWriteRunner({ spawnProcess = spawn, versionReader = readOmpVersion } = {}) {
	let versionPromise;
	return async function runGitHubWrite(args, stdin, ctx, signal) {
		if (!isGitHubBodyWrite(args)) throw new Error("Only body-bearing `gh` writes are accepted by this tool.");
		if (!Array.isArray(args) || args.some((arg) => typeof arg !== "string")) {
			throw new Error("`args` must be an array of `gh` argument strings.");
		}
		versionPromise ??= Promise.resolve().then(versionReader).then((version) =>
			typeof version === "string" && version.length > 0 ? version.replace(/^omp[\/\s]+/iu, "") : "n/a",
		).catch(() => "n/a");
		const [version, model, session] = await Promise.all([
			versionPromise,
			Promise.resolve(ctx?.model?.id),
			Promise.resolve().then(() => ctx?.sessionManager?.getSessionId?.()),
		]);
		const attribution = {
			model: typeof model === "string" && model.length > 0 ? model : "n/a",
			harness: `Omp ${version}`,
			session: typeof session === "string" && session.length > 0 ? session : "n/a",
		};
		let temporaryDirectory;
		try {
			temporaryDirectory = mkdtempSync(join(tmpdir(), "daily-driver-gh-write-"));
			const preparedArgs = prepareArguments(args, stdin, attribution, ctx?.cwd, temporaryDirectory);
			return await runProcess(spawnProcess, preparedArgs, stdin, ctx?.cwd, signal);
		} finally {
			if (temporaryDirectory) rmSync(temporaryDirectory, { recursive: true, force: true });
		}
	};
}
