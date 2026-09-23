export const MODEL_CLASS_ROLE_DEFAULTS = Object.freeze({
  mechanical: "openai-codex/gpt-6-luna:high",
  standard: "openai-codex/gpt-5.6-terra:high",
  advanced: "openai-codex/gpt-6-astra:high",
});

export const MODEL_CLASS_ROLE_TAGS = Object.freeze({
  mechanical: Object.freeze({ name: "Mechanical" }),
  standard: Object.freeze({ name: "Standard" }),
  advanced: Object.freeze({ name: "Advanced" }),
});

export function installModelClassDefaults(settings) {
  const missingRoles = {};
  for (const [role, selector] of Object.entries(MODEL_CLASS_ROLE_DEFAULTS)) {
    if (!settings.getModelRole(role)) missingRoles[role] = selector;
  }
  if (Object.keys(missingRoles).length > 0) settings.overrideModelRoles(missingRoles);

  const existingTags = settings.get("modelTags");
  const modelTags = { ...existingTags };
  let addedTag = false;
  for (const [role, tag] of Object.entries(MODEL_CLASS_ROLE_TAGS)) {
    if (!Object.hasOwn(existingTags, role)) {
      modelTags[role] = tag;
      addedTag = true;
    }
  }
  if (addedTag) settings.override("modelTags", modelTags);
}

