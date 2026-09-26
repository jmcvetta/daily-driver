/** Default model selectors for Omp task capability classes. */
export const MODEL_CLASS_ROLE_DEFAULTS = Object.freeze({
	mechanical: "openai-codex/gpt-6-luna:high",
	implementation: "openai-codex/gpt-5.6-terra:high",
	reasoning: "openai-codex/gpt-6-astra:high",
});

/** Display metadata for task capability roles in the Omp Roles view. */
export const MODEL_CLASS_ROLE_TAGS = Object.freeze({
	mechanical: Object.freeze({ name: "Mechanical" }),
	implementation: Object.freeze({ name: "Implementation" }),
	reasoning: Object.freeze({ name: "Reasoning" }),
});

/** Install only absent class selectors and role tags on one Omp settings instance. */
export function installModelClassDefaults(settings, modelTagsSetting) {
	const missingRoles = {};
	for (const [role, selector] of Object.entries(MODEL_CLASS_ROLE_DEFAULTS)) {
		if (!settings.getModelRole(role)) missingRoles[role] = selector;
	}
	if (Object.keys(missingRoles).length > 0) settings.overrideModelRoles(missingRoles);

	const existingTags = modelTagsSetting.get(settings);
	const modelTags = { ...existingTags };
	let addedTag = false;
	for (const [role, tag] of Object.entries(MODEL_CLASS_ROLE_TAGS)) {
		if (!Object.hasOwn(existingTags, role)) {
			modelTags[role] = tag;
			addedTag = true;
		}
	}
	if (addedTag) modelTagsSetting.override(settings, modelTags);
}
