#!/usr/bin/env node
/**
 * Behavioural check for the Omp eval arm's sandbox guard
 * (evals/coder-eval-omp/src/coder_eval_omp/eval_guard.js).
 *
 * Imports the extension with a fake `pi`, the way check-omp-extension.mjs
 * drives the plugin's extension, and sends it the `tool_call` events issue
 * #461 measured. Each case's comment names the bypass it exists to catch: a
 * guard that misses one raises no error, and the eval row reaches GitHub.
 *
 * What it cannot show is that Omp honours the refusal, or that `-e` and the
 * linked plugin load together. `make check-omp-eval-guard-live` drives a real
 * `omp` for that.
 *
 * Credential-free and dependency-free. Run from the repository root:
 *
 *     node scripts/check-omp-eval-guard.mjs
 */

import assert from "node:assert/strict";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const GUARD = resolve(ROOT, "evals/coder-eval-omp/src/coder_eval_omp/eval_guard.js");

const { default: evalGuardExtension, TOOLS_ENV } = await import(pathToFileURL(GUARD).href);

const handlers = [];
evalGuardExtension({
	on(event, handler) {
		assert.equal(event, "tool_call", "the guard subscribes to tool_call alone");
		handlers.push(handler);
	},
});
assert.equal(handlers.length, 1, "the guard registers exactly one tool_call handler");

/** The guard's verdict on one call, with `tools` as the row's grant (undefined: unset). */
function verdict(toolName, input, tools) {
	if (tools === undefined) delete process.env[TOOLS_ENV];
	else process.env[TOOLS_ENV] = tools;
	return handlers[0]({ type: "tool_call", toolCallId: "call-1", toolName, input }, {});
}

function refuses(name, toolName, input, tools, scheme) {
	const result = verdict(toolName, input, tools);
	assert.equal(result?.block, true, `${name}: must be refused`);
	assert.ok(result.reason, `${name}: a refusal carries a reason`);
	if (scheme) {
		assert.match(result.reason, new RegExp(`${scheme}://`), `${name}: the reason names the scheme`);
		assert.match(result.reason, /outside this eval's sandbox/, `${name}: the reason says why`);
	}
}

function passes(name, toolName, input, tools) {
	assert.equal(verdict(toolName, input, tools), undefined, `${name}: must pass`);
}

// Row 1 of #461: a read of `pr://` reached GitHub with the ambient token.
refuses("read pr://", "read", { path: "pr://o/r/1" }, "read", "pr");

// Row 4: `grep` resolves the same schemes, so a guard on `read` alone misses it.
refuses("grep issue://", "grep", { pattern: "x", path: "issue://o/r/1" }, "read,grep", "issue");

// Row 7: Omp splits a `;` list and resolves each part, so a whole-string check
// of `read`'s path was bypassed.
refuses("read ;-list", "read", { path: "inside.txt;issue://o/r/1" }, "read", "issue");

// Scheme case: Omp lowercases before it matches, so a case-sensitive guard
// would pass `HTTPS://`.
refuses("read HTTPS://", "read", { path: "HTTPS://example.com/" }, "read", "https");

// A nested argument: `glob` and `grep` take path lists, so a guard that read
// only top-level strings would miss a scheme inside an array.
refuses("glob paths list", "glob", { pattern: "*", paths: ["src", "issue://o/r/1"] }, "glob", "issue");

// Row 9: with `read` on Omp adds a `write`, and only Omp's own check keeps it
// off the filesystem. The guard makes that boundary ours.
refuses("write file under read", "write", { path: "notes.txt", content: "x" }, "read");

// `proc://` is an allowed scheme, so only the write rule stops this: a
// `proc://` write has workspace scope.
refuses("write proc:// under read", "write", { path: "proc://svc/mode", content: "x" }, "read");

// Fail closed: a guard that loses the grant must not read that as a grant of
// devices, or of anything else.
refuses("write xd:// with the grant unset", "write", { path: "xd://x", content: "{}" }, undefined);

// The ordinary file read every row makes.
passes("read inside.txt", "read", { path: "inside.txt" }, "read");

// Omp engages a skill by reading `skill://<name>`; refusing it voids every
// positive row.
passes("read skill://", "read", { path: "skill://undertake" }, "read");

// `undertake/09-title-before-claim-omp` grades exactly this device write.
passes(
	"write xd:// under read",
	"write",
	{ path: "xd://daily_driver_set_session_title", content: '{"title":"#1 x"}' },
	"read",
);

// A row that grants `Write` must still write files.
passes("write file under read,write", "write", { path: "notes.txt", content: "x" }, "read,write");

// `bash` is out of scope: a row that allows `Bash` has the network on both
// harnesses, and refusing it here would make the arms disagree.
passes("bash", "bash", { command: "curl https://example.com/ && gh pr view 1" }, "bash");

console.log("check-omp-eval-guard: the eval guard refuses every measured bypass and passes the rows' own calls");
