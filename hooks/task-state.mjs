import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createTaskStateController } from "../extensions/task-state.mjs";
import { contractHandoff } from "../extensions/task-contract.mjs";

const TOOL = "daily_driver_task_state";

/** shellStructure keeps a command's shell syntax and makes each quoted word and heredoc body inert. */
function shellStructure(command) {
	let out = "";
	const heredocs = [];
	for (let i = 0; i < command.length; i++) {
		const c = command[i];
		if (c === "'" || c === '"') {
			let j = i + 1;
			while (j < command.length && command[j] !== c) j += c === '"' && command[j] === "\\" ? 2 : 1;
			const body = command.slice(i + 1, j);
			// Substitution inside double quotes runs another command, so it stays a separator.
			out += c === '"' && /\$\(|`/u.test(body) ? ";" : `${c}${body.replace(/[\s;&|<>]/gu, "_")}${c}`;
			i = j;
			continue;
		}
		if (c === "\\") { out += "_"; i++; continue; }
		const heredoc = command[i - 1] !== "<" && command.slice(i).match(/^<<(-?)\s*(['"]?)([A-Za-z_]\w*)\2/u);
		if (heredoc) { heredocs.push({ delimiter: heredoc[3], tabs: heredoc[1] === "-" }); out += " "; i += heredoc[0].length - 1; continue; }
		if (c === "\n" && heredocs.length) {
			let rest = i + 1;
			for (const { delimiter, tabs } of heredocs.splice(0)) {
				for (;;) {
					const end = command.indexOf("\n", rest);
					const line = command.slice(rest, end < 0 ? command.length : end);
					rest = end < 0 ? command.length : end + 1;
					if (end < 0 || (tabs ? line.replace(/^\t+/u, "") : line) === delimiter) break;
				}
			}
			out += "\n";
			i = rest - 1;
			continue;
		}
		out += c;
	}
	return out.trimEnd();
}

/** isTaskStateCommand recognizes a standalone shell call of the task-state command route; chained work keeps its evidence. */
export function isTaskStateCommand(input) {
	const command = typeof input?.command === "string" ? input.command : Array.isArray(input?.command) ? input.command.join(" ") : "";
	const structure = shellStructure(command);
	if (/;|&&|\|\||\n|(?<![>&])&(?![>&])/u.test(structure)) return false;
	return structure.split("|").some((segment) => {
		const words = segment.trim().split(/\s+/u).map((word) => word.replace(/^['"]|['"]$/gu, ""));
		const start = words[0] === "env" ? 1 : 0;
		const script = /(?:^|\/)python3?$/u.test(words[start] ?? "") ? words[start + 1] : words[start];
		return /(?:^|\/)hooks\/task-state\.py$/u.test(script ?? "") && words.includes("--tool");
	});
}

/** handleTaskEvent maps attested harness events onto the shared task controller. */
export async function handleTaskEvent(request) {
	const ledger = request.ledger ?? { schemaVersion: 1, entries: [] };
	if (ledger.schemaVersion !== 1 || !Array.isArray(ledger.entries)) throw new Error("Unsupported private task ledger schema");
	const session = `${request.harness}:${request.sessionId}:${request.agentId ?? "main"}`;
	const inherited = request.parentLedger?.entries ?? [];
	const resolvable = [...inherited, ...(request.rootLedger?.entries ?? [])];
	const notifications = [];
	const pi = {
		appendEntry(customType, data) { ledger.entries.push({ type: "custom", customType, data }); },
		getActiveTools: () => request.toolAvailable === false ? [] : [TOOL],
		getAllTools: () => [{ name: TOOL }],
		resolveSource: (id) => resolvable.map((item) => item.data?.source ?? item.data?.observation).find((item) => item?.sourceId === id),
	};
	const ctx = { cwd: request.cwd, agent: { kind: "main" },
		sessionManager: { getBranch: () => ledger.entries, getSessionId: () => session },
		ui: { notify: (message, type) => notifications.push({ message, type }) },
	};
	const controller = createTaskStateController(pi);
	const event = request.event ?? {};
	const origin = { harness: request.harness, sessionId: request.sessionId, agentId: request.agentId ?? null,
		channel: event.origin?.kind ?? event.hook_event_name ?? event.name };
	const status = async () => (await controller.execute("runtime", { action: "status" }, null, null, ctx)).details;
	if (request.agentId && !(await status()).state) {
		const parent = inherited.filter((item) => item.customType === "daily-driver.task-state").at(-1)?.data?.state;
		if (parent?.contract) controller.adopt(ctx, contractHandoff(parent, { harness: request.harness, sessionId: request.sessionId, sourceId: parent.externalSourceId }), event.turn_id ?? event.id);
	}
	let output = {};
	if (request.action) {
		output = await controller.execute("runtime", { action: request.action, record: request.record ? JSON.stringify(request.record) : undefined }, null, null, ctx);
	} else {
		const name = event.hook_event_name ?? event.name;
		if (name === "UserPromptSubmit" || name === "prompt.submit") {
			const genuine = request.harness === "codex" ? !request.agentId : ["composer", "bridge"].includes(event.origin?.kind);
			controller.input({ text: event.prompt ?? event.text ?? "", source: genuine ? "rpc" : "delegated",
				harness: request.harness, origin, eventId: event.turn_id ?? event.id, allowTask: request.harness === "claude" && event.origin?.kind === "sdk" }, ctx);
		} else if ((name === "PostToolUse" || name === "tool.result") && isTaskStateCommand(event.tool_input ?? event.input)) {
			// The model's own task-state call is bookkeeping: its errors must not become blocker evidence or reset the correction bound.
		} else if (name === "PostToolUse" || name === "tool.result") {
			const response = event.tool_response ?? event.result;
			controller.toolResult({ toolCallId: event.tool_use_id ?? event.id, toolName: event.tool_name ?? event.tool,
				input: event.tool_input ?? event.input, content: [{ type: "text", text: typeof response === "string" ? response : JSON.stringify(response) }],
				isError: event.isError ?? response?.isError ?? (typeof response?.exit_code === "number" && response.exit_code !== 0) }, ctx);
		} else if (name === "Interrupt" || name === "turn.aborted") {
			controller.cancel(ctx, `${name}:${event.turn_id ?? event.id}`);
		} else if (name === "Stop" || name === "SubagentStop") {
			const correction = controller.stop({}, ctx);
			if (correction?.continue) output = { decision: "block", reason: correction.additionalContext };
		}
		if (["SessionStart", "SubagentStart", "session.start"].includes(name)) {
			const policy = readFileSync(new URL("../rules/constitution.md", import.meta.url), "utf8");
			controller.beforeAgentStart({ systemPrompt: [policy], origin: { ...origin, path: "rules/constitution.md" } }, ctx);
		}
		const state = (await status()).state;
		if (state && ["UserPromptSubmit", "SessionStart", "SubagentStart", "prompt.submit", "session.start", "session.compact"].includes(name)) {
			const route = request.harness === "claude" ? "\nNative task-state tool: mcp__daily-driver__task_state." : request.toolCommand ? `\nTask-state tool route: ${request.toolCommand}. Supply JSON {action, record} on stdin. The command is bound to this native session; do not change its session identity.` : "";
			const context = controller.instructions(ctx) + route;
			output = request.harness === "codex" ? { hookSpecificOutput: { hookEventName: name, additionalContext: context } } : { context };
		}
	}
	if (notifications.length && !request.action) output.systemMessage = notifications.map((item) => item.message).join("\n");
	return { ledger, output, notifications };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
	let input = "";
	for await (const chunk of process.stdin) input += chunk;
	try { process.stdout.write(JSON.stringify(await handleTaskEvent(JSON.parse(input)))); }
	catch (error) { console.error(error.message); process.exitCode = 1; }
}
