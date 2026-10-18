import { lstatSync, readdirSync, realpathSync, statSync } from "node:fs";
import { dirname, isAbsolute, relative, resolve } from "node:path";

/** Adapter-owned JSON policy: one task root and explicitly declared treatment documents. */
export const READ_POLICY_ENV = "CODER_EVAL_OMP_READ_POLICY";

const SELECTOR = /^(?:raw|img|conflicts|-?\d+(?:[-+,]\d+)*)(?::(?:raw|img|conflicts|-?\d+(?:[-+,]\d+)*))*$/;
const URI = /^([a-z][a-z0-9+.-]*):\/{1,2}(.*)$/i;

function contained(target, root) {
	const tail = relative(root, target);
	return tail === "" || (tail !== ".." && !tail.startsWith("../") && !isAbsolute(tail));
}

function policyFrom(env) {
	const policy = JSON.parse(env[READ_POLICY_ENV]);
	if (!isAbsolute(policy.taskRoot) || !Array.isArray(policy.documentRoots) ||
		policy.documentRoots.some((root) => typeof root !== "string" || !isAbsolute(root))) {
		throw new Error("invalid read policy");
	}
	return {
		taskRoot: realpathSync(policy.taskRoot),
		roots: [policy.taskRoot, ...policy.documentRoots].map((root) => realpathSync(root)),
	};
}

function allowed(target, policy) {
	return policy.roots.some((root) => contained(target, root));
}

function normalize(raw, env) {
	let text = raw.trim().replace(/^"(.*)"$/, "$1");
	text = text.replace(/^@/, "").replace(/^:(?=[/\\~]|\.\.?[/\\])/, "");
	text = text.replace(/[\u00a0\u2000-\u200a\u202f\u205f\u3000]/g, " ");
	if (text.startsWith("~")) text = resolve(env.HOME, text.slice(1).replace(/^[/\\]/, ""));
	return text;
}

// Existing literal names take precedence, as in Omp. A missing target never
// reaches Omp's fuzzy suffix or approved-plan recovery outside the read policy.
function existingTarget(text, policy) {
	const absolute = resolve(policy.taskRoot, text);
	try {
		return realpathSync(absolute);
	} catch {
		for (let colon = text.lastIndexOf(":"); colon > 0; colon = text.lastIndexOf(":", colon - 1)) {
			if (!SELECTOR.test(text.slice(colon + 1))) continue;
			try {
				return realpathSync(resolve(policy.taskRoot, text.slice(0, colon)));
			} catch { /* A different selector split may identify the literal file. */ }
		}
		return null;
	}
}

// Native directory readers and searches can follow descendants, not only their
// input root. Refuse a tree containing an escaping link before giving it to Omp.
function safeTree(target, policy, seen = new Set()) {
	if (!allowed(target, policy)) return false;
	if (!statSync(target).isDirectory() || seen.has(target)) return true;
	seen.add(target);
	for (const entry of readdirSync(target)) {
		const child = resolve(target, entry);
		const stat = lstatSync(child);
		if ((stat.isDirectory() || stat.isSymbolicLink()) && !safeTree(realpathSync(child), policy, seen)) return false;
	}
	return true;
}

function skillTarget(body, commands) {
	// Only runtime-loaded skills confer URI access. In particular, a bare arm
	// cannot turn a known host checkout into a registered skill.
	const entries = commands.filter((command) => command.source === "skill" && typeof command.path === "string")
		.map((command) => ({ name: command.name.replace(/^skill:/, ""), path: command.path }))
		.sort((a, b) => b.name.length - a.name.length);
	for (const entry of entries) {
		if (body !== entry.name && !body.startsWith(`${entry.name}/`) && !body.startsWith(`${entry.name}:`)) continue;
		let suffix = body.slice(entry.name.length);
		if (suffix.startsWith(":")) {
			if (!SELECTOR.test(suffix.slice(1))) return null;
			suffix = "";
		}
		if (!suffix || suffix === "/") return entry.path;
		const decoded = decodeURIComponent(suffix.slice(1));
		if (decoded.split(/[\\/]/).includes("..") || isAbsolute(decoded)) return null;
		return resolve(dirname(entry.path), decoded);
	}
	return null;
}

function safePath(raw, tool, policy, env, commands) {
	const text = normalize(raw, env);
	if (text.includes(";")) {
		return text.split(";").every((part) => part.trim() && safePath(part, tool, policy, env, commands));
	}
	const uri = URI.exec(text);
	if (uri) {
		const scheme = uri[1].toLowerCase();
		if (scheme === "skill") {
			const target = skillTarget(uri[2], commands);
			if (target === null) return false;
			return safePath(target, tool, policy, env, commands);
		}
		// These protocols serve runtime-managed virtual resources, not arbitrary
		// local filenames. The outer eval guard still owns the scheme allow list.
		return ["rule", "xd", "proc", "omp"].includes(scheme);
	}
	const target = existingTarget(text, policy);
	if (target !== null) return safeTree(target, policy);
	if (tool === "glob" || tool === "grep") {
		const wildcard = text.search(/[*?\[{]/);
		if (wildcard >= 0) {
			// Only the directory before the first wildcard determines search scope.
			// Parent segments after it could make glob expansion leave that scope.
			if (text.slice(wildcard).includes("..") || /[\[{]/.test(text)) return false;
			const prefix = text.slice(0, wildcard);
			const base = prefix.slice(0, prefix.lastIndexOf("/") + 1) || ".";
			const root = existingTarget(base, policy);
			return root !== null && safeTree(root, policy);
		}
	}
	return false;
}

/** Refuse file-tool inputs whose canonical read targets cannot be proven allowed. */
export function guardReadCall(event, env, commands = []) {
	if (!["read", "grep", "glob"].includes(event.toolName)) return undefined;
	try {
		const policy = policyFrom(env);
		const paths = event.input?.path ?? (event.toolName === "read" ? null : ".");
		if (typeof paths !== "string" || !safePath(paths, event.toolName, policy, env, commands)) {
			throw new Error("outside readable inputs or unsupported target");
		}
		return undefined;
	} catch {
		return {
			block: true,
			reason: "The eval read boundary refuses this target: it is outside this task's readable inputs, " +
				"cannot be resolved safely, or the read policy is missing. Use existing task files or declared skill documents.",
		};
	}
}
