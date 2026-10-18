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
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const GUARD = resolve(ROOT, "evals/coder-eval-omp/src/coder_eval_omp/eval_guard.js");

const { default: evalGuardExtension, TOOLS_ENV } = await import(pathToFileURL(GUARD).href);
const { READ_POLICY_ENV } = await import(pathToFileURL(resolve(dirname(GUARD), "read_boundary.js")).href);
const fixture = mkdtempSync(resolve(tmpdir(), "eval-read-boundary-"));
process.on("exit", () => rmSync(fixture, { recursive: true, force: true }));
const task = resolve(fixture, "task");
const skills = resolve(fixture, "plugin/skills");
const host = resolve(fixture, "host");
mkdirSync(task, { recursive: true });
mkdirSync(resolve(skills, "undertake/references"), { recursive: true });
mkdirSync(host);
writeFileSync(resolve(task, "inside.txt"), "task input\nsecond line\n");
writeFileSync(resolve(skills, "undertake/SKILL.md"), "declared treatment");
writeFileSync(resolve(skills, "undertake/references/omp.md"), "declared reference");
writeFileSync(resolve(host, "task.json"), "protected sibling output");
const policy = JSON.stringify({ taskRoot: task, documentRoots: [skills] });
process.env[READ_POLICY_ENV] = policy;
const commands = [{ name: "skill:undertake", source: "skill", path: resolve(skills, "undertake/SKILL.md") }];

const handlers = [];
evalGuardExtension({
	getCommands: () => commands,
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

// A bare subject must not turn known host skill paths into treatment inputs.
process.env[READ_POLICY_ENV] = JSON.stringify({ taskRoot: task, documentRoots: [] });
refuses("bare host skill", "read", { path: commands[0].path }, "read");
refuses("bare skill URI", "read", { path: "skill://undertake" }, "read");
process.env[READ_POLICY_ENV] = policy;

// Protected bytes stay out through absolute, traversal, prefix-collision,
// selector and compound spellings of the same outside file.
for (const path of [
	resolve(host, "task.json"), "../host/task.json", `${host}/task.json:1-2:raw`,
	`inside.txt;${host}/task.json`, `skill://undertake:1;${host}/task.json`,
	"skill://undertake/%2e%2e/%2e%2e/host/task.json",
	"skill:/undertake/../../../host/task.json", "@/etc/passwd", ":/etc/passwd",
]) {
	refuses(`outside ${path}`, "read", { path }, "read");
}
for (const tool of ["grep", "glob"]) {
	refuses(`${tool} outside`, tool, { path: `${host}/*`, pattern: "protected" }, tool);
	passes(`${tool} task`, tool, { path: task, pattern: "input" }, tool);
}
passes("selected task input", "read", { path: "inside.txt:1-2:raw" }, "read");
// Unresolved colon paths must terminate; glob expansion must not manufacture
// parent segments outside an otherwise permitted search root.
refuses("colon-only unresolved target", "read", { path: ":missing" }, "read");
refuses("glob brace traversal", "glob", { path: "{inside,../host}/*" }, "glob");
refuses("glob bracket traversal", "glob", { path: "[.][.]/host/*" }, "glob");
passes("declared skill search", "glob", { path: "skill://undertake/references/*.md" }, "glob");
passes("declared reference", "read", { path: "skill://undertake/references/omp.md:1-2" }, "read");
passes("declared direct path", "read", { path: commands[0].path }, "read");

// A link in a permitted tree must not expose a provider file, including through
// a directory listing or recursive search whose argument itself is allowed.
symlinkSync(host, resolve(task, "escape"));
for (const tool of ["read", "grep", "glob"]) {
	refuses(`${tool} symlink`, tool, { path: "escape/task.json:1", pattern: "protected" }, tool);
	refuses(`${tool} nested symlink`, tool, { path: task, pattern: "protected" }, tool);
}

// Missing/malformed metadata and missing files must not activate runtime fuzzy
// recovery against host paths, or silently reuse another replicate's policy.
for (const raw of [undefined, "{", "{}", JSON.stringify({ taskRoot: task, documentRoots: ["/missing"] })]) {
	if (raw === undefined) delete process.env[READ_POLICY_ENV];
	else process.env[READ_POLICY_ENV] = raw;
	refuses("invalid read policy", "read", { path: "inside.txt" }, "read");
}
process.env[READ_POLICY_ENV] = policy;
refuses("unresolved target", "read", { path: "missing.txt" }, "read");

console.log("check-omp-eval-guard: the eval guard refuses every measured bypass and passes the rows' own calls");
