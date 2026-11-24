import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";

const ATTRIBUTION_KEYS = new Map([
	["co-authored-by", "Co-Authored-By"],
	["omp-session", "Omp-Session"],
	["claude-session", "Claude-Session"],
	["codex-session", "Codex-Session"],
]);
const CONTROL = /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/u;

function messageText(value, name) {
	if (typeof value !== "string" || value.includes("\0")) {
		throw new Error(`${name} must be a string without NUL characters`);
	}
	return value;
}

function trailerValue(value, name) {
	if (typeof value !== "string" || !value.trim() || value !== value.trim() || CONTROL.test(value)) {
		throw new Error(`${name} must be a nonempty, single-line trailer value without surrounding whitespace`);
	}
	return value;
}

function parseTrailers(message) {
	// Parse outside the caller's repository, without user/system configuration.
	// --only-input (included in --parse) never executes configured trailer commands.
	const env = { ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL: "/dev/null", GIT_CONFIG_COUNT: "0" };
	for (const key of ["GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS"]) delete env[key];
	const output = execFileSync("git", ["-c", "trailer.separators=:", "interpret-trailers", "--parse", "--no-divider"], {
		cwd: tmpdir(), env, input: message, encoding: "utf8", maxBuffer: 16 * 1024 * 1024,
		stdio: ["pipe", "pipe", "pipe"], timeout: 10000,
	});
	return output.split("\n").filter(Boolean).map(line => {
		const colon = line.indexOf(":");
		if (colon < 1) throw new Error("Git returned an invalid trailer record");
		return { key: line.slice(0, colon), value: line.slice(colon + 1).trim() };
	});
}

function recordId({ key, value }) {
	return JSON.stringify([key.toLowerCase(), value]);
}

function rawRecords(message) {
	const records = [];
	const lines = [...message.matchAll(/[^\n]*(?:\n|$)/gu)].filter(match => match[0]);
	for (let index = 0; index < lines.length; index++) {
		const match = /^([^\s:]+)[ \t]*:[ \t]*([^\r\n]*)/u.exec(lines[index][0]);
		if (!match) continue;
		const start = lines[index].index;
		let end = start + lines[index][0].length;
		let value = match[2].trim();
		while (index + 1 < lines.length && /^[ \t]+\S/u.test(lines[index + 1][0])) {
			index++;
			value += ` ${lines[index][0].trim()}`;
			end = lines[index].index + lines[index][0].length;
		}
		records.push({ key: match[1], value, start, end });
	}
	return records;
}

function trailerSpans(message, parsed) {
	// Match only records Git identified, from the end. Similar text in earlier
	// prose or examples is not part of the trailing Git trailer block.
	const candidates = rawRecords(message);
	const spans = [];
	let index = candidates.length - 1;
	for (let trailer = parsed.length - 1; trailer >= 0; trailer--) {
		const id = recordId(parsed[trailer]);
		while (index >= 0 && recordId(candidates[index]) !== id) index--;
		if (index < 0) throw new Error("Cannot preserve the Git trailer block without changing its content");
		spans.unshift(candidates[index--]);
	}
	return spans;
}

/** Prepare a commit body with distinct source and live Omp attribution; never modify Git state. */
export function prepareCommitMessage({ body, sourceMessages = [], coAuthor }, ctx) {
	messageText(body, "body");
	if (!body.trim()) throw new Error("body must contain substantive commit text");
	if (!Array.isArray(sourceMessages)) throw new Error("sourceMessages must be an array of commit messages");
	for (const message of sourceMessages) messageText(message, "sourceMessages entry");
	if (coAuthor !== undefined) {
		trailerValue(coAuthor, "coAuthor");
		if (!/^[^<>]+ <[^<>\s@]+@[^<>\s@]+>$/u.test(coAuthor)) {
			throw new Error("coAuthor must be a verified configured Name <address> identity");
		}
	}
	const observedSession = ctx?.sessionManager?.getSessionId?.();
	const session = observedSession === undefined || observedSession === null || observedSession === ""
		? "n/a" : trailerValue(observedSession, "Omp session");
	const parsed = parseTrailers(body);
	const spans = trailerSpans(body, parsed);
	const trailers = [];
	const seen = new Set();
	const append = record => {
		const canonical = ATTRIBUTION_KEYS.get(record.key.toLowerCase());
		if (!canonical || seen.has(recordId(record))) return false;
		seen.add(recordId(record));
		trailers.push({ key: canonical, value: record.value });
		return true;
	};
	const removed = [];
	for (let index = 0; index < parsed.length; index++) {
		if (ATTRIBUTION_KEYS.has(parsed[index].key.toLowerCase()) && !append(parsed[index])) removed.push(spans[index]);
	}
	let prepared = body;
	for (const span of removed.reverse()) prepared = prepared.slice(0, span.start) + prepared.slice(span.end);
	const additions = [];
	for (const message of sourceMessages) {
		for (const record of parseTrailers(message)) {
			if (append(record)) additions.push(trailers.at(-1));
		}
	}
	for (const record of [
		...(coAuthor === undefined ? [] : [{ key: "Co-Authored-By", value: coAuthor }]),
		{ key: "Omp-Session", value: session },
	]) {
		if (append(record)) additions.push(trailers.at(-1));
	}
	if (additions.length) {
		prepared = prepared.replace(/(?:\r?\n)+$/u, "");
		prepared += (parsed.length ? "\n" : "\n\n") + additions.map(({ key, value }) => `${key}: ${value}`).join("\n") + "\n";
	}
	return { body: prepared, trailers };
}
