import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createTaskStateController } from "../extensions/task-state.mjs";
import { contractHandoff } from "../extensions/task-contract.mjs";

const TOOL = "daily_driver_task_state";

const RECEIPT = "daily-driver.task-receipt";

/** responseTexts lists the text a shell result may carry, from the shapes hook payloads use. */
function responseTexts(response) {
	if (typeof response === "string") return [response];
	if (Array.isArray(response)) return [response.map((part) => part?.text ?? "").join("\n")];
	if (!response || typeof response !== "object") return [];
	return ["output", "stdout", "aggregated_output", "formatted_output", "text"].map((key) => response[key])
		.filter((value) => typeof value === "string").concat(Array.isArray(response.content) ? responseTexts(response.content) : []);
}

/** consumeReceipt removes the receipt whose recorded output this result carries exactly, if one is pending. */
function consumeReceipt(ledger, response) {
	const digests = new Set(responseTexts(response).map((text) => createHash("sha256").update(text.trim()).digest("hex")));
	const index = ledger.entries.findIndex((entry) => entry.customType === RECEIPT && digests.has(entry.data?.digest));
	if (index >= 0) ledger.entries.splice(index, 1);
	return index >= 0;
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
		} else if (name === "PostToolUse" || name === "tool.result") {
			const response = event.tool_response ?? event.result;
			const isError = event.isError ?? response?.isError ?? (typeof response?.exit_code === "number" && response.exit_code !== 0);
			// The model's own task-state call is bookkeeping: its exact output matches a receipt the command recorded.
			if (!isError && consumeReceipt(ledger, response)) return { ledger, output, notifications };
			controller.toolResult({ toolCallId: event.tool_use_id ?? event.id, toolName: event.tool_name ?? event.tool,
				input: event.tool_input ?? event.input, content: [{ type: "text", text: typeof response === "string" ? response : JSON.stringify(response) }],
				isError }, ctx);
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
			const route = request.harness === "claude" ? "\nNative task-state tool: mcp__daily-driver__task_state." : request.toolCommand ? `\nTask-state tool route: ${request.toolCommand}. Supply JSON {action, record} on stdin. A rejection still exits 0: read isError in the JSON answer. Run the command on its own, not chained with other work, so its exact output matches the receipt that keeps it out of task evidence. The command is bound to this native session; do not change its session identity.` : "";
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
